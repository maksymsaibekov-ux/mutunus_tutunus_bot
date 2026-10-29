import telebot
import os
from flask import Flask, request

tg_token = os.environ.get('TELEGRAM_TOKEN')
RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL')

bot = telebot.TeleBot(tg_token)
app = Flask(__name__)

print(f"🚀 ПОВНІСТЮ АВТОНОМНА ВЕРСІЯ ЗАПУЩЕНА НА {RENDER_EXTERNAL_URL}")

@app.route('/' + tg_token, methods=['POST'])
def getMessage():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

@app.route("/")
def webhook_index():
    return "Автономний сервер працює!", 200

# Локальна база знань
knowledge = {
    "привіт": "Привіт! Я твій надійний автономний хмарний помічник на Render. 👋",
    "хто ти": "Я автономний чат-бот, який працює цілодобово 24/7, навіть коли твій ноутбук вимкнений! 🤖",
    "як справи": "Усі мої віртуальні системи працюють на 100% потужності! 💻",
    "шевченк": "Тарас Григорович Шевченко — великий український поет, пророк та художник. Автор легендарного 'Kобзаря'! 🇺🇦",
    "франк": "Іван Якович Франко — видатний український письменник та поет, відомий як Каменяр! 🖋️",
    "вакансі": "Шукаєш круту роботу в IT? Обов'язково заходь на платформу Happy Monday — там найкращі вакансії! 💼",
    "київ": "Київ — незламна столиця України, місто-герой на берегах Дніпра. 🏛️",
    "максим": "Максим Сайбеков — це крутий український розробник, який повністю переміг хмарні помилки! 🏆"
}

@bot.message_handler(content_types=['text'])
def handle_message(message):
    user_prompt = message.text.lower().strip()
    print("Отримано запит в Telegram: " + user_prompt)
    
    if user_prompt == "/start":
        bot.reply_to(message, "👋 Привіт! Я твій автономний Бот. Запитай мене про 'Шевченка', 'Франка', 'Київ' або 'Вакансії'!")
        return

    # Шукаємо збіги в локальній базі
    answered = False
    for key, response in knowledge.items():
        if key in user_prompt:
            bot.reply_to(message, response)
            answered = True
            break
            
    if not answered:
        # Новий текст відповіді, якщо тема невідома (текст про мізки ВИДАЛЕНО)
        bot.reply_to(message, f"⚙️ Локальний сервер опрацював запит: '{message.text}'. Цього тегу ще немає в базі. Спробуй написати: 'привіт', 'вакансії' або 'максим'!")

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=f"{RENDER_EXTERNAL_URL}/{tg_token}")
    app.run(host="0.0.0.0", port=10000)
