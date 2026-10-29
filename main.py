import telebot
from g4f.client import Client
import threading
from http.server import SimpleHTTPRequestHandler, HTTPServer

# 1. Вставляємо ваш токен Telegram
bot = telebot.TeleBot("9132142154:AAGqeXNGT51i_ouCpK2Vtk8NCF5THY_ONRQ")
ai_client = Client()

print("🚀 Фінальна версія бота запущена на сервері Render!")

@bot.message_handler(content_types=['text'])
def handle_message(message):
    user_prompt = message.text
    print("Отримано запит: " + user_prompt)
    
    if user_prompt == "/start":
        bot.reply_to(message, "👋 Привіт! Я твій особистий ШІ-бот. Задай мені будь-яке питання українською мовою!")
        return

    try:
        response = ai_client.chat.completions.create(
            model="gemini-2.0-flash",
            messages=[
                {"role": "system", "content": "Ти дружній асистент. Обов'язково відповідай коротко і виключно українською мовою."},
                {"role": "user", "content": user_prompt}
            ]
        )
        
        if hasattr(response, 'choices'):
            ai_answer = response.choices.message.content
        else:
            ai_answer = str(response)
            
        bot.reply_to(message, ai_answer)
        print("ШІ успішно відповів користувачу!")
        
    except Exception as e:
        print("Помилка підключення: ", e)
        bot.reply_to(message, "🤖 Ой, мережа ШІ на секунду перервалася. Напиши мені це повідомлення ще раз прямо зараз!")

# -------------------------------------------------------------
# ХИТРІСТЬ ДЛЯ RENDER: створюємо фейковий веб-сервер на порті 10000
def run_fake_server():
    server_address = ('0.0.0.0', 10000)
    httpd = HTTPServer(server_address, SimpleHTTPRequestHandler)
    print("Фейковий веб-сервер для Render запущено на порті 10000")
    httpd.serve_forever()

# Запускаємо фейковий сервер в окремому потоці, щоб він не заважав боту
threading.Thread(target=run_fake_server, daemon=True).start()
# -------------------------------------------------------------

bot.polling(none_stop=True, skip_pending=True, timeout=30)
