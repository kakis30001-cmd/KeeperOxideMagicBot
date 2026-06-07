import os
import json
import requests
import psycopg2
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from flask import Flask, request, jsonify

# ============================================
# НАСТРОЙКИ
# ============================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
DB_URL = os.getenv("DB_URL")
RAILWAY_URL = os.getenv("RAILWAY_URL")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# FSM (временное хранение)
user_states = {}

class Database:
    def get_connection(self):
        clean_db_url = DB_URL.replace("postgresql+asyncpg://", "postgresql://")
        return psycopg2.connect(clean_db_url)

    def init_db(self):
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS tg_users (user_id BIGINT PRIMARY KEY, balance INTEGER DEFAULT 0);
                    CREATE TABLE IF NOT EXISTS products (id SERIAL PRIMARY KEY, name TEXT, price INTEGER);
                    CREATE TABLE IF NOT EXISTS keys (id SERIAL PRIMARY KEY, product_id INTEGER REFERENCES products(id), key_value TEXT, is_sold BOOLEAN DEFAULT FALSE);
                ''')
            conn.commit()

    def get_products(self):
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, name, price FROM products")
                return cur.fetchall()

    def add_product(self, name, price):
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO products (name, price) VALUES (%s, %s)", (name, price))
            conn.commit()

db = Database()
db.init_db()

# ============================================
# КЛАВИАТУРЫ
# ============================================
def main_markup():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("🏪 Магазин"), KeyboardButton("👤 Профиль"))
    if "ADMIN_ID" in os.environ and int(os.environ["ADMIN_ID"]) == 0: pass # Заглушка
    return markup

def admin_markup():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("➕ Добавить товар"), KeyboardButton("🔙 Назад"))
    return markup

# ============================================
# ОБРАБОТЧИКИ
# ============================================
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Добро пожаловать в магазин!", reply_markup=main_markup())

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id == ADMIN_ID:
        bot.send_message(message.chat.id, "Админ-панель:", reply_markup=admin_markup())
    else:
        bot.send_message(message.chat.id, "Недостаточно прав.")

@bot.message_handler(func=lambda message: message.text == "🏪 Магазин")
def show_shop(message):
    products = db.get_products()
    if not products:
        bot.send_message(message.chat.id, "Товаров пока нет.")
        return
    
    markup = InlineKeyboardMarkup()
    for p in products:
        markup.add(InlineKeyboardButton(f"{p[1]} — {p[2]}₽", callback_data=f"buy_{p[0]}"))
    bot.send_message(message.chat.id, "Выберите товар:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "➕ Добавить товар" and message.from_user.id == ADMIN_ID)
def add_prod_step1(message):
    user_states[message.from_user.id] = "wait_name"
    bot.send_message(message.chat.id, "Введите название товара:")

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "wait_name")
def add_prod_step2(message):
    user_states[message.from_user.id] = {"name": message.text, "state": "wait_price"}
    bot.send_message(message.chat.id, "Введите цену:")

@bot.message_handler(func=lambda message: isinstance(user_states.get(message.from_user.id), dict) and user_states[message.from_user.id]["state"] == "wait_price")
def add_prod_step3(message):
    data = user_states.pop(message.from_user.id)
    db.add_product(data["name"], int(message.text))
    bot.send_message(message.chat.id, f"Товар {data['name']} добавлен!", reply_markup=admin_markup())

# ============================================
# FLASK ВЕБХУКИ (Тот же код, что и раньше)
# ============================================
@app.route('/telegram_webhook', methods=['POST'])
def telegram_webhook():
    update = telebot.types.Update.de_json(request.get_data().decode('utf-8'))
    bot.process_new_updates([update])
    return "OK", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
