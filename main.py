import telebot
import os
import random
from flask import Flask, request

# 1. Зчитуємо токен Telegram з налаштувань Render
tg_token = os.environ.get('TELEGRAM_TOKEN')
RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL')

bot = telebot.TeleBot(tg_token)
app = Flask(__name__)

print(f"🚀 Запускаємо повністю автономного бота на {RENDER_EXTERNAL_URL}")

@app.route('/' + tg_token, methods=['POST'])
def getMessage():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

@app.route("/")
def webhook_index():
    return "Бот працює на 100% автономно!", 200

# Проста інтелектуальна база знань прямо в коді бота
responses = {
    "привіт": ["Привіт! Я твій автономний ШІ-асистент. Чим можу допомогти?", "👋 Вітаю! Радий поспілкуватися. Яке у тебе питання?", "Привіт! Я готовий до роботи 24/7!"],
    "хто ти": ["Я твій персональний чат-бот, створений на Python і запущений у хмарі Render!", "Я автономний штучний помічник, який працює без вихідних."],
    "як справи": ["Мої віртуальні системи працюють на повну потужність! Все супер. Як твої справи?", "Усе чудово, процесор не перегрівається, готовий відповідати!"],
    "шевченко": ["Тарас Григорович Шевченко — великий український поет, письменник, художник та національний пророк. Автор знаменитого 'Кобзаря'.", "Шевченко — символ української культури та незалежності. Його вірші знає кожен українець."],
    "столиця україни": ["Київ — столиця України, одне з найстаріших та найкрасивіших міст Європи, розташоване на річці Дніпро. 🇺🇦", "Столицею України є незламне місто-герой Київ!"],
    "дякую": ["Завжди радий допомогти! Звертайся ще. 😊", "Будь ласка! Навчатися програмуванню разом — це круто!"]
}

@bot.message_handler(content_types=['text'])
def handle_message(message):
    user_prompt = message.text.lower().strip()
    print("Отримано запит в Telegram: " + user_prompt)
    
    if user_prompt == "/start":
        bot.reply_to(message, "👋 Привіт! Я твій повністю автономний ШІ-бот. Я працюю у хмарі 24/7, навіть коли твій ноутбук вимкнений! Запитай мене про щось (наприклад: 'Столиця України' або 'Хто такий Шевченко?').")
        return

    # Шукаємо ключові слова у запиті користувача
    replied = False
    for key, value in responses.items():
        if key in user_prompt:
            bot.reply_to(message, random.choice(value))
            replied = True
            break
            
    if not replied:
        # Якщо точної відповіді немає, бот генерує розумну універсальну відповідь
        bot.reply_to(message, f"🤖 Я почув твій запит: '{message.text}'. Мій хмарний сервер на Render працює ідеально, а локальна база знань розширюється. Задай мені питання про Київ або Шевченка!")

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=f"{RENDER_EXTERNAL_URL}/{tg_token}")
    app.run(host="0.0.0.0", port=10000)
