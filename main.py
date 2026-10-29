import telebot
from google import genai
import os
import threading
from http.server import SimpleHTTPRequestHandler, HTTPServer

# 1. Зчитуємо ключ Gemini з налаштувань сервера Render
google_key = os.environ.get('GEMINI_API_KEY')

# 2. Налаштовуємо клієнтів
bot = telebot.TeleBot("9132142154:AAGqeXNGT51i_ouCpK2Vtk8NCF5THY_ONRQ")
ai_client = genai.Client(api_key=google_key)

print("🚀 Офіційний Бот Gemini успішно запущений на Render!")

@bot.message_handler(content_types=['text'])
def handle_message(message):
    user_prompt = message.text
    print("Отримано запит: " + user_prompt)
    
    if user_prompt == "/start":
        bot.reply_to(message, "👋 Привіт! Я твій офіційний безкоштовний бот на базі Google Gemini. Запитай мене про що завгодно українською!")
        return

    try:
        # Використовуємо стабільну офіційну модель Gemini 2.0
        response = ai_client.models.generate_content(
            model='gemini-2.0-flash', 
            contents=f"Ти дружній асистент. Дай відповідь обов'язково українською мовою: {user_prompt}",
        )
        
        if response.text:
            bot.reply_to(message, response.text)
            print("Gemini успішно відповів!")
        else:
            bot.reply_to(message, "ШІ задумався. Спробуй ще раз!")
            
    except Exception as e:
        print("Помилка Gemini API: ", e)
        bot.reply_to(message, "🤖 Ой, сервери Google зараз дуже завантажені. Напиши мені це повідомлення ще раз прямо зараз!")

# Фейковий веб-сервер для утримання Render у режимі Live
def run_fake_server():
    server_address = ('0.0.0.0', 10000)
    httpd = HTTPServer(server_address, SimpleHTTPRequestHandler)
    httpd.serve_forever()

threading.Thread(target=run_fake_server, daemon=True).start()

bot.polling(none_stop=True, skip_pending=True, timeout=30)
