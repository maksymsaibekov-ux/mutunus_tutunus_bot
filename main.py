import telebot
import os
import urllib.request
import json
from flask import Flask, request

# 1. Зчитуємо токен Telegram та ключ Mistral з налаштувань Render
tg_token = os.environ.get('TELEGRAM_TOKEN')
mistral_key = os.environ.get('MISTRAL_API_KEY')
RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL')

bot = telebot.TeleBot(tg_token)
app = Flask(__name__)

print(f"🚀 Запускаємо справжнього ШІ-бота Mistral на {RENDER_EXTERNAL_URL}")

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
        bot.reply_to(message, "👋 Привіт! Я твій всезнаючий автономний ШІ-бот. Запитай мене про що завгодно українською мовою!")
        return

    try:
        # 2. Офіційний прямий HTTP-запит до легального API Mistral AI
        url = "https://mistral.ai"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {mistral_key}"
        }
        data = {
            "model": "mistral-small-latest",
            "messages": [
                {"role": "system", "content": "Ти дружній та дуже розумний асистент. Обов'язково відповідай виключно українською мовою, коротко і чітко."},
                {"role": "user", "content": user_prompt}
            ]
        }
        
        req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers)
        
        with urllib.request.urlopen(req, timeout=20) as response:
            result = json.loads(response.read().decode('utf-8'))
            ai_answer = result['choices'][0]['message']['content']
            
        bot.reply_to(message, ai_answer)
        print("ШІ успішно надіслав справжню відповідь!")
        
    except Exception as e:
        print("Помилка ШІ: ", e)
        bot.reply_to(message, "🤖 Мережа ШІ на секунду перервалася. Напиши мені це повідомлення ще раз прямо зараз!")

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=f"{RENDER_EXTERNAL_URL}/{tg_token}")
    app.run(host="0.0.0.0", port=10000)
