import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from flask import Flask, request

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# Хранилище состояний
user_states = {}

# --- БАЗА ДАННЫХ (Упрощенная структура) ---
# В реале лучше хранить в БД, здесь для примера используем словарь
# Структура: {user_id: {"balance": 0}}
users_db = {}
promo_codes = {} # {"NAME": {"type": "rub/percent", "value": 100}}

def get_user_data(user_id):
    if user_id not in users_db:
        users_db[user_id] = {"balance": 0}
    return users_db[user_id]

# --- КЛАВИАТУРЫ ---
def main_markup():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("🏪 Магазин"), KeyboardButton("👤 Профиль"))
    return markup

def profile_markup():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("💳 Пополнить", callback_data="topup"))
    markup.add(InlineKeyboardButton("🎟 Промокод", callback_data="use_promo"))
    markup.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return markup

# --- ОБРАБОТЧИКИ ---

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Добро пожаловать!\n\nБот для продажи подписок LITE и VIP.\nОплата через Platega (СБП, Криптовалюта).", reply_markup=main_markup())

@bot.message_handler(func=lambda message: message.text == "👤 Профиль")
def profile(message):
    data = get_user_data(message.from_user.id)
    text = (f"👤 Профиль: {message.from_user.first_name}\n"
            f"🆔 ID: <code>{message.from_user.id}</code>\n"
            f"💰 Баланс: {data['balance']} ₽")
    bot.reply_to(message, text, parse_mode="HTML", reply_markup=profile_markup())

# --- АДМИН ПАНЕЛЬ ---
@bot.message_handler(commands=['admin'])
def admin(message):
    if message.from_user.id == ADMIN_ID:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("➕ Товар", "🎟 Создать промокод", "🔙 Назад")
        bot.send_message(message.chat.id, "Админ-панель", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "🎟 Создать промокод" and message.from_user.id == ADMIN_ID)
def promo_step1(message):
    user_states[message.from_user.id] = "promo_name"
    bot.send_message(message.chat.id, "Введите название промокода:")

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "promo_name")
def promo_step2(message):
    user_states[message.from_user.id] = {"name": message.text, "state": "promo_value"}
    bot.send_message(message.chat.id, "Введите скидку (число):")

@bot.message_handler(func=lambda message: isinstance(user_states.get(message.from_user.id), dict) and user_states[message.from_user.id].get("state") == "promo_value")
def promo_step3(message):
    data = user_states.pop(message.from_user.id)
    promo_codes[data["name"]] = {"value": int(message.text)}
    bot.send_message(message.chat.id, f"Промокод {data['name']} на {message.text} создан!")

# --- ИСПРАВЛЕННЫЙ ДОБАВИТЕЛЬ ТОВАРА ---
@bot.message_handler(func=lambda message: message.text == "➕ Товар" and message.from_user.id == ADMIN_ID)
def add_prod_1(message):
    user_states[message.from_user.id] = "add_prod_name"
    bot.send_message(message.chat.id, "Введите название:")

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "add_prod_name")
def add_prod_2(message):
    user_states[message.from_user.id] = {"name": message.text, "state": "add_prod_price"}
    bot.send_message(message.chat.id, "Введите цену:")

@bot.message_handler(func=lambda message: isinstance(user_states.get(message.from_user.id), dict) and user_states[message.from_user.id]["state"] == "add_prod_price")
def add_prod_3(message):
    data = user_states.pop(message.from_user.id)
    # Здесь добавить db.add_product(data["name"], message.text)
    bot.send_message(message.chat.id, f"Товар {data['name']} за {message.text} добавлен!")

@app.route('/telegram_webhook', methods=['POST'])
def webhook():
    bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('utf-8'))])
    return "OK", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
