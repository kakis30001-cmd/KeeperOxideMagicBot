import os
import sqlite3
import telebot
from telebot import types
from flask import Flask, request

# --- НАСТРОЙКИ ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect('shop.db', check_same_thread=False)
    conn.execute('CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY, name TEXT, price INTEGER)')
    conn.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance INTEGER DEFAULT 0)')
    conn.commit()
    conn.close()

init_db()

# --- СЛОВАРЬ СОСТОЯНИЙ ---
user_data = {}

# --- КОМАНДЫ ---
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🏪 Магазин", "👤 Профиль")
    if message.from_user.id == ADMIN_ID:
        markup.row("⚙️ Админ-панель")
    bot.send_message(message.chat.id, "Добро пожаловать в IceBerg Magic!", reply_markup=markup)

# --- АДМИНКА ---
@bot.message_handler(func=lambda m: m.text == "⚙️ Админ-панель" and m.from_user.id == ADMIN_ID)
def admin_panel(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("➕ Добавить товар", "🔙 Назад")
    bot.send_message(message.chat.id, "Админ-панель активна:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "➕ Добавить товар" and m.from_user.id == ADMIN_ID)
def add_product(message):
    bot.send_message(message.chat.id, "Введите название товара:")
    bot.register_next_step_handler(message, get_name)

def get_name(message):
    user_data[message.chat.id] = {"name": message.text}
    bot.send_message(message.chat.id, "Введите цену:")
    bot.register_next_step_handler(message, get_price)

def get_price(message):
    conn = sqlite3.connect('shop.db')
    conn.execute("INSERT INTO products (name, price) VALUES (?, ?)", (user_data[message.chat.id]['name'], message.text))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "✅ Товар успешно добавлен!", reply_markup=types.ReplyKeyboardRemove())
    start(message)

# --- МАГАЗИН ---
@bot.message_handler(func=lambda m: m.text == "🏪 Магазин")
def shop(message):
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()
    conn.close()

    if not products:
        bot.send_message(message.chat.id, "📦 В магазине пока пусто.")
    else:
        markup = types.InlineKeyboardMarkup()
        for p in products:
            markup.add(types.InlineKeyboardButton(f"{p[1]} — {p[2]}₽", callback_data=f"buy_{p[0]}"))
        bot.send_message(message.chat.id, "Выберите товар для покупки:", reply_markup=markup)

# --- FLASK ВЕБХУК ---
@app.route('/telegram_webhook', methods=['POST'])
def webhook():
    update = types.Update.de_json(request.get_data().decode('UTF-8'))
    bot.process_new_updates([update])
    return '!', 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
