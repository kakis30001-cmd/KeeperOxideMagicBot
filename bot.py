import os
import sqlite3
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from flask import Flask, request

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# Инициализация базы данных SQLite
def init_sqlite():
    conn = sqlite3.connect('shop.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                      (user_id INTEGER PRIMARY KEY, balance INTEGER DEFAULT 0)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS products 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, price INTEGER)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS promos 
                      (code TEXT PRIMARY KEY, discount INTEGER)''')
    conn.commit()
    return conn

db_conn = init_sqlite()

# Хранилище состояний (FSM)
user_states = {}

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def get_user(user_id):
    cursor = db_conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    db_conn.commit()
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    return cursor.fetchone()[0]

# --- КЛАВИАТУРЫ ---
def main_markup():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🏪 Магазин", "👤 Профиль")
    return markup

# --- ОБРАБОТЧИКИ ---
@bot.message_handler(commands=['start'])
def start(message):
    get_user(message.from_user.id) # Регистрация в БД
    bot.send_message(message.chat.id, "Добро пожаловать!\n\nБот для продажи подписок LITE и VIP.\nОплата через Platega.", reply_markup=main_markup())

@bot.message_handler(func=lambda message: message.text == "👤 Профиль")
def profile(message):
    balance = get_user(message.from_user.id)
    text = (f"👤 Профиль: {message.from_user.first_name}\n"
            f"🆔 ID: <code>{message.from_user.id}</code>\n"
            f"💰 Баланс: {balance} ₽")
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("💳 Пополнить", callback_data="topup"))
    markup.add(InlineKeyboardButton("🎟 Промокод", callback_data="use_promo"))
    
    bot.reply_to(message, text, parse_mode="HTML", reply_markup=markup)

# --- АДМИН ПАНЕЛЬ (ПРОМОКОДЫ) ---
@bot.message_handler(func=lambda message: message.text == "🎟 Создать промокод" and message.from_user.id == ADMIN_ID)
def promo_step1(message):
    user_states[message.from_user.id] = "promo_name"
    bot.send_message(message.chat.id, "Введите название промокода:")

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "promo_name")
def promo_step2(message):
    user_states[message.from_user.id] = {"name": message.text, "state": "promo_value"}
    bot.send_message(message.chat.id, "Введите скидку в рублях:")

@bot.message_handler(func=lambda message: isinstance(user_states.get(message.from_user.id), dict))
def promo_step3(message):
    data = user_states.pop(message.from_user.id)
    cursor = db_conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO promos (code, discount) VALUES (?, ?)", (data['name'], int(message.text)))
    db_conn.commit()
    bot.send_message(message.chat.id, f"✅ Промокод {data['name']} на {message.text}₽ создан!")

# --- ВЕБХУК ---
@app.route('/telegram_webhook', methods=['POST'])
def webhook():
    bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('utf-8'))])
    return "OK", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
