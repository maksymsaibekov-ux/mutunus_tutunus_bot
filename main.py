import telebot
import os
import urllib.request
import json
from flask import Flask, request

# 1. Считываем токен Telegram из настроек Render
tg_token = os.environ.get('TELEGRAM_TOKEN')
RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL')

bot = telebot.TeleBot(tg_token)
app = Flask(__name__)

print(f"🚀 Запускаем безлимитного ШІ-бота GPT-4o на {RENDER_EXTERNAL_URL}")

@app.route('/' + tg_token, methods=['POST'])
def getMessage():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

@app.route("/")
def webhook_index():
    return "Стабильный ШІ-сервер работает без ограничений!", 200

@bot.message_handler(content_types=['text'])
def handle_message(message):
    user_prompt = message.text
    print("Отримано запит в Telegram: " + user_prompt)
    
    if user_prompt.lower().strip() == "/start":
        bot.reply_to(message, "👋 Привіт! Я твій повністю автономний ШІ-бот на базі GPT-4o-Mini. Я знаю абсолютно все на світі! Запитай мене про що завгодно українською мовою!")
        return

    try:
        # 2. Прямой легальный запрос к бесплатному безлимитному шлюзу Pollinations AI (модель OpenAI)
        url = "https://pollinations.ai"
        headers = {"Content-Type": "application/json"}
        data = {
            "messages": [
                {"role": "system", "content": "Ти дружній та дуже розумний асистент. Обов'язково відповідай виключно українською мовою, коротко і чітко на будь-які запитання користувача."},
                {"role": "user", "content": user_prompt}
            ],
            "model": "openai",
            "json": False
        }
        
        req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers)
        
        with urllib.request.urlopen(req, timeout=20) as response:
            ai_answer = response.read().decode('utf-8')
            
        if ai_answer and "error" not in ai_answer.lower():
            bot.reply_to(message, ai_answer)
            print("ШІ успешно прислал полноценный ответ!")
        else:
            bot.reply_to(message, "🤖 Моя сеть ИИ на секунду задумалась. Напиши это сообщение еще раз прямо сейчас!")
            
    except Exception as e:
        print("Помилка ШІ: ", e)
        bot.reply_to(message, "🤖 Моя сеть ИИ на секунду задумалась. Напиши это сообщение еще раз прямо сейчас!")

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=f"{RENDER_EXTERNAL_URL}/{tg_token}")
    app.run(host="0.0.0.0", port=10000)
