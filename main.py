import telebot
from google import genai
import os
from flask import Flask, request

# 1. Пропишіть ваші оригінальні ключі сюди
TG_TOKEN = "9132142154:AAFMSSlbyCTvyndZ4ujKWu_I_h97WOl3tU0"
GEMINI_KEY = "ВСТАВТЕ_ВАШ_КЛЮЧ_AIzaSy_ВІД_GOOGLE_AI_STUDIO"

bot = telebot.TeleBot(TG_TOKEN)
ai_client = genai.Client(api_key=GEMINI_KEY)
app = Flask(__name__)

print("🚀 Розумний ШІ-бот офіційно запущений на серверах Google Cloud!")

@app.route('/', methods=['POST', 'GET'])
def webhook():
    if request.method == 'POST':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "!", 200
    return "Google ШІ-сервер працює!", 200

@bot.message_handler(content_types=['text'])
def handle_message(message):
    user_prompt = message.text
    print("Запит від користувача: " + user_prompt)
    
    if user_prompt.lower().strip() == "/start":
        bot.reply_to(message, "👋 Привіт! Я твій автономний ШІ-бот, який працює на серверах Google Cloud. Запитай мене про що завгодно!")
        return

    try:
        # Викликаємо оригінальну модель Gemini, яка на серверах Google літає миттєво
        response = ai_client.models.generate_content(
            model='gemini-1.5-flash', 
            contents=f"Ти дружній асистент. Дай відповідь обов'язково українською мовою, чітко і коротко: {user_prompt}",
        )
        
        if response.text:
            bot.reply_to(message, response.text)
        else:
            bot.reply_to(message, "Я задумався, спробуй ще раз!")
            
    except Exception as e:
        print("Помилка: ", e)
        bot.reply_to(message, "🤖 Помилка з'єднання з ШІ. Спробуй надіслати запит ще раз!")

# Telegram Webhook налаштується автоматично через сервери Google
if __name__ == "__main__":
    # Сервер Google сам підставить потрібний порт
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
