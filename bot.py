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
def get_db():
    conn = sqlite3.connect('shop.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY, name TEXT, price INTEGER)')
    conn.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance INTEGER DEFAULT 0)')
    conn.commit()
    conn.close()

init_db()

# --- КЛАВИАТУРЫ ---
def main_kb(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🏪 Магазин", "👤 Профиль")
    if user_id == ADMIN_ID:
        markup.row("⚙️ Админ-панель")
    return markup

# --- ОБРАБОТЧИКИ ---
@bot.message_handler(commands=['start'])
def start(message):
    conn = get_db()
    conn.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (message.from_user.id,))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "Добро пожаловать в IceBerg Magic!", reply_markup=main_kb(message.from_user.id))

@bot.message_handler(func=lambda m: m.text == "👤 Профиль")
def profile(message):
    conn = get_db()
    user = conn.execute("SELECT balance FROM users WHERE user_id = ?", (message.from_user.id,)).fetchone()
    balance = user['balance'] if user else 0
    conn.close()
    
    text = f"👤 <b>Профиль</b>\n🆔 ID: <code>{message.from_user.id}</code>\n💰 Баланс: <b>{balance}₽</b>"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💳 Пополнить", callback_data="topup"))
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "🏪 Магазин")
def shop(message):
    conn = get_db()
    products = conn.execute("SELECT * FROM products").fetchall()
    conn.close()
    
    if not products:
        bot.send_message(message.chat.id, "📦 Магазин пуст.")
    else:
        markup = types.InlineKeyboardMarkup()
        for p in products:
            markup.add(types.InlineKeyboardButton(f"{p['name']} - {p['price']}₽", callback_data=f"buy_{p['id']}"))
        bot.send_message(message.chat.id, "Выберите товар:", reply_markup=markup)

# --- АДМИН-ПАНЕЛЬ (Логика добавления) ---
@bot.message_handler(func=lambda m: m.text == "⚙️ Админ-панель" and m.from_user.id == ADMIN_ID)
def admin_panel(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("➕ Добавить товар", "🔙 Назад")
    bot.send_message(message.chat.id, "Админ-панель:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "➕ Добавить товар" and m.from_user.id == ADMIN_ID)
def add_prod(message):
    bot.send_message(message.chat.id, "Введите название:")
    bot.register_next_step_handler(message, lambda m: bot.send_message(message.chat.id, "Введите цену:") or bot.register_next_step_handler(m, lambda price_m: save_prod(m.text, price_m.text)))

def save_prod(name, price):
    conn = get_db()
    conn.execute("INSERT INTO products (name, price) VALUES (?, ?)", (name, int(price)))
    conn.commit()
    conn.close()
    bot.send_message(ADMIN_ID, "✅ Товар добавлен.")

# --- ВЕБХУК ---
@app.route('/telegram_webhook', methods=['POST'])
def webhook():
    bot.process_new_updates([types.Update.de_json(request.get_data().decode('UTF-8'))])
    return '!', 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
