import telebot
import os
import urllib.request
import json
import urllib.parse
from flask import Flask, request

# 1. Зчитуємо токен Telegram з налаштувань Render
tg_token = os.environ.get('TELEGRAM_TOKEN')
RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL')

bot = telebot.TeleBot(tg_token)
app = Flask(__name__)

print(f"🚀 Запускаємо бота в режимі Webhook на {RENDER_EXTERNAL_URL}")

@app.route('/' + tg_token, methods=['POST'])
def getMessage():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

@app.route("/")
def webhook_index():
    return "Бот працює стабільно!", 200

@bot.message_handler(content_types=['text'])
def handle_message(message):
    user_prompt = message.text
    print("Отримано запит в Telegram: " + user_prompt)
    
    if user_prompt == "/start":
        bot.reply_to(message, "👋 Привіт! Я твій повністю автономний ШІ-бот. Задай мені будь-яке питання українською мовою!")
        return

    try:
        # Використовуємо стабільний безкоштовний ШІ-сервер без ключів доступу
        api_url = f"https://open-api.bot{urllib.parse.quote(user_prompt)}&lang=uk"
        req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
        
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            ai_answer = data.get("response", "Я трохи замислився, спробуй ще раз!")
            
        bot.reply_to(message, ai_answer)
        print("ШІ успішно відповів!")
        
    except Exception as e:
        print("Помилка підключення до ШІ: ", e)
        bot.reply_to(message, "🤖 Мої віртуальні мізки зараз відпочивають. Напиши мені ще раз прямо зараз!")

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=f"{RENDER_EXTERNAL_URL}/{tg_token}")
    app.run(host="0.0.0.0", port=10000)
