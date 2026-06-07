import os
import telebot
from telebot import types
from flask import Flask, request
import sqlite3

# --- Инициализация ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# --- База данных (упростил до надежного формата) ---
def get_db():
    conn = sqlite3.connect('shop.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# --- КЛАВИАТУРЫ ---
def main_kb():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🏪 Магазин", "👤 Профиль")
    return markup

def admin_kb():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("➕ Добавить товар", "🎟 Добавить промокод")
    markup.row("🔙 Назад в меню")
    return markup

# --- ОБРАБОТЧИКИ ---

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Добро пожаловать! Выберите раздел:", reply_markup=main_kb())

@bot.message_handler(commands=['admin'])
def admin_menu(message):
    if message.from_user.id == ADMIN_ID:
        bot.send_message(message.chat.id, "Админ-панель:", reply_markup=admin_kb())
    else:
        bot.send_message(message.chat.id, "Доступ запрещен.")

@bot.message_handler(func=lambda m: m.text == "🏪 Магазин")
def shop(message):
    conn = get_db()
    products = conn.execute("SELECT * FROM products").fetchall()
    
    if not products:
        bot.send_message(message.chat.id, "В магазине пусто.")
    else:
        markup = types.InlineKeyboardMarkup()
        for p in products:
            markup.add(types.InlineKeyboardButton(f"{p['name']} - {p['price']}₽", callback_data=f"buy_{p['id']}"))
        bot.send_message(message.chat.id, "Наши товары:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🔙 Назад в меню")
def back(message):
    bot.send_message(message.chat.id, "Главное меню:", reply_markup=main_kb())

# --- АДМИН ЛОГИКА (Добавление товара) ---
user_data = {}

@bot.message_handler(func=lambda m: m.text == "➕ Добавить товар" and m.from_user.id == ADMIN_ID)
def add_prod(message):
    bot.send_message(message.chat.id, "Введите название товара:")
    bot.register_next_step_handler(message, process_name)

def process_name(message):
    user_data[message.chat.id] = {'name': message.text}
    bot.send_message(message.chat.id, "Теперь введите цену:")
    bot.register_next_step_handler(message, process_price)

def process_price(message):
    conn = get_db()
    conn.execute("INSERT INTO products (name, price) VALUES (?, ?)", (user_data[message.chat.id]['name'], message.text))
    conn.commit()
    bot.send_message(message.chat.id, "✅ Товар добавлен!", reply_markup=admin_kb())

# --- ВЕБХУК ---
@app.route('/telegram_webhook', methods=['POST'])
def webhook():
    json_str = request.get_data().decode('UTF-8')
    update = types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return '!', 200

if __name__ == '__main__':
    # Инициализация таблиц
    conn = get_db()
    conn.execute("CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY, name TEXT, price INTEGER)")
    conn.close()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
