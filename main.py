import os
import json
import hmac
import requests
from flask import Flask, request

app = Flask(__name__)

TG_TOKEN = os.environ["TG_TOKEN"]
GROQ_KEY = os.environ["GROQ_API_KEY"]
UP_URL = os.environ["UPSTASH_URL"]
UP_TOKEN = os.environ["UPSTASH_TOKEN"]
MODEL = os.environ.get("MODEL", "openai/gpt-oss-120b")
AUTO_LEARN = os.environ.get("AUTO_LEARN", "1") == "1"
TG_URL = f"https://api.telegram.org/bot{TG_TOKEN}"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

WEBHOOK_SECRET = os.environ["WEBHOOK_SECRET"]
ALLOWED_IDS = {int(x) for x in os.environ.get("ALLOWED_IDS", "").split(",") if x.strip()}

BASE_PROMPT = (
    "Ти дружній і розумний помічник у Telegram. "
    "Відповідай українською, коротко і по суті, без води. "
    "Якщо питання незрозуміле, став одне уточнююче питання. "
    "Якщо не знаєш відповіді, так і скажи, не вигадуй."
)


# ---------- База даних (Upstash Redis через HTTP) ----------
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
        redis("LTRIM", f"facts:{chat_id}", -30, -1)  # максимум 30 фактів


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
    """Просимо AI знайти в повідомленні стійкий факт про користувача."""
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
    facts = load_facts(chat_id)
    system = BASE_PROMPT
    if facts:
        system += "\n\nЩо ти знаєш про користувача:\n" + "\n".join(f"- {f}" for f in facts)

    msgs = load_history(chat_id)
    msgs.append({"role": "user", "content": text})
    answer = groq([{"role": "system", "content": system}] + msgs[-10:])
    answer = answer or "Порожня відповідь, спробуй ще раз."
    msgs.append({"role": "assistant", "content": answer})
    save_history(chat_id, msgs)

    # автоматичне "навчання": запам'ятовуємо факти про користувача
    if AUTO_LEARN:
        try:
            fact = extract_fact(text)
            if fact:
                add_fact(chat_id, fact)
        except Exception as e:
            print("Learn error:", e, flush=True)
    return answer


# ---------- Telegram ----------
def handle_text(chat_id, text):
    if text == "/start":
        redis("DEL", f"hist:{chat_id}")
        return (
            "Привіт! Пиши що завгодно 🙂\n\n"
            "Команди:\n"
            "/remember текст — запам'ятати факт\n"
            "/memory — що я про тебе знаю\n"
            "/forget — забути всі факти"
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
    return ask_ai(chat_id, text)


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
    if msg and "text" in msg:
        chat_id = msg["chat"]["id"]
        user_id = msg.get("from", {}).get("id")
        if ALLOWED_IDS and user_id not in ALLOWED_IDS:
            answer = "Вибач, цей бот приватний."
        else:
            try:
                answer = handle_text(chat_id, msg["text"][:2000])
            except Exception as e:
                print("Error:", e, flush=True)
                answer = "Щось пішло не так, спробуй пізніше."
        requests.post(
            f"{TG_URL}/sendMessage",
            json={"chat_id": chat_id, "text": answer[:4000]},
        )
    return "ok"
