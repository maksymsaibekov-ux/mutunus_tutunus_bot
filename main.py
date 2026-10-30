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

MAX_CHUNKS = 400      # максимум шматків з одного файлу
CHUNK_SIZE = 800      # символів у шматку
CHUNK_OVERLAP = 100   # перекриття між шматками

BASE_PROMPT = (
    "Ти дружній і розумний помічник у Telegram. "
    "Відповідай українською, коротко і по суті, без води. "
    "Якщо питання незрозуміле, став одне уточнююче питання. "
    "Якщо не знаєш відповіді, так і скажи, не вигадуй."
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


# ---------- Redis (історія, факти, список документів) ----------
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


# ---------- Векторна база (документи) ----------
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


def chunk_text(text):
    text = re.sub(r"\s+", " ", text).strip()
    chunks, i = [], 0
    while i < len(text):
        chunks.append(text[i:i + CHUNK_SIZE])
        i += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


def handle_document(chat_id, doc):
    name = doc.get("file_name", "file")
    if not name.lower().endswith((".pdf", ".docx", ".txt", ".md")):
        raise UserError("Я читаю PDF, DOCX і TXT. Старий формат .doc спершу збережи як .docx.")
    if doc.get("file_size", 0) > 15 * 1024 * 1024:
        raise UserError("Файл завеликий, максимум 15 МБ.")

    send(chat_id, f"Читаю «{name}»… ⏳")
    text = extract_text(download_tg_file(doc["file_id"]), name)
    chunks = chunk_text(text)
    if not chunks:
        raise UserError(
            "Не знайшов у файлі тексту. Якщо це скан або PDF із картинок, "
            "я такий прочитати не можу."
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

    msg = f"Готово ✅ «{name}» збережено ({len(chunks)} шматків). Тепер став питання за змістом файлу."
    if truncated:
        msg += f"\n⚠️ Файл великий, прочитано лише перші {MAX_CHUNKS} шматків."
    return msg


# ---------- Робота з AI ----------
def groq(messages, temperature=0.7):
    r = requests.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {GROQ_KEY}"},
        json={"model": MODEL, "messages": messages, "temperature": temperature},
        timeout=60,
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

    # RAG: шукаємо потрібні шматки в документах користувача
    if redis("SCARD", f"docs:{chat_id}"):
        try:
            found = search_docs(chat_id, text)
            if found:
                system += (
                    "\n\nНижче фрагменти з документів користувача. Якщо питання "
                    "стосується їх, відповідай на їх основі й назви файл. Якщо відповіді "
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


# ---------- Команди ----------
def handle_text(chat_id, text):
    if text == "/start":
        redis("DEL", f"hist:{chat_id}")
        return (
            "Привіт! Пиши що завгодно 🙂 Можеш надіслати PDF або DOCX, "
            "і я відповідатиму за його змістом.\n\n"
            "Команди:\n"
            "/remember текст — запам'ятати факт\n"
            "/memory — що я про тебе знаю\n"
            "/forget — забути всі факти\n"
            "/docs — список збережених документів\n"
            "/cleardocs — видалити всі документи"
        )
    if text.startswith("/remember"):
        fact = text[len("/remember"):].strip()
        if not fact:
            return "Напиши так: /remember Я люблю каву"
        add_fact(chat_id, fact[:200])
        return "Запам'ятав ✅"
    if text == "/memory":
        facts = load_facts(chat_id)
        if not facts:
            return "Поки що я нічого про тебе не знаю."
        return "Що я знаю:\n" + "\n".join(f"• {f}" for f in facts)
    if text == "/forget":
        redis("DEL", f"facts:{chat_id}")
        return "Усе забув 🧹"
    if text == "/docs":
        names = redis("SMEMBERS", f"docs:{chat_id}") or []
        if not names:
            return "Документів немає. Надішли PDF або DOCX."
        return "Збережені документи:\n" + "\n".join(f"• {n}" for n in names)
    if text == "/cleardocs":
        vec(f"reset/u{chat_id}", None, method="DELETE")
        redis("DEL", f"docs:{chat_id}")
        return "Усі документи видалено 🧹"
    return ask_ai(chat_id, text)


def process_message(msg):
    chat_id = msg["chat"]["id"]
    try:
        if "document" in msg:
            answer = handle_document(chat_id, msg["document"])
        elif "text" in msg:
            answer = handle_text(chat_id, msg["text"][:2000])
        else:
            return
    except UserError as e:
        answer = str(e)
    except Exception as e:
        print("Error:", e, flush=True)
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
            # обробляємо у фоні, щоб одразу відповісти Telegram
            threading.Thread(target=process_message, args=(msg,), daemon=True).start()
    return "ok"
