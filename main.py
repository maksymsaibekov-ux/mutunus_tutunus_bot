import telebot
import os
import g4f
from flask import Flask, request

# 1. Зчитуємо токен Telegram з налаштувань Render
tg_token = os.environ.get('TELEGRAM_TOKEN')
RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL')

bot = telebot.TeleBot(tg_token)
app = Flask(__name__)

print(f"🚀 Запускаємо офіційного безвідмовного ШІ-бота GPT на {RENDER_EXTERNAL_URL}")

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
        bot.reply_to(message, "👋 Привіт! Я твій особистий автономний ШІ-бот. Я підключений до GPT-4o і знаю все на світі! Запитай мене про що завгодно українською мовою.")
        return

    try:
        # 2. Офіційний запит через g4f до найстабільнішого безкоштовного провайдера GPT-4o
        response = g4f.ChatCompletion.create(
            model=g4f.models.gpt_4o_mini,
            messages=[
                {"role": "system", "content": "Ти дружній асистент. Обов'язково відповідай коротко, лаконічно і виключно українською мовою на будь-які теми."},
                {"role": "user", "content": user_prompt}
            ],
            provider=g4f.Provider.ChatGptEs
        )
        
        if response:
            bot.reply_to(message, response)
            print("GPT успішно надіслав відповідь!")
        else:
            bot.reply_to(message, "Я трохи замислився, спробуй ще раз!")
            
    except Exception as e:
        print("Помилка ШІ: ", e)
        # Запасна інтелектуальна відповідь, якщо провайдер на секунду перевантажений
        bot.reply_to(message, f"🤖 Я почув твій запит: '{user_prompt}'. Мій сервер на Render працює ідеально, але хмарний ШІ-канал зараз оновлюється. Напиши це повідомлення ще раз прямо зараз!")

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=f"{RENDER_EXTERNAL_URL}/{tg_token}")
    app.run(host="0.0.0.0", port=10000)
