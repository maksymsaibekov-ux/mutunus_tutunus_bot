import telebot
from huggingface_hub import InferenceClient
import os
import threading
from http.server import SimpleHTTPRequestHandler, HTTPServer

# 1. Безпечно зчитуємо токен Telegram та ключ ШІ з налаштувань Render
tg_token = os.environ.get('TELEGRAM_TOKEN')
hf_token = os.environ.get('HF_TOKEN')

# 2. Ініціалізуємо офіційних клієнтів
bot = telebot.TeleBot(tg_token)
client = InferenceClient(api_key=hf_token)

print("🚀 Офіційний автономний ШІ-бот успішно запущений на Render!")

@bot.message_handler(content_types=['text'])
def handle_message(message):
    user_prompt = message.text
    print("Отримано запит в Telegram: " + user_prompt)
    
    if user_prompt == "/start":
        bot.reply_to(message, "👋 Привіт! Я твій особистісний автономний ШІ-бот. Задай мені будь-яке питання українською мовою!")
        return

    try:
        # Використовуємо офіційну відкриту модель Llama 3.2, яка працює легально через ваш ключ
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.2-3B-Instruct",
            messages=[
                {"role": "system", "content": "Ти дружній асистент. Обов'язково відповідай коротко і виключно українською мовою."},
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
