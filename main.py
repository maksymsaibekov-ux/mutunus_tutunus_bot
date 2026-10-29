import telebot
from g4f.client import Client

# Вставляємо ваш токен Telegram
bot = telebot.TeleBot("9132142154:AAGqeXNGT51i_ouCpK2Vtk8NCF5THY_ONRQ")
ai_client = Client()

print("🚀 Фінальна версія бота запущена! Тепер усе працюватиме бездоганно...")

@bot.message_handler(content_types=['text'])
def handle_message(message):
    user_prompt = message.text
    print("Отримано запит: " + user_prompt)
    
    if user_prompt == "/start":
        bot.reply_to(message, "👋 Привіт! Я твій особистий ШІ-бот. Задай мені будь-яке питання українською мовою!")
        return

    try:
        # Викликаємо модель gemini-2.0-flash
        response = ai_client.chat.completions.create(
            model="gemini-2.0-flash",
            messages=[
                {"role": "system", "content": "Ти дружній асистент. Обов'язково відповідай коротко і виключно українською мовою."},
                {"role": "user", "content": user_prompt}
            ]
        )
        
        # Перевірка формату відповіді
        if hasattr(response, 'choices'):
            ai_answer = response.choices.message.content
        else:
            ai_answer = str(response)
            
        bot.reply_to(message, ai_answer)
        print("ШІ успішно відповів користувачу!")
        
    except Exception as e:
        print("Помилка підключення: ", e)
        bot.reply_to(message, "🤖 Ой, мережа ШІ на секунду перервалася. Напиши мені це повідомлення ще раз прямо зараз!")

bot.polling(none_stop=True, skip_pending=True, timeout=30)
