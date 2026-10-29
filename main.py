import telebot
import os
import urllib.request
import json
from flask import Flask, request

# 1. Безпечно зчитуємо токен Telegram та безкоштовний ключ Groq ШІ
tg_token = os.environ.get('TELEGRAM_TOKEN')
groq_key = os.environ.get('GROQ_API_KEY')
RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL')

bot = telebot.TeleBot(tg_token)
app = Flask(__name__)

print(f"🚀 Запускаємо офіційного ШІ-бота Groq на {RENDER_EXTERNAL_URL}")

@app.route('/' + tg_token, methods=['POST'])
def getMessage():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

@app.route("/")
def webhook_index():
    return "Надшвидкий ШІ-сервер працює!", 200

@bot.message_handler(content_types=['text'])
def handle_message(message):
    user_prompt = message.text
    print("Отримано запит в Telegram: " + user_prompt)
    
    if user_prompt.lower().strip() == "/start":
        bot.reply_to(message, "👋 Привіт! Я твій офіційний автономний ШІ-бот на базі моделі Llama 3.1 від Groq. Я знаю абсолютно все на світі! Запитай мене про що завгодно українською мовою!")
        return

    try:
        # 2. Прямий швидкий HTTP-запит до офіційного безкоштовного API Groq
        url = "https://groq.com"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {groq_key}"
        }
        data = {
            "model": "llama-3.1-8b-instant",
            "messages": [
                {"role": "system", "content": "Ти дружній та дуже розумний асистент. Обов'язково відповідай виключно українською мовою, коротко і чітко на будь-які запитання користувача."},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.7
        }
        
        req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers)
        
        with urllib.request.urlopen(req, timeout=15) as response:
            result = json.loads(response.read().decode('utf-8'))
            ai_answer = result['choices'][0]['message']['content']
            
        bot.reply_to(message, ai_answer)
        print("Groq ШІ успішно надіслав відповідь користувачу!")
        
    except Exception as e:
        print("Помилка Groq API: ", e)
        bot.reply_to(message, "🤖 Мої віртуальні мізки зараз обробляють занадто багато інформації. Надішли це повідомлення ще раз через 5 секунд!")

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=f"{RENDER_EXTERNAL_URL}/{tg_token}")
    app.run(host="0.0.0.0", port=10000)
