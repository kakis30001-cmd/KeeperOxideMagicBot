import os
import json
import requests
import psycopg2
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask, request, jsonify

# ============================================
# НАСТРОЙКИ И ПЕРЕМЕННЫЕ
# ============================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
DB_URL = os.getenv("DB_URL")
RAILWAY_URL = os.getenv("RAILWAY_URL")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# Словари для имитации состояний (FSM) в telebot
user_states = {}
admin_data = {}

# ============================================
# БАЗА ДАННЫХ (PostgreSQL)
# ============================================
class Database:
    def get_connection(self):
        # Автоматически убираем +asyncpg, если он есть в переменной
        clean_db_url = DB_URL.replace("postgresql+asyncpg://", "postgresql://")
        return psycopg2.connect(clean_db_url)

    def init_db(self):
        # ... остальной код ...

    def init_db(self):
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY,
                        balance INTEGER DEFAULT 0
                    );
                    CREATE TABLE IF NOT EXISTS products (
                        id SERIAL PRIMARY KEY,
                        name TEXT,
                        price INTEGER
                    );
                    CREATE TABLE IF NOT EXISTS keys (
                        id SERIAL PRIMARY KEY,
                        product_id INTEGER REFERENCES products(id),
                        key_value TEXT,
                        is_sold BOOLEAN DEFAULT FALSE
                    );
                ''')
            conn.commit()

    def get_user(self, user_id):
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('INSERT INTO users (user_id) VALUES (%s) ON CONFLICT DO NOTHING', (user_id,))
                cur.execute('SELECT balance FROM users WHERE user_id = %s', (user_id,))
                return cur.fetchone()

    def add_product(self, name, price):
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('INSERT INTO products (name, price) VALUES (%s, %s) RETURNING id', (name, price))
                return cur.fetchone()[0]

    def add_keys(self, product_id, keys_list):
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                args_str = ','.join(cur.mogrify("(%s,%s)", (product_id, k)).decode('utf-8') for k in keys_list)
                cur.execute(f'INSERT INTO keys (product_id, key_value) VALUES {args_str}')

    def activate_subscription(self, user_id, sub_type, days):
        # Заглушка для твоей функции из вебхука Platega
        print(f"Активация подписки {sub_type} на {days} дней для Oxide-скрипта юзеру {user_id}")

db = Database()
db.init_db()

# ============================================
# КЛАВИАТУРЫ
# ============================================
def main_menu():
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("🏪 Магазин", callback_data="shop"))
    markup.row(InlineKeyboardButton("👤 Профиль", callback_data="profile"))
    markup.row(InlineKeyboardButton("📢 Поддержка", callback_data="support"))
    markup.row(InlineKeyboardButton("ℹ️ Правила", callback_data="rules"))
    return markup

# Заглушка для генерации ссылок из твоего кода
def create_group_link(sub_type):
    return "https://t.me/+example_invite_link"

# ============================================
# ЛОГИКА БОТА
# ============================================
@bot.message_handler(commands=['start'])
def cmd_start(message):
    db.get_user(message.from_user.id) # Регистрация юзера
    text = (
        "☺️ <b>Добро пожаловать в IceBerg Magic Cheat Shop</b>\n\n"
        "Для покупки товаров используйте кнопки ниже ⬇️"
    )
    bot.send_message(message.chat.id, text, reply_markup=main_menu(), parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data in ["profile", "back_main"])
def callback_handler(call):
    if call.data == "profile":
        user_data = db.get_user(call.from_user.id)
        balance = user_data[0] if user_data else 0
        
        text = (
            f"👤 <b>Ваш профиль:</b>\n\n"
            f"ID: <code>{call.from_user.id}</code>\n"
            f"💰 Баланс: <b>{balance} ₽</b>"
        )
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("💳 Пополнить баланс", callback_data="top_up"))
        markup.row(InlineKeyboardButton("🔙 Назад", callback_data="back_main"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")
        
    elif call.data == "back_main":
        text = (
            "☺️ <b>Добро пожаловать в IceBerg Magic Cheat Shop</b>\n\n"
            "Для покупки товаров используйте кнопки ниже ⬇️"
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=main_menu(), parse_mode="HTML")

# --- АДМИН ПАНЕЛЬ ---
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    user_states[message.from_user.id] = "waiting_for_name_price"
    bot.send_message(
        message.chat.id,
        "🛠 <b>Добавление товара</b>\n\n"
        "Отправь название и цену товара через тире.\n"
        "<i>Пример: Oxide Private Script - 500</i>",
        parse_mode="HTML"
    )

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "waiting_for_name_price")
def process_name_price(message):
    try:
        name, price = message.text.split("-")
        name = name.strip()
        price = int(price.strip())
        
        product_id = db.add_product(name, price)
        admin_data[message.from_user.id] = {"product_id": product_id}
        user_states[message.from_user.id] = "waiting_for_keys"
        
        bot.send_message(
            message.chat.id,
            f"✅ Товар <b>{name}</b> (Цена: {price}₽) создан.\n\n"
            "Теперь отправь список ключей для этого товара.\n"
            "<b>Каждый ключ с новой строки!</b>",
            parse_mode="HTML"
        )
    except ValueError:
        bot.send_message(message.chat.id, "❌ Ошибка формата. Напиши в формате: Название - Цена")

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "waiting_for_keys")
def process_keys(message):
    product_id = admin_data[message.from_user.id]["product_id"]
    keys_list = [key.strip() for key in message.text.split("\n") if key.strip()]
    
    if keys_list:
        db.add_keys(product_id, keys_list)
        bot.send_message(message.chat.id, f"✅ Успешно загружено ключей: <b>{len(keys_list)}</b> шт.", parse_mode="HTML")
    else:
        bot.send_message(message.chat.id, "❌ Вы не отправили ни одного ключа.")
        
    # Очищаем состояния
    user_states.pop(message.from_user.id, None)
    admin_data.pop(message.from_user.id, None)

# ============================================
# FLASK ПРИЛОЖЕНИЕ И ВЕБХУКИ
# ============================================
@app.route('/', methods=['GET'])
def index():
    return "Бот работает!", 200

@app.route('/telegram_webhook', methods=['POST'])
def telegram_webhook():
    try:
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    except Exception as e:
        print(f"Ошибка Telegram вебхука: {e}")
        return "Error", 200

@app.route('/webhook', methods=['POST'])
def platega_webhook():
    try:
        data = request.json
        print(f" Вебхук Platega: {json.dumps(data, indent=2)}")
        status = data.get('status')
        payload = data.get('payload')
        
        if status == "CONFIRMED" and payload:
            if payload.startswith('donate'):
                print(f" Получен донат: {payload}")
            elif payload.startswith('user'):
                parts = payload.split('_')
                if len(parts) >= 5:
                    user_id = int(parts[1])
                    sub_type = parts[2]
                    days = int(parts[3].replace('day', ''))
                    key = parts[4]
                    
                    db.activate_subscription(user_id, sub_type, days)
                    
                    group_link = create_group_link(sub_type)
                    group_text = f"\n\n Ссылка для входа в группу:\n{group_link}\n Ссылка одноразовая!" if group_link else ""
                    
                    try:
                        bot.send_message(
                            user_id,
                            f"✅ Оплата подтверждена!\n\n"
                            f"🔑 Ваш ключ: <code>{key}</code>\n"
                            f"📦 Подписка: {sub_type.upper()} {days} д.\n"
                            f"{group_text}\n\n"
                            f"Сохраните ключ!",
                            parse_mode="HTML"
                        )
                    except Exception as msg_e:
                        print(f"Ошибка отправки сообщения юзеру: {msg_e}")
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        print(f"Ошибка вебхука Platega: {e}")
        return jsonify({"status": "error"}), 500

# ============================================
# ЗАПУСК
# ============================================
if __name__ == '__main__':
    print("=" * 60)
    print(" БОТ ЗАПУЩЕН")
    print(f" Callback URL: {RAILWAY_URL}/webhook")
    print("=" * 60)
    
    try:
        # Устанавливаем вебхук Telegram при запуске
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook")
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook", json={"url": f"{RAILWAY_URL}/telegram_webhook"})
        print("✅ Webhook установлен")
    except Exception as e:
        print(f"❌ Ошибка установки вебхука: {e}")
    
    # Порт берётся из окружения Railway
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
