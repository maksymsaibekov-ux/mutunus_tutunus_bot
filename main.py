import telebot
import os
import urllib.request
import json
import urllib.parse
from flask import Flask, request

tg_token = os.environ.get('TELEGRAM_TOKEN')
RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL')

bot = telebot.TeleBot(tg_token)
app = Flask(__name__)

print(f"🚀 Запускаем умного энциклопедического Бот-ШИ на {RENDER_EXTERNAL_URL}")

@app.route('/' + tg_token, methods=['POST'])
def getMessage():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

@app.route("/")
def webhook_index():
    return "Энциклопедический ШІ-сервер работает стабильно!", 200

@bot.message_handler(content_types=['text'])
def handle_message(message):
    user_prompt = message.text.strip()
    print("Отримано запит в Telegram: " + user_prompt)
    
    if user_prompt.lower() == "/start":
        bot.reply_to(message, "👋 Привіт! Я твій всезнаючий автономний Бот-ШІ. Я підключений до глобальної бази знань і можу знайти інформацію про що завгодно! Просто напиши мені слово або термін українською мовою.")
        return

    try:
        # Прямой легальный запрос к украинской Википедии через официальное API (без ключей и блокировок)
        search_query = urllib.parse.quote(user_prompt)
        wiki_url = f"https://wikipedia.org{search_query}&redirects=1"
        
        req = urllib.request.Request(wiki_url, headers={'User-Agent': 'Mozilla/5.0'})
        
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode('utf-8'))
            pages = data.get("query", {}).get("pages", {})
            
            page_id = list(pages.keys())[0]
            if page_id != "-1":
                ai_answer = pages[page_id].get("extract", "")
                # Ограничиваем длину ответа для удобства чтения в Telegram
                if len(ai_answer) > 600:
                    ai_answer = ai_answer[:600] + "..."
            else:
                ai_answer = f"🤖 Я обшукав усю глобальну базу знань, але точної статті за запитом '{user_prompt}' не знайдено. Спробуй написати назву міста, історичної постаті чи терміну більш точно (наприклад: 'Київ', 'Шевченко', 'Програмування')."
                
        bot.reply_to(message, ai_answer)
        print("База знань успішно надіслала відповідь!")
        
    except Exception as e:
        print("Помилка бази знань: ", e)
        bot.reply_to(message, "🤖 Моя мережа знань на секунду задумалася. Напиши це повідомлення ще раз прямо зараз!")

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=f"{RENDER_EXTERNAL_URL}/{tg_token}")
    app.run(host="0.0.0.0", port=10000)
