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

# Временное хранилище для процесса добавления
temp_data = {}

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

# --- КОМАНДЫ И ОБРАБОТЧИКИ ---
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Главное меню:", reply_markup=main_kb(message.from_user.id))

@bot.message_handler(func=lambda m: m.text == "⚙️ Админ-панель" and m.from_user.id == ADMIN_ID)
def admin_panel(message):
    bot.send_message(message.chat.id, "Админ-панель:", reply_markup=admin_kb())

@bot.message_handler(func=lambda m: m.text == "🔙 Назад")
def back_to_main(message):
    bot.send_message(message.chat.id, "Возврат в меню:", reply_markup=main_kb(message.from_user.id))

# --- ДОБАВЛЕНИЕ ТОВАРА (РАЗВЕРНУТО) ---
@bot.message_handler(func=lambda m: m.text == "➕ Добавить товар" and m.from_user.id == ADMIN_ID)
def start_add_product(message):
    bot.send_message(message.chat.id, "Введите название товара:")
    bot.register_next_step_handler(message, get_product_name)

def get_product_name(message):
    temp_data[message.chat.id] = {'name': message.text}
    bot.send_message(message.chat.id, "Теперь введите цену:")
    bot.register_next_step_handler(message, get_product_price)

def get_product_price(message):
    name = temp_data[message.chat.id]['name']
    price = message.text
    
    conn = get_db()
    conn.execute("INSERT INTO products (name, price) VALUES (?, ?)", (name, int(price)))
    conn.commit()
    conn.close()
    
    bot.send_message(message.chat.id, f"✅ Товар '{name}' с ценой {price}₽ добавлен!")
    # Удаляем временные данные
    del temp_data[message.chat.id]

# --- СОЗДАНИЕ ПРОМОКОДА (РАЗВЕРНУТО) ---
@bot.message_handler(func=lambda m: m.text == "🎟 Создать промокод" and m.from_user.id == ADMIN_ID)
def start_add_promo(message):
    bot.send_message(message.chat.id, "Введите название промокода:")
    bot.register_next_step_handler(message, get_promo_name)

def get_promo_name(message):
    temp_data[message.chat.id] = {'promo_name': message.text}
    bot.send_message(message.chat.id, "Введите скидку (в рублях):")
    bot.register_next_step_handler(message, get_promo_discount)

def get_promo_discount(message):
    code = temp_data[message.chat.id]['promo_name']
    discount = message.text
    
    conn = get_db()
    conn.execute("INSERT INTO promos (code, discount) VALUES (?, ?)", (code, int(discount)))
    conn.commit()
    conn.close()
    
    bot.send_message(message.chat.id, f"✅ Промокод '{code}' на {discount}₽ создан!")
    del temp_data[message.chat.id]

# --- ВЕБХУК ---
@app.route('/telegram_webhook', methods=['POST'])
def webhook():
    json_str = request.get_data().decode('UTF-8')
    update = types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return '!', 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
