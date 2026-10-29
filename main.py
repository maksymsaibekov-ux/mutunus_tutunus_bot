import telebot
from huggingface_hub import InferenceClient
import os
from flask import Flask, request

# 1. Зчитуємо ключі з налаштувань Render
tg_token = os.environ.get('TELEGRAM_TOKEN')
hf_token = os.environ.get('HF_TOKEN')
RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL')

# 2. Ініціалізуємо офіційних клієнтів
bot = telebot.TeleBot(tg_token)
client = InferenceClient(api_key=hf_token)
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
        bot.reply_to(message, "👋 Привіт! Я твій особистий автономний ШІ-бот. Задай мені будь-яке питання українською мовою!")
        return

    try:
        # Використовуємо суперстабільну модель від Microsoft
        response = client.chat.completions.create(
            model="microsoft/Phi-3-mini-4k-instruct",
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

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=f"{RENDER_EXTERNAL_URL}/{tg_token}")
    app.run(host="0.0.0.0", port=10000)
