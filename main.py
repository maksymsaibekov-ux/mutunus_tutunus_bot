import os
import requests
from flask import Flask, request

app = Flask(__name__)

TG_TOKEN = os.environ["TG_TOKEN"]
GROQ_KEY = os.environ["GROQ_API_KEY"]
TG_URL = f"https://api.telegram.org/bot{TG_TOKEN}"


def ask_ai(text):
    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_KEY}"},
        json={
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": "Ти корисний помічник. Відповідай українською."},
                {"role": "user", "content": text},
            ],
        },
        timeout=30,
    )
    if r.status_code != 200:
        raise Exception(f"Groq {r.status_code}: {r.text[:300]}")
    return r.json()["choices"][0]["message"]["content"]


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
        try:
            answer = ask_ai(msg["text"])
                except Exception as e:
            print("AI error:", e, flush=True)
            answer = f"Помилка: {e}"
        requests.post(
            f"{TG_URL}/sendMessage",
            json={"chat_id": msg["chat"]["id"], "text": answer[:4000]},
        )
    return "ok"
