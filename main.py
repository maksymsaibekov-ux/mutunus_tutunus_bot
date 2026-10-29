import telebot
from g4f.client import Client
import threading
from http.server import SimpleHTTPRequestHandler, HTTPServer

# 1. Налаштовуємо ваш токен Telegram
bot = telebot.TeleBot("9132142154:AAFTPiSnZuS_TY0NOXi8CkEqj5283lPu22Y")
ai_client = Client()

print("🚀 Фінальний автономний ШІ-бот успішно запущений на Render!")

@bot.message_handler(content_types=['text'])
def handle_message(message):
    user_prompt = message.text
    print("Отримано запит в Telegram: " + user_prompt)
    
    if user_prompt == "/start":
        bot.reply_to(message, "👋 Привіт! Я твій особистий автономний ШІ-бот. Задай мені будь-яке питання українською мовою!")
        return

    try:
        # Викликаємо стабільну безкоштовну модель Yi-34B
        response = ai_client.chat.completions.create(
            model="yi-34b",
            messages=[
                {"role": "system", "content": "Ти дружній асистент. Обов'язково відповідай коротко і виключно українською мовою."},
                {"role": "user", "content": user_prompt}
            ]
        )
        
        # Перевіряємо формат відповіді та дістаємо чистий текст
        if hasattr(response, 'choices'):
            ai_answer = response.choices.message.content
        else:
            ai_answer = str(response)
            
        bot.reply_to(message, ai_answer)
        print("ШІ успішно відповів користувачу!")
        
    except Exception as e:
        print("Помилка підключення до ШІ: ", e)
        bot.reply_to(message, "🤖 Ой, мережа ШІ на секунду перервалася. Напиши мені це повідомлення ще раз прямо зараз!")

# -------------------------------------------------------------
# ХИТРІСТЬ ДЛЯ RENDER: утримуємо порт 10000 відкритим
def run_fake_server():
    server_address = ('0.0.0.0', 10000)
    httpd = HTTPServer(server_address, SimpleHTTPRequestHandler)
    httpd.serve_forever()

threading.Thread(target=run_fake_server, daemon=True).start()
# -------------------------------------------------------------

bot.polling(none_stop=True, skip_pending=True, timeout=30)
