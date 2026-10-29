import telebot
from huggingface_hub import InferenceClient
import os
import threading
from http.server import SimpleHTTPRequestHandler, HTTPServer

# 1. Считываем безкоштовний ключ ШІ з налаштувань сервера Render
hf_token = os.environ.get('HF_TOKEN')

# 2. Налаштовуємо клієнтів (Вставте ваш НОВИЙ токен Telegram всередину лапок)
bot = telebot.TeleBot("9132142154:AAFTPiSnZuS_TY0NOXi8CkEqj5283lPu22Y")
client = InferenceClient(api_key=hf_token)

print("🚀 Стабільний автономний ШІ-бот успішно запущений на Render!")

@bot.message_handler(content_types=['text'])
def handle_message(message):
    user_prompt = message.text
    print("Отримано запит в Telegram: " + user_prompt)
    
    if user_prompt == "/start":
        bot.reply_to(message, "👋 Привіт! Я твій особистий автономний ШІ-бот. Задай мені будь-яке питання українською мовою!")
        return

    try:
        # Використовуємо стабільну відкриту модель Qwen 2.5
        response = client.chat.completions.create(
            model="Qwen/Qwen2.5-7B-Instruct",
            messages=[
                {"role": "system", "content": "Ти дружній та розумний асистент. Обов'язково відповідай коротко і виключно українською мовою."},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=300
        )
        
        ai_answer = response.choices.message.content
        bot.reply_to(message, ai_answer)
        print("ШІ успішно відповів солов'їною!")
        
    except Exception as e:
        print("Помилка сервера ШІ: ", e)
        bot.reply_to(message, "🤖 Мої віртуальні мізки трохи задумалися. Напиши мені це повідомлення ще раз прямо зараз!")

# Фейковий веб-сервер для утримання Render у режимі Live
def run_fake_server():
    server_address = ('0.0.0.0', 10000)
    httpd = HTTPServer(server_address, SimpleHTTPRequestHandler)
    httpd.serve_forever()

threading.Thread(target=run_fake_server, daemon=True).start()

bot.polling(none_stop=True, skip_pending=True, timeout=30)
