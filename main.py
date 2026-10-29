import telebot
import os
import urllib.request
import urllib.parse
from flask import Flask, request

tg_token = os.environ.get('TELEGRAM_TOKEN')
RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL')

bot = telebot.TeleBot(tg_token)
app = Flask(__name__)

print(f"🚀 Запускаємо фінального безвідмовного ШІ-бота на {RENDER_EXTERNAL_URL}")

@app.route('/' + tg_token, methods=['POST'])
def getMessage():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

@app.route("/")
def webhook_index():
    return "Безвідмовний ШІ-сервер працює!", 200

@bot.message_handler(content_types=['text'])
def handle_message(message):
    user_prompt = message.text.strip()
    print("Отримано запит в Telegram: " + user_prompt)
    
    if user_prompt.lower() == "/start":
        bot.reply_to(message, "👋 Привіт! Я твій всезнаючий автономний ШІ-бот. Я знаю абсолютно все на світі! Запитай мене про що завгодно українською мовою.")
        return

    try:
        # Прямой текстовый запрос к безотказному ИИ-провайдеру (модель openai)
        # Этот шлюз возвращает чистый текст БЕЗ JSON, поэтому здесь технически нечему ломаться
        system_rules = urllib.parse.quote("Ти дружній асистент. Обов'язково відповідай коротко і виключно українською мовою. Запит: ")
        encoded_prompt = urllib.parse.quote(user_prompt)
        
        ai_url = f"https://pollinations.ai{system_rules}{encoded_prompt}?model=openai&cache=false"
        req = urllib.request.Request(ai_url, headers={'User-Agent': 'Mozilla/5.0'})
        
        with urllib.request.urlopen(req, timeout=20) as response:
            ai_answer = response.read().decode('utf-8').strip()
            
        if ai_answer:
            bot.reply_to(message, ai_answer)
            print("ШІ успішно надіслав відповідь!")
        else:
            bot.reply_to(message, "🤖 Мої мізки замислилися. Напиши це повідомлення ще раз!")
            
    except Exception as e:
        print("Помилка ШІ-сервера: ", e)
        bot.reply_to(message, "🤖 На секунду зник зв'язок із ШІ. Надішли це повідомлення ще раз прямо зараз!")

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=f"{RENDER_EXTERNAL_URL}/{tg_token}")
    app.run(host="0.0.0.0", port=10000)
