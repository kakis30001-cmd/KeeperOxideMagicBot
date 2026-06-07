@bot.message_handler(commands=['start'])
def cmd_start(message):
    print("=" * 30)
    print(f"ПРИШЛА КОМАНДА /START ОТ {message.from_user.id}")
    
    try:
        bot.send_message(message.chat.id, "🛠 Тест связи! Если ты это видишь, значит отправка сообщений работает.")
        print("СООБЩЕНИЕ УСПЕШНО ОТПРАВЛЕНО В ТЕЛЕГРАМ!")
    except Exception as e:
        print(f"ОШИБКА ОТПРАВКИ: {e}")
        
    print("=" * 30)
