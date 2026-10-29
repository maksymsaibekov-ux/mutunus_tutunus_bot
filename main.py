import telebot
import os
import difflib
from flask import Flask, request

# 1. Зчитуємо токен Telegram з налаштувань Render
tg_token = os.environ.get('TELEGRAM_TOKEN')
RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL')

bot = telebot.TeleBot(tg_token)
app = Flask(__name__)

print(f"🚀 Запускаємо автономного інтелектуального бота на {RENDER_EXTERNAL_URL}")

@app.route('/' + tg_token, methods=['POST'])
def getMessage():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

@app.route("/")
def webhook_index():
    return "Бот працює на 100% автономно!", 200

# Розширена інтелектуальна база знань прямо всередині пам'яті сервера
knowledge_base = {
    "привіт": "Привіт! Я твій повністю автономний ШІ-асистент на Render. Готовий відповідати 24/7! 👋",
    "хто ти": "Я твій хмарний чат-бот, створений на Python. Я вмію працювати цілодобово, навіть коли твій ноутбук вимкнений! 🤖",
    "як справи": "Мої віртуальні системи працюють ідеально! Процесор не перегрівається і готовий до роботи. 💻",
    "шевченко": "Тарас Григорович Шевченко — великий український поет, видатний художник та національний пророк. Автор знаменитої збірки віршів 'Кобзар', яка стала символом української культури та незалежності. 🇺🇦",
    "столиця україни": "Столицею України є незламне місто-герой Київ! Це одне з найдавніших та найкрасивіших міст Європи, розташоване на річці Дніпро. 🏛️",
    "дякую": "Завжди радий допомогти! Навчатися програмуванню та створювати власні хмарні проекти разом — це круто! 😊",
    "максим сайбеков": "Максим Сайбеков — талановитий український розробник-початківець, який успішно пройшов квест розгортання клієнт-серверного ШІ-додатка у хмарі Render! 🏆"
}

@bot.message_handler(content_types=['text'])
def handle_message(message):
    user_prompt = message.text.lower().strip()
    print("Отримано запит в Telegram: " + user_prompt)
    
    if user_prompt == "/start":
        bot.reply_to(message, "👋 Привіт! Я твій повністю автономний ШІ-бот. Я працюю у хмарі 24/7, навіть коли твій ноутбук вимкнений! Запитай мене про що завгодно (наприклад: 'Хто такий Шевченко?' або 'Яка столиця України?').")
        return

    # Розумний пошук найближчого за змістом запитання в нашій базі знань
    keys = list(knowledge_base.keys())
    
    # Шукаємо збіги за допомогою алгоритму difflib (знаходить слова, навіть якщо дописані цифри на кшталт 15:44)
    matches = difflib.get_close_matches(user_prompt, keys, n=1, cutoff=0.3)
    
    # Також перевіряємо, чи є ключове слово просто частиною довгого речення
    partial_match = None
    for key in keys:
        if key in user_prompt:
            partial_match = key
            break

    if matches:
        matched_key = matches[0]
        bot.reply_to(message, knowledge_base[matched_key])
        print(f"Інтелектуальна відповідь знайдена для ключа: {matched_key}")
    elif partial_match:
        bot.reply_to(message, knowledge_base[partial_match])
        print(f"Частковий збіг знайдено для ключа: {partial_match}")
    else:
        # Універсальна відповідь, яка підставляє текст користувача, якщо тема абсолютно нова
        bot.reply_to(message, f"🤖 Я почув твій запит: '{message.text}'. Мій хмарний сервер на Render працює бездоганно. Зараз я розширюю свою локальну базу знань. Задай мені питання про Шевченка, Київ або Максима Сайбекова!")

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=f"{RENDER_EXTERNAL_URL}/{tg_token}")
    app.run(host="0.0.0.0", port=10000)
