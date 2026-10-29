import telebot
from google import genai
import os
from flask import Flask, request

# 1. Считываем ключи из настроек Render
tg_token = os.environ.get('TELEGRAM_TOKEN')
google_key = os.environ.get('GEMINI_API_KEY')
RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL')

# 2. Инициализируем официальных клиентов
bot = telebot.TeleBot(tg_token)
ai_client = genai.Client(api_key=google_key)
app = Flask(__name__)

print(f"🚀 Запускаем умного официального бота на {RENDER_EXTERNAL_URL}")

@app.route('/' + tg_token, methods=['POST'])
def getMessage():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

@app.route("/")
def webhook_index():
    return "Бот работает стабильно с Gemini 1.5!", 200

@bot.message_handler(content_types=['text'])
def handle_message(message):
    user_prompt = message.text
    print("Отримано запит в Telegram: " + user_prompt)
    
    if user_prompt.lower().strip() == "/start":
        bot.reply_to(message, "👋 Привіт! Я твій офіційний всезнаючий ШІ-бот на базі Google Gemini 1.5. Запитай мене про що завгодно українською мовою!")
        return

    try:
        # Используем суперстабильную модель Gemini 1.5 Flash с огромными лимитами
        response = ai_client.models.generate_content(
            model='gemini-1.5-flash', 
            contents=f"Ти дружній та дуже розумний асистент. Дай відповідь обов'язково українською мовою: {user_prompt}",
        )
        
        if response.text:
            bot.reply_to(message, response.text)
            print("Gemini успешно ответил!")
        else:
            bot.reply_to(message, "ШІ задумався. Спробуй ще раз!")
            
    except Exception as e:
        print("Помилка Gemini API: ", e)
        bot.reply_to(message, "🤖 Ой, хмарна нейромережа зараз оновлюється. Напиши мені це повідомлення ще раз прямо зараз!")

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=f"{RENDER_EXTERNAL_URL}/{tg_token}")
    app.run(host="0.0.0.0", port=10000)
