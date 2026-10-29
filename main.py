import telebot
import os
import urllib.request
import json
from flask import Flask, request

# Зчитуємо правильний токен з налаштувань Render
tg_token = os.environ.get('TELEGRAM_TOKEN')
RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL')

bot = telebot.TeleBot(tg_token)
app = Flask(__name__)

print(f"🚀 Запускаємо офіційного ШІ-бота на {RENDER_EXTERNAL_URL}")

@app.route('/' + tg_token, methods=['POST'])
def getMessage():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

@app.route("/")
def webhook_index():
    return "ШІ-сервер працює стабільно!", 200

@bot.message_handler(content_types=['text'])
def handle_message(message):
    user_prompt = message.text
    print("Отримано запит в Telegram: " + user_prompt)
    
    if user_prompt.lower().strip() == "/start":
        bot.reply_to(message, "👋 Привіт! Я твій всезнаючий автономний ШІ-бот. Я підключений до моделі Qwen і знаю абсолютно все на світі! Запитай мене про що завгодно українською мовою.")
        return

    try:
        # Безкоштовний безлімітний ШІ-шлюз, який не блокується хмарою Render
        url = "https://pollinations.ai"
        headers = {"Content-Type": "application/json"}
        data = {
            "messages": [
                {"role": "system", "content": "Ти дружній та дуже розумний асистент. Обов'язково відповідай виключно українською мовою, коротко і чітко на будь-які запитання користувача."},
                {"role": "user", "content": user_prompt}
            ],
            "model": "qwen",
            "json": False
        }
        
        req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers)
        
        with urllib.request.urlopen(req, timeout=20) as response:
            ai_answer = response.read().decode('utf-8').strip()
            
        if ai_answer:
            bot.reply_to(message, ai_answer)
            print("ШІ успішно надіслав відповідь!")
        else:
            bot.reply_to(message, "🤖 Мої віртуальні мізки замислилися. Напиши це повідомлення ще раз!")
            
    except Exception as e:
        print("Помилка ШІ: ", e)
        bot.reply_to(message, "🤖 Ой, хмарна нейромережа зараз оновлюється. Напиши мені це повідомлення ще раз прямо зараз!")

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=f"{RENDER_EXTERNAL_URL}/{tg_token}")
    app.run(host="0.0.0.0", port=10000)
