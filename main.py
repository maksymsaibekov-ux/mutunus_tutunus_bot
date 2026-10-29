import telebot
import os
import urllib.request
import json
from flask import Flask, request

# 1. Зчитуємо токен Telegram з налаштувань Render
tg_token = os.environ.get('TELEGRAM_TOKEN')
RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL')

bot = telebot.TeleBot(tg_token)
app = Flask(__name__)

print(f"🚀 Запускаємо безвідмовного ШІ-бота на {RENDER_EXTERNAL_URL}")

@app.route('/' + tg_token, methods=['POST'])
def getMessage():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

@app.route("/")
def webhook_index():
    return "Бот працює зі стабільним ШІ!", 200

@bot.message_handler(content_types=['text'])
def handle_message(message):
    user_prompt = message.text
    print("Отримано запит в Telegram: " + user_prompt)
    
    if user_prompt.lower().strip() == "/start":
        bot.reply_to(message, "👋 Привіт! Я твій повністю автономний ШІ-бот. Запитай мене про що завгодно українською мовою!")
        return

    try:
        # 2. Прямий стабільний запит до безлімітного ШІ-шлюзу без використання API-ключів
        req = urllib.request.Request(
            "https://pollinations.ai", 
            data=json.dumps({
                "messages": [
                    {"role": "system", "content": "Ти дружній та розумний асистент. Обов'язково відповідай коротко, лаконічно і виключно українською мовою."},
                    {"role": "user", "content": user_prompt}
                ],
                "model": "qwen"
            }).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        
        with urllib.request.urlopen(req, timeout=15) as response:
            ai_answer = response.read().decode('utf-8')
            
        if ai_answer:
            bot.reply_to(message, ai_answer)
            print("ШІ успішно надіслав текстову відповідь!")
        else:
            bot.reply_to(message, "Я трохи замислився, спробуй ще раз!")
            
    except Exception as e:
        print("Помилка підключення до ШІ: ", e)
        bot.reply_to(message, "🤖 Мої віртуальні мізки зараз оновлюються. Напиши мені це повідомлення ще раз прямо зараз!")

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=f"{RENDER_EXTERNAL_URL}/{tg_token}")
    app.run(host="0.0.0.0", port=10000)
