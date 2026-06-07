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

# Вот та самая переменная, которую потерял Python :)
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

user_states = {}
admin_data = {}

# ============================================
# БАЗА ДАННЫХ (PostgreSQL)
# ============================================
class Database:
    def get_connection(self):
        # Исправляем ссылку для psycopg2 "на лету"
        clean_db_url = DB_URL.replace("postgresql+asyncpg://", "postgresql://")
        return psycopg2.connect(clean_db_url)

    def init_db(self):
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS tg_users (
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
                # Теперь обращаемся к новой таблице tg_users
                cur.execute('INSERT INTO tg_users (user_id) VALUES (%s) ON CONFLICT DO NOTHING', (user_id,))
                cur.execute('SELECT balance FROM tg_users WHERE user_id = %s', (user_id,))
                return cur.fetchone()

# Создаем экземпляр базы
db = Database()
db.init_db()

# ============================================
# ЛОГИКА БОТА С ОТЛАДКОЙ
# ============================================
def main_menu():
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("🏪 Магазин", callback_data="shop"))
    markup.row(InlineKeyboardButton("👤 Профиль", callback_data="profile"))
    return markup

@bot.message_handler(commands=['start'])
def cmd_start(message):
    print("=" * 40)
    print(f"ПРИШЛА КОМАНДА /START ОТ {message.from_user.id}")
    
    try:
        # Проверяем базу данных
        db.get_user(message.from_user.id)
        print("1. База данных: Юзер записан/найден успешно.")
        
        # Пробуем отправить сообщение
        text = (
            "☺️ <b>Добро пожаловать в IceBerg Magic Cheat Shop</b>\n\n"
            "Для покупки товаров используйте кнопки ниже ⬇️"
        )
        bot.send_message(message.chat.id, text, reply_markup=main_menu(), parse_mode="HTML")
        print("2. Telegram: Сообщение успешно отправлено в чат!")
        
    except Exception as e:
        print(f"!!! ОШИБКА В ПРОЦЕССЕ: {e}")
        
    print("=" * 40)

# ============================================
# FLASK И ВЕБХУКИ
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

# ============================================
# ЗАПУСК
# ============================================
if __name__ == '__main__':
    print("=" * 60)
    print(" БОТ ЗАПУЩЕН")
    print("=" * 60)
    
    try:
        # Принудительно очищаем старые вебхуки и ставим новый
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook")
        
        # Убираем возможный слэш на конце RAILWAY_URL
        clean_railway_url = RAILWAY_URL.rstrip('/')
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook", json={"url": f"{clean_railway_url}/telegram_webhook"})
        print("✅ Webhook установлен")
    except Exception as e:
        print(f"❌ Ошибка установки вебхука: {e}")
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
