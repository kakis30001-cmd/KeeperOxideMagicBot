import os
import sqlite3
import telebot
from telebot import types
from flask import Flask, request

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
    conn.execute('CREATE TABLE IF NOT EXISTS promos (code TEXT PRIMARY KEY, discount INTEGER)')
    conn.commit()
    conn.close()

init_db()

user_data = {}

# --- КЛАВИАТУРЫ ---
def main_kb(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🏪 Магазин", "👤 Профиль")
    if user_id == ADMIN_ID:
        markup.row("⚙️ Админ-панель")
    return markup

def admin_kb():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("➕ Добавить товар", "🎟 Создать промокод")
    markup.row("🔙 Назад")
    return markup

# --- ОБРАБОТЧИКИ ---
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Добро пожаловать в IceBerg Magic!", reply_markup=main_kb(message.from_user.id))

@bot.message_handler(func=lambda m: m.text == "👤 Профиль")
def profile(message):
    conn = get_db()
    user = conn.execute("SELECT balance FROM users WHERE user_id = ?", (message.from_user.id,)).fetchone()
    balance = user['balance'] if user else 0
    conn.close()
    text = f"👤 <b>Профиль</b>\n🆔 ID: <code>{message.from_user.id}</code>\n💰 Баланс: <b>{balance}₽</b>"
    bot.send_message(message.chat.id, text, parse_mode="HTML")

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

# --- АДМИН-ПАНЕЛЬ ---
@bot.message_handler(func=lambda m: m.text == "⚙️ Админ-панель" and m.from_user.id == ADMIN_ID)
def admin_panel(message):
    bot.send_message(message.chat.id, "Панель управления:", reply_markup=admin_kb())

@bot.message_handler(func=lambda m: m.text == "🔙 Назад")
def back(message):
    bot.send_message(message.chat.id, "Главное меню:", reply_markup=main_kb(message.from_user.id))

# Добавление товара
@bot.message_handler(func=lambda m: m.text == "➕ Добавить товар" and m.from_user.id == ADMIN_ID)
def add_prod(message):
    bot.send_message(message.chat.id, "Введите название товара:")
    bot.register_next_step_handler(message, lambda m: bot.send_message(message.chat.id, "Введите цену:") or bot.register_next_step_handler(m, lambda price: save_prod(m.text, price.text)))

def save_prod(name, price):
    conn = get_db()
    conn.execute("INSERT INTO products (name, price) VALUES (?, ?)", (name, int(price)))
    conn.commit()
    conn.close()
    bot.send_message(ADMIN_ID, f"✅ Товар {name} добавлен.")

# Создание промокода
@bot.message_handler(func=lambda m: m.text == "🎟 Создать промокод" and m.from_user.id == ADMIN_ID)
def add_promo(message):
    bot.send_message(message.chat.id, "Введите название промокода:")
    bot.register_next_step_handler(message, lambda m: bot.send_message(message.chat.id, "Введите скидку (рубли):") or bot.register_next_step_handler(m, lambda disc: save_promo(m.text, disc.text)))

def save_promo(code, discount):
    conn = get_db()
    conn.execute("INSERT INTO promos (code, discount) VALUES (?, ?)", (code, int(discount)))
    conn.commit()
    conn.close()
    bot.send_message(ADMIN_ID, f"✅ Промокод {code} на {discount}₽ создан.")

# --- ВЕБХУК ---
@app.route('/telegram_webhook', methods=['POST'])
def webhook():
    bot.process_new_updates([types.Update.de_json(request.get_data().decode('UTF-8'))])
    return '!', 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
