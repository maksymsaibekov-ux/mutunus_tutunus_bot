import telebot
from huggingface_hub import InferenceClient
import os
from flask import Flask, request

# 1. Зчитуємо ключі з налаштувань Render
tg_token = os.environ.get('TELEGRAM_TOKEN')
hf_token = os.environ.get('HF_TOKEN')

# 2. Назва вашого сервера на Render (береться автоматично)
RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL')

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
    return "Бот працює!", 200

@bot.message_handler(content_types=['text'])
def handle_message(message):
    user_prompt = message.text
    print("Отримано запит в Telegram: " + user_prompt)
    
    if user_prompt == "/start":
        bot.reply_to(message, "👋 Привіт! Я твій повністю автономний ШІ-бот. Задай мені питання українською мовою!")
        return

    try:
        # Використовуємо стабільну відкриту модель Llama 3.2
        response = client.chat.completions.create(
            model="Qwen/Qwen2.5-7B-Instruct",
            messages=[
                {"role": "system", "content": "Ти дружній асистент. Обов'язково відповідай коротко і виключно українською мовою."},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=300
        )
        
        ai_answer = response.choices.message.content
        bot.reply_to(message, ai_answer)
        
    except Exception as e:
        print("Помилка ШІ: ", e)
        bot.reply_to(message, "🤖 Мої віртуальні мізки трохи задумалися. Напиши ще раз!")

if __name__ == "__main__":
    # Налаштовуємо вебхук у Telegram
    bot.remove_webhook()
    bot.set_webhook(url=f"{RENDER_EXTERNAL_URL}/{tg_token}")
    
    # Запускаємо сервер на порті 10000, який вимагає Render
    app.run(host="0.0.0.0", port=10000)
