import os
import requests
from flask import Flask, request

app = Flask(__name__)

TG_TOKEN = os.environ["TG_TOKEN"]
GROQ_KEY = os.environ["GROQ_API_KEY"]
MODEL = os.environ.get("MODEL", "openai/gpt-oss-120b")
TG_URL = f"https://api.telegram.org/bot{TG_TOKEN}"

SYSTEM_PROMPT = (
    "Ти дружній і розумний помічник у Telegram. "
    "Відповідай українською, коротко і по суті, без води. "
    "Якщо питання незрозуміле, став одне уточнююче питання. "
    "Якщо не знаєш відповіді, так і скажи, не вигадуй."
)

# chat_id -> список останніх повідомлень (пам'ять діалогу)
history = {}


def ask_ai(chat_id, text):
    msgs = history.setdefault(chat_id, [])
    msgs.append({"role": "user", "content": text})
    del msgs[:-10]  # пам'ятаємо останні 10 повідомлень

    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_KEY}"},
        json={
            "model": MODEL,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + msgs,
            "temperature": 0.7,
        },
        timeout=60,
    )
    if r.status_code != 200:
        raise Exception(f"Groq {r.status_code}: {r.text[:300]}")

    answer = r.json()["choices"][0]["message"].get("content") or "Порожня відповідь, спробуй ще раз."
    msgs.append({"role": "assistant", "content": answer})
    return answer


@app.route("/")
def home():
    return "ok"


@app.route("/set_webhook")
def set_webhook():
    url = f"https://mutunus-tutunus-bot.onrender.com/{TG_TOKEN}"
    r = requests.get(f"{TG_URL}/setWebhook", params={"url": url})
    return r.text


@app.route(f"/{TG_TOKEN}", methods=["POST"])
def webhook():
    msg = (request.get_json() or {}).get("message")
    if msg and "text" in msg:
        chat_id = msg["chat"]["id"]
        if msg["text"] == "/start":
            history.pop(chat_id, None)
            answer = "Привіт! Пиши що завгодно 🙂"
        else:
            try:
                answer = ask_ai(chat_id, msg["text"])
            except Exception as e:
                print("AI error:", e, flush=True)
                answer = f"Помилка: {e}"
        requests.post(
            f"{TG_URL}/sendMessage",
            json={"chat_id": chat_id, "text": answer[:4000]},
        )
    return "ok"
