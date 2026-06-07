import os
import sqlite3
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from flask import Flask, request

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# Работа с SQLite (на Railway лучше создать базу в /tmp/shop.db или использовать Postgre)
conn = sqlite3.connect('shop.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY, name TEXT, price INTEGER)')
cursor.execute('CREATE TABLE IF NOT EXISTS keys (id INTEGER PRIMARY KEY, prod_id INTEGER, key_text TEXT)')
conn.commit()

user_states = {}

# --- КЛАВИАТУРЫ ---
def main_markup():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🏪 Магазин", "👤 Профиль")
    return markup

def back_markup():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔙 Назад", callback_data="main_menu"))
    return markup

# --- АДМИНКА ---
@bot.message_handler(commands=['admin'])
def admin_cmd(message):
    if message.from_user.id == ADMIN_ID:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("➕ Добавить товар", "🔙 Назад")
        bot.send_message(message.chat.id, "Админ-панель открыта", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "➕ Добавить товар" and message.from_user.id == ADMIN_ID)
def add_prod(message):
    user_states[message.from_user.id] = "wait_name"
    bot.send_message(message.chat.id, "Введите название товара:")

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "wait_name")
def get_name(message):
    user_states[message.from_user.id] = {"name": message.text, "state": "wait_price"}
    bot.send_message(message.chat.id, "Введите цену:")

@bot.message_handler(func=lambda message: isinstance(user_states.get(message.from_user.id), dict))
def get_price(message):
    data = user_states.pop(message.from_user.id)
    cursor.execute("INSERT INTO products (name, price) VALUES (?, ?)", (data['name'], int(message.text)))
    conn.commit()
    bot.send_message(message.chat.id, "✅ Товар добавлен!")

# --- МАГАЗИН И ОБРАБОТКА ---
@bot.message_handler(func=lambda message: message.text == "🏪 Магазин")
def shop(message):
    cursor.execute("SELECT id, name, price FROM products")
    products = cursor.fetchall()
    if not products:
        bot.send_message(message.chat.id, "📦 В магазине пока пусто.", reply_markup=back_markup())
        return
    
    markup = InlineKeyboardMarkup()
    for p in products:
        markup.add(InlineKeyboardButton(f"{p[1]} - {p[2]}₽", callback_data=f"buy_{p[0]}"))
    markup.add(InlineKeyboardButton("🔙 Назад", callback_data="main_menu"))
    bot.send_message(message.chat.id, "Выберите товар:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == "main_menu":
        bot.edit_message_text("Возвращаю в меню...", call.message.chat.id, call.message.message_id)
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "Главное меню:", reply_markup=main_markup())
    
    elif call.data.startswith("buy_"):
        prod_id = call.data.split("_")[1]
        bot.answer_callback_query(call.id, "Вы выбрали товар!")
        # Тут логика оплаты

@app.route('/telegram_webhook', methods=['POST'])
def webhook():
    bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('utf-8'))])
    return "OK", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
