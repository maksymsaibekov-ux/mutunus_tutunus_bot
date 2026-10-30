import io
import os
import re
import json
import hmac
import hashlib
import threading
import requests
from flask import Flask, request
from pypdf import PdfReader
from docx import Document as DocxDocument
from youtube_transcript_api import YouTubeTranscriptApi

app = Flask(__name__)

TG_TOKEN = os.environ["TG_TOKEN"]
GROQ_KEY = os.environ["GROQ_API_KEY"]
UP_URL = os.environ["UPSTASH_URL"]
UP_TOKEN = os.environ["UPSTASH_TOKEN"]
VEC_URL = os.environ["UPSTASH_VECTOR_URL"].rstrip("/")
VEC_TOKEN = os.environ["UPSTASH_VECTOR_TOKEN"]
MODEL = os.environ.get("MODEL", "openai/gpt-oss-120b")
AUTO_LEARN = os.environ.get("AUTO_LEARN", "1") == "1"
TG_URL = f"https://api.telegram.org/bot{TG_TOKEN}"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

WEBHOOK_SECRET = os.environ["WEBHOOK_SECRET"]
ALLOWED_IDS = {int(x) for x in os.environ.get("ALLOWED_IDS", "").split(",") if x.strip()}

# Необов'язкові ключі (функції вмикаються, лише якщо ключ доданий)
X_BEARER = os.environ.get("X_BEARER_TOKEN", "")
THREADS_TOKEN = os.environ.get("THREADS_TOKEN", "")
X_MAX_POSTS = int(os.environ.get("X_MAX_POSTS", "20"))  # 10..100, кожен допис платний

MAX_CHUNKS = 400
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
SUMMARY_CHARS = int(os.environ.get("SUMMARY_CHARS", "9000"))   # скільки тексту даємо моделі
ANALYZE_CHARS = int(os.environ.get("ANALYZE_CHARS", "9000"))

BASE_PROMPT = (
    "Ти дружній і розумний помічник у Telegram. "
    "Відповідай українською, коротко і по суті, без води. "
    "Якщо питання незрозуміле, став одне уточнююче питання. "
    "Якщо не знаєш відповіді, так і скажи, не вигадуй."
)

PROMPTS = {
    "analyze": (
        "Ти аналітик соціальних мереж. Тобі дали добірку дописів чи коментарів. "
        "Відповідай українською за структурою:\n"
        "1) Головні теми (3-5 пунктів).\n"
        "2) Загальний настрій: позитивний, негативний чи нейтральний, приблизно у відсотках.\n"
        "3) Основні позиції: аргументи «за» і «проти», якщо вони є.\n"
        "4) Повторювані ідеї чи цікаві спостереження (перефразуй, не цитуй довго).\n"
        "5) Короткий висновок у 1-2 реченнях.\n"
        "Спирайся лише на наданий текст. Якщо даних мало, скажи про це. Не вигадуй."
    ),
    "summary": (
        "Ти робиш конспекти. Тобі дали текст (стаття, транскрипт відео чи документ). "
        "Відповідай українською: спочатку 2-3 речення про що це, потім 5-8 ключових "
        "пунктів, наприкінці короткий висновок. Спирайся лише на наданий текст, не вигадуй."
    ),
}

YT_RE = re.compile(
    r"(?:youtube\.com/(?:watch\?(?:\S*&)?v=|shorts/|embed/|live/)|youtu\.be/)([A-Za-z0-9_-]{11})"
)


class UserError(Exception):
    """Помилка, текст якої можна показати користувачу."""


# ---------- Telegram ----------
def send(chat_id, text):
    requests.post(
        f"{TG_URL}/sendMessage",
        json={"chat_id": chat_id, "text": text[:4000]},
        timeout=20,
    )


def download_tg_file(file_id):
    info = requests.get(f"{TG_URL}/getFile", params={"file_id": file_id}, timeout=20).json()
    if not info.get("ok"):
        raise UserError("Не вдалося отримати файл (Telegram дозволяє ботам до 20 МБ).")
    path = info["result"]["file_path"]
    r = requests.get(f"https://api.telegram.org/file/bot{TG_TOKEN}/{path}", timeout=60)
    r.raise_for_status()
    return r.content


# ---------- Redis ----------
def redis(*cmd):
    r = requests.post(
        UP_URL,
        headers={"Authorization": f"Bearer {UP_TOKEN}"},
        json=list(cmd),
        timeout=10,
    )
    r.raise_for_status()
    return r.json().get("result")


def load_history(chat_id):
    raw = redis("GET", f"hist:{chat_id}")
    return json.loads(raw) if raw else []


def save_history(chat_id, msgs):
    redis("SET", f"hist:{chat_id}", json.dumps(msgs[-10:], ensure_ascii=False))


def load_facts(chat_id):
    return redis("LRANGE", f"facts:{chat_id}", 0, -1) or []


def add_fact(chat_id, fact):
    if fact not in load_facts(chat_id):
        redis("RPUSH", f"facts:{chat_id}", fact)
        redis("LTRIM", f"facts:{chat_id}", -30, -1)


# ---------- Векторна база ----------
def vec(path, payload, method="POST"):
    r = requests.request(
        method,
        f"{VEC_URL}/{path}",
        headers={"Authorization": f"Bearer {VEC_TOKEN}"},
        json=payload,
        timeout=60,
    )
    if r.status_code != 200:
        raise Exception(f"Vector {r.status_code}: {r.text[:200]}")
    return r.json()


def search_docs(chat_id, question):
    res = vec(
        f"query-data/u{chat_id}",
        {"data": question, "topK": 4, "includeMetadata": True},
    )
    out = []
    for item in res.get("result", []):
        meta = item.get("metadata") or {}
        if meta.get("text"):
            out.append((meta.get("source", "?"), meta["text"]))
    return out


def chunk_text(text):
    text = re.sub(r"\s+", " ", text).strip()
    chunks, i = [], 0
    while i < len(text):
        chunks.append(text[i:i + CHUNK_SIZE])
        i += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


def ingest_text(chat_id, name, text):
    """Ділить текст на шматки й зберігає у векторній базі. Повертає (кількість, обрізано?)."""
    chunks = chunk_text(text)
    if not chunks:
        raise UserError(
            "Не знайшов тексту. Якщо це скан або PDF із картинок, я такий прочитати не можу."
        )
    truncated = len(chunks) > MAX_CHUNKS
    chunks = chunks[:MAX_CHUNKS]

    ns = f"u{chat_id}"
    doc_id = hashlib.md5(name.encode()).hexdigest()[:8]
    for i in range(0, len(chunks), 20):
        batch = [
            {
                "id": f"{doc_id}:{i + j}",
                "data": c,
                "metadata": {"text": c, "source": name},
            }
            for j, c in enumerate(chunks[i:i + 20])
        ]
        vec(f"upsert-data/{ns}", batch)
    redis("SADD", f"docs:{chat_id}", name)
    return len(chunks), truncated


# ---------- Читання файлів ----------
def extract_text(data, name):
    lower = name.lower()
    if lower.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((p.extract_text() or "") for p in reader.pages)
    if lower.endswith(".docx"):
        doc = DocxDocument(io.BytesIO(data))
        parts = [p.text for p in doc.paragraphs]
        for table in doc.tables:
            for row in table.rows:
                parts.append(" | ".join(c.text for c in row.cells))
        return "\n".join(parts)
    return data.decode("utf-8", errors="ignore")  # txt, md


def handle_document(chat_id, doc):
    name = doc.get("file_name", "file")
    if not name.lower().endswith((".pdf", ".docx", ".txt", ".md")):
        raise UserError("Я читаю PDF, DOCX і TXT. Старий формат .doc спершу збережи як .docx.")
    if doc.get("file_size", 0) > 15 * 1024 * 1024:
        raise UserError("Файл завеликий, максимум 15 МБ.")

    send(chat_id, f"Читаю «{name}»… ⏳")
    text = extract_text(download_tg_file(doc["file_id"]), name)

    # якщо перед цим обрано /analyze або /summary, аналізуємо файл, а не зберігаємо
    mode = redis("GET", f"mode:{chat_id}")
    if mode in PROMPTS:
        redis("DEL", f"mode:{chat_id}")
        return run_mode(mode, text)

    count, truncated = ingest_text(chat_id, name, text)
    msg = f"Готово ✅ «{name}» збережено ({count} шматків). Тепер став питання за змістом файлу."
    if truncated:
        msg += f"\n⚠️ Файл великий, прочитано лише перші {MAX_CHUNKS} шматків."
    return msg


# ---------- AI ----------
def groq(messages, temperature=0.7):
    r = requests.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {GROQ_KEY}"},
        json={"model": MODEL, "messages": messages, "temperature": temperature},
        timeout=90,
    )
    if r.status_code != 200:
        raise Exception(f"Groq {r.status_code}: {r.text[:300]}")
    return r.json()["choices"][0]["message"].get("content") or ""


def extract_fact(text):
    out = groq(
        [
            {
                "role": "system",
                "content": (
                    "Ти витягуєш факти про користувача. Якщо в повідомленні "
                    "користувач розповідає щось стійке про себе (ім'я, вік, місто, "
                    "робота, хобі, уподобання, плани), поверни ОДНЕ коротке речення "
                    "українською, наприклад: 'Користувача звати Макс'. "
                    "Якщо такого факту немає, відповідь рівно NONE."
                ),
            },
            {"role": "user", "content": text},
        ],
        temperature=0,
    ).strip()
    if not out or "NONE" in out.upper():
        return None
    return out[:200]


def ask_ai(chat_id, text):
    system = BASE_PROMPT

    facts = load_facts(chat_id)
    if facts:
        system += "\n\nЩо ти знаєш про користувача:\n" + "\n".join(f"- {f}" for f in facts)

    if redis("SCARD", f"docs:{chat_id}"):
        try:
            found = search_docs(chat_id, text)
            if found:
                system += (
                    "\n\nНижче фрагменти з документів і відео користувача. Якщо питання "
                    "стосується їх, відповідай на їх основі й назви джерело. Якщо відповіді "
                    "там немає, чесно скажи про це і не вигадуй.\n"
                )
                system += "\n".join(f"[{src}]: {chunk}" for src, chunk in found)
        except Exception as e:
            print("Search error:", e, flush=True)

    msgs = load_history(chat_id)
    msgs.append({"role": "user", "content": text})
    answer = groq([{"role": "system", "content": system}] + msgs[-10:])
    answer = answer or "Порожня відповідь, спробуй ще раз."
    msgs.append({"role": "assistant", "content": answer})
    save_history(chat_id, msgs)

    if AUTO_LEARN:
        try:
            fact = extract_fact(text)
            if fact:
                add_fact(chat_id, fact)
        except Exception as e:
            print("Learn error:", e, flush=True)
    return answer


def run_mode(mode, material):
    """Аналіз або конспект наданого тексту."""
    material = material.strip()
    if len(material) < 80:
        raise UserError("Замало тексту, щоб щось проаналізувати. Надішли більше.")
    out = groq(
        [
            {"role": "system", "content": PROMPTS[mode]},
            {"role": "user", "content": material[:ANALYZE_CHARS]},
        ],
        temperature=0.3,
    )
    out = out or "Порожня відповідь, спробуй ще раз."
    if len(material) > ANALYZE_CHARS:
        out += f"\n\n⚠️ Проаналізовано лише перші {ANALYZE_CHARS} символів із {len(material)}."
    return out


# ---------- YouTube ----------
def get_transcript(video_id):
    try:
        fetched = YouTubeTranscriptApi().fetch(video_id, languages=["uk", "ru", "en"])
        return " ".join(s.text for s in fetched)
    except Exception as e:
        name = type(e).__name__
        print("YT error:", name, str(e)[:200], flush=True)
        if "Blocked" in name:
            raise UserError(
                "YouTube блокує запити з мого сервера (так буває з хмарними хостингами).\n\n"
                "Обхід: відкрий відео → «Показати текст відео» (Show transcript) під описом → "
                "скопіюй текст → надішли мені командою /summary (спочатку напиши /summary, "
                "потім вставляй текст, або надішли його файлом .txt)."
            )
        if "Disabled" in name or "NoTranscript" in name:
            raise UserError("У цього відео немає субтитрів (або вони вимкнені), тож аналізувати нічого.")
        if "Unavailable" in name or "Unplayable" in name:
            raise UserError("Це відео недоступне (приватне, видалене або з віковим обмеженням).")
        raise UserError("Не вдалося дістати субтитри цього відео. Спробуй інше або обхід через /summary.")


def sample_text(text, limit):
    if len(text) <= limit:
        return text
    part = limit // 3
    mid = len(text) // 2 - part // 2
    return text[:part] + "\n[...]\n" + text[mid:mid + part] + "\n[...]\n" + text[-part:]


def handle_youtube(chat_id, text):
    m = YT_RE.search(text)
    if not m:
        raise UserError("Не бачу посилання на YouTube. Надішли його повністю.")
    vid = m.group(1)
    send(chat_id, "Дістаю субтитри… ⏳")
    transcript = get_transcript(vid)

    saved = True
    try:
        ingest_text(chat_id, f"YouTube {vid}", transcript)
    except Exception as e:
        print("Ingest error:", e, flush=True)
        saved = False

    sampled = sample_text(transcript, SUMMARY_CHARS)
    summary = groq(
        [
            {"role": "system", "content": PROMPTS["summary"]},
            {"role": "user", "content": sampled},
        ],
        temperature=0.3,
    )
    out = f"🎬 Конспект відео:\n\n{summary}"
    if len(transcript) > SUMMARY_CHARS:
        out += "\n\n(Відео довге, тож для конспекту взято початок, середину й кінець.)"
    if saved:
        out += "\n\nТранскрипт збережено, можеш ставити питання про це відео."
    return out


# ---------- Соцмережі (необов'язково) ----------
def fetch_x(topic):
    n = max(10, min(X_MAX_POSTS, 100))
    r = requests.get(
        "https://api.x.com/2/tweets/search/recent",
        headers={"Authorization": f"Bearer {X_BEARER}"},
        params={"query": f"{topic} -is:retweet", "max_results": n, "tweet.fields": "created_at,lang"},
        timeout=30,
    )
    if r.status_code != 200:
        raise Exception(f"X {r.status_code}: {r.text[:200]}")
    return [t["text"] for t in r.json().get("data", [])]


def fetch_threads(topic):
    r = requests.get(
        "https://graph.threads.net/v1.0/keyword_search",
        params={
            "q": topic,
            "search_type": "TOP",
            "fields": "text,username,timestamp",
            "access_token": THREADS_TOKEN,
        },
        timeout=30,
    )
    if r.status_code != 200:
        raise Exception(f"Threads {r.status_code}: {r.text[:200]}")
    return [p["text"] for p in r.json().get("data", []) if p.get("text")]


def handle_social(source, topic):
    if not topic:
        raise UserError(f"Напиши так: /{source} тема")
    if source == "x":
        if not X_BEARER:
            raise UserError(
                "Пошук в X не підключено: для нього потрібен платний доступ до API X "
                "(оплата за кожен прочитаний допис). Поки що скопіюй дописи й надішли їх "
                "після команди /analyze."
            )
        posts, label = fetch_x(topic), "X, останні 7 днів"
    else:
        if not THREADS_TOKEN:
            raise UserError(
                "Пошук у Threads не підключено: для публічного пошуку потрібен застосунок Meta "
                "зі схваленим дозволом. Поки що скопіюй дописи й надішли їх після /analyze."
            )
        posts, label = fetch_threads(topic), "Threads"
    if not posts:
        raise UserError("За цією темою нічого не знайшов.")
    material = "\n".join("- " + p.replace("\n", " ") for p in posts)
    out = run_mode("analyze", material)
    return f"📊 {label}: проаналізовано {len(posts)} дописів за темою «{topic}»\n\n{out}"


# ---------- Команди ----------
def handle_text(chat_id, text):
    parts = text.split(None, 1)
    cmd = parts[0].lower().split("@")[0] if parts else ""
    arg = parts[1].strip() if len(parts) > 1 else ""

    if cmd == "/start":
        redis("DEL", f"hist:{chat_id}")
        redis("DEL", f"mode:{chat_id}")
        return (
            "Привіт! Пиши що завгодно 🙂\n\n"
            "Що я вмію:\n"
            "• Відповідати на питання й пам'ятати розмову\n"
            "• Читати PDF, DOCX, TXT: надішли файл і став питання\n"
            "• Конспект YouTube: надішли посилання\n"
            "• /analyze: аналіз добірки дописів із X, Threads чи будь-де\n"
            "• /summary: конспект довгого тексту\n"
            "• /x тема, /threads тема: пошук і аналіз (якщо підключено)\n\n"
            "Пам'ять:\n"
            "/remember текст, /memory, /forget\n"
            "/docs, /cleardocs"
        )
    if cmd == "/remember":
        if not arg:
            return "Напиши так: /remember Я люблю каву"
        add_fact(chat_id, arg[:200])
        return "Запам'ятав ✅"
    if cmd == "/memory":
        facts = load_facts(chat_id)
        if not facts:
            return "Поки що я нічого про тебе не знаю."
        return "Що я знаю:\n" + "\n".join(f"• {f}" for f in facts)
    if cmd == "/forget":
        redis("DEL", f"facts:{chat_id}")
        return "Усе забув 🧹"
    if cmd == "/docs":
        names = redis("SMEMBERS", f"docs:{chat_id}") or []
        if not names:
            return "Документів немає. Надішли PDF, DOCX або посилання на YouTube."
        return "Збережене:\n" + "\n".join(f"• {n}" for n in names)
    if cmd == "/cleardocs":
        vec(f"reset/u{chat_id}", None, method="DELETE")
        redis("DEL", f"docs:{chat_id}")
        return "Усе збережене видалено 🧹"
    if cmd == "/yt":
        return handle_youtube(chat_id, arg)
    if cmd in ("/analyze", "/summary"):
        mode = cmd[1:]
        if arg:
            return run_mode(mode, arg)
        redis("SET", f"mode:{chat_id}", mode, "EX", 900)
        what = "добірку дописів чи коментарів" if mode == "analyze" else "текст для конспекту"
        return f"Надішли {what} наступним повідомленням (або файлом PDF/DOCX/TXT). Маю 15 хвилин 🙂"
    if cmd == "/x":
        return handle_social("x", arg)
    if cmd == "/threads":
        return handle_social("threads", arg)

    # звичайний текст
    mode = redis("GET", f"mode:{chat_id}")
    if mode in PROMPTS and not text.startswith("/"):
        redis("DEL", f"mode:{chat_id}")
        return run_mode(mode, text)
    if YT_RE.search(text):
        return handle_youtube(chat_id, text)
    return ask_ai(chat_id, text)


def process_message(msg):
    chat_id = msg["chat"]["id"]
    try:
        if "document" in msg:
            answer = handle_document(chat_id, msg["document"])
        elif "text" in msg:
            answer = handle_text(chat_id, msg["text"][:4000])
        else:
            return
    except UserError as e:
        answer = str(e)
    except Exception as e:
        print("Error:", e, flush=True)
        s = str(e)
        if "Groq 429" in s or "Groq 413" in s:
            answer = ("Забагато тексту або запитів для безкоштовного ліміту Groq. "
                      "Зачекай хвилину або надішли менший фрагмент.")
        else:
            answer = "Щось пішло не так, спробуй пізніше."
    send(chat_id, answer)


# ---------- Flask ----------
@app.route("/")
def home():
    return "ok"


@app.route("/set_webhook")
def set_webhook():
    r = requests.post(
        f"{TG_URL}/setWebhook",
        json={
            "url": "https://mutunus-tutunus-bot.onrender.com/webhook",
            "secret_token": WEBHOOK_SECRET,
            "allowed_updates": ["message"],
            "drop_pending_updates": True,
        },
    )
    return r.text


@app.route("/webhook", methods=["POST"])
def webhook():
    header = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not hmac.compare_digest(header, WEBHOOK_SECRET):
        return "forbidden", 403

    msg = (request.get_json(silent=True) or {}).get("message")
    if msg:
        user_id = msg.get("from", {}).get("id")
        if ALLOWED_IDS and user_id not in ALLOWED_IDS:
            send(msg["chat"]["id"], "Вибач, цей бот приватний.")
        else:
            threading.Thread(target=process_message, args=(msg,), daemon=True).start()
    return "ok"
