import os
import telebot
from telebot import types
from flask import Flask, request
import sqlite3

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# --- БАЗА ДАННЫХ ---
def get_db():
    conn = sqlite3.connect('shop.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# --- КЛАВИАТУРЫ ---
def main_kb():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🏪 Магазин", "👤 Профиль")
    return markup

def profile_kb():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💳 Пополнить", callback_data="topup"))
    markup.add(types.InlineKeyboardButton("🎟 Промокод", callback_data="use_promo"))
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu"))
    return markup

# --- ОБРАБОТЧИКИ ---

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Добро пожаловать в <b>IceBerg Magic!</b>", 
                     parse_mode="HTML", reply_markup=main_kb())

@bot.message_handler(func=lambda m: m.text == "👤 Профиль")
def profile(message):
    # Берем баланс из БД (для примера пока 0)
    balance = 0 
    
    text = (
        f"👤 <b>Профиль пользователя</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⚡️ <b>Имя:</b> {message.from_user.first_name}\n"
        f"🆔 <b>ID:</b> <code>{message.from_user.id}</code>\n"
        f"💰 <b>Баланс:</b> <code>{balance} ₽</code>\n"
        f"━━━━━━━━━━━━━━━━━━"
    )
    bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=profile_kb())

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    if call.data == "back_to_menu":
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "Главное меню:", reply_markup=main_kb())
    
    elif call.data == "use_promo":
        bot.send_message(call.message.chat.id, "Введите ваш промокод:")
        bot.register_next_step_handler(call.message, apply_promo)

def apply_promo(message):
    # Тут логика проверки промокода в БД
    bot.send_message(message.chat.id, f"Промокод <code>{message.text}</code> не найден или истек! ❌", parse_mode="HTML")

# --- АДМИН ПАНЕЛЬ ---
@bot.message_handler(commands=['admin'])
def admin(message):
    if message.from_user.id == ADMIN_ID:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row("➕ Добавить товар", "🎟 Создать промокод")
        bot.send_message(message.chat.id, "Админ-панель открыта.", reply_markup=markup)

# --- FLASK ---
@app.route('/telegram_webhook', methods=['POST'])
def webhook():
    bot.process_new_updates([types.Update.de_json(request.get_data().decode('UTF-8'))])
    return '!', 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
