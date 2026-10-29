import telebot
from google import genai
import os
from flask import Flask, request

# 1. Безпечно зчитуємо токен Telegram та свіжий ключ Gemini з налаштувань Render
tg_token = os.environ.get('TELEGRAM_TOKEN')
google_key = os.environ.get('GEMINI_API_KEY')
RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL')

# 2. Ініціалізуємо офіційних хмарних клієнтів
bot = telebot.TeleBot(tg_token)
ai_client = genai.Client(api_key=google_key)
app = Flask(__name__)

print(f"🚀 Запускаємо розумного автономного ШІ-бота на {RENDER_EXTERNAL_URL}")

@app.route('/' + tg_token, methods=['POST'])
def getMessage():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

@app.route("/")
def webhook_index():
    return "Бот працює і думає мізками Gemini 1.5!", 200

@bot.message_handler(content_types=['text'])
def handle_message(message):
    user_prompt = message.text
    print("Отримано запит в Telegram: " + user_prompt)
    
    if user_prompt.lower().strip() == "/start":
        bot.reply_to(message, "👋 Привіт! Я твій офіційний автономний ШІ-бот на базі Google Gemini 1.5. Я знаю геть усе на світі! Запитай мене про що завгодно українською мовою!")
        return

    try:
        # Викликаємо суперстабільну модель Gemini 1.5 Flash з великими безкоштовними лімітами
        response = ai_client.models.generate_content(
            model='gemini-1.5-flash', 
            contents=f"Ти дружній та дуже розумний асистент. Дай відповідь обов'язково українською мовою, коротко і лаконічно: {user_prompt}",
        )
        
        if response.text:
            bot.reply_to(message, response.text)
            print("Gemini успішно надіслав ШІ-відповідь!")
        else:
            bot.reply_to(message, "Я трохи замислився, спробуй перефразувати питання!")
            
    except Exception as e:
        print("Помилка Gemini API: ", e)
        bot.reply_to(message, "🤖 Мої віртуальні мізки зараз перевантажені. Напиши мені це повідомлення ще раз прямо зараз!")

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=f"{RENDER_EXTERNAL_URL}/{tg_token}")
    app.run(host="0.0.0.0", port=10000)
