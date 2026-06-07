import asyncio
import os
from threading import Thread
from flask import Flask, request, jsonify
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from config import BOT_TOKEN, ADMIN_ID, DB_URL, RAILWAY_URL
from database import (
    connect_db, add_user, get_balance, get_all_products,
    add_product, add_keys_to_product, get_unused_key,
    mark_key_as_used, update_user_balance
)

# ========== ИНИЦИАЛИЗАЦИЯ ==========
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
flask_app = Flask(__name__)

# ========== КЛАВИАТУРЫ ==========
# Главное меню (как на скрине)
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🛍 Магазин"), KeyboardButton(text="👤 Профиль")],
        [KeyboardButton(text="📞 Поддержка"), KeyboardButton(text="📜 Правила")]
    ],
    resize_keyboard=True
)

# Меню профиля
profile_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💰 Пополнить баланс"), KeyboardButton(text="📋 История заказов")],
        [KeyboardButton(text="👥 Реферальная система"), KeyboardButton(text="🎟 Активировать промокод")],
        [KeyboardButton(text="🏠 Главная")]
    ],
    resize_keyboard=True
)

# Меню магазина
shop_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🏠 Главная")]
    ],
    resize_keyboard=True
)

# ========== FSM СОСТОЯНИЯ ==========
class AddProductStates(StatesGroup):
    waiting_name = State()
    waiting_price = State()

class AddKeysStates(StatesGroup):
    waiting_product_id = State()
    waiting_keys = State()

# ========== КОМАНДЫ БОТА ==========
@dp.message(CommandStart())
async def start_cmd(message: Message):
    await add_user(message.from_user.id)
    await message.answer(
        "✨ *Добро пожаловать в IceBerg Magic Cheat Shop*\n\n"
        "Для покупки товаров используйте кнопки ниже ↓",
        parse_mode="Markdown",
        reply_markup=main_menu
    )

# ========== ГЛАВНОЕ МЕНЮ ==========
@dp.message(lambda m: m.text == "🏠 Главная")
async def back_to_main(message: Message):
    await message.answer(
        "✨ *Главное меню*\n\nВыберите действие:",
        parse_mode="Markdown",
        reply_markup=main_menu
    )

@dp.message(lambda m: m.text == "🛍 Магазин")
async def shop_cmd(message: Message):
    products = await get_all_products()
    if not products:
        await message.answer("📭 *Товаров пока нет*\n\nОжидайте пополнения ассортимента.", parse_mode="Markdown")
        return
    
    # Создаем красивые кнопки с товарами
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🎮 {p['name']} | {p['price']}₽", callback_data=f"buy_{p['id']}")]
        for p in products
    ])
    
    await message.answer(
        "🛍 *Выберите нужный товар*\n\n"
        "Нажмите на кнопку с товаром для покупки:",
        parse_mode="Markdown",
        reply_markup=kb
    )

@dp.message(lambda m: m.text == "👤 Профиль")
async def profile_cmd(message: Message):
    balance = await get_balance(message.from_user.id)
    await message.answer(
        f"👤 *Профиль*\n\n"
        f"📛 Имя: {message.from_user.full_name}\n"
        f"🆔 ID: `{message.from_user.id}`\n"
        f"💰 Ваш баланс: `{balance} ₽`\n\n"
        f"Выберите действие в меню ниже:",
        parse_mode="Markdown",
        reply_markup=profile_menu
    )

@dp.message(lambda m: m.text == "💰 Пополнить баланс")
async def deposit_cmd(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="100 ₽", callback_data="deposit_100")],
        [InlineKeyboardButton(text="500 ₽", callback_data="deposit_500")],
        [InlineKeyboardButton(text="1000 ₽", callback_data="deposit_1000")],
        [InlineKeyboardButton(text="5000 ₽", callback_data="deposit_5000")]
    ])
    await message.answer(
        "💰 *Пополнение баланса*\n\n"
        "Выберите сумму пополнения:",
        parse_mode="Markdown",
        reply_markup=kb
    )

@dp.message(lambda m: m.text == "📋 История заказов")
async def orders_history(message: Message):
    # TODO: добавить вывод истории из БД
    await message.answer(
        "📋 *История заказов*\n\n"
        "У вас пока нет покупок.",
        parse_mode="Markdown"
    )

@dp.message(lambda m: m.text == "👥 Реферальная система")
async def referral_cmd(message: Message):
    await message.answer(
        "👥 *Реферальная система*\n\n"
        "Приглашайте друзей и получайте бонусы!\n\n"
        "Ваша реферальная ссылка:\n"
        f"`https://t.me/{bot.username}?start=ref_{message.from_user.id}`\n\n"
        "За каждого приглашенного друга вы получите 5% от его покупок!",
        parse_mode="Markdown"
    )

@dp.message(lambda m: m.text == "🎟 Активировать промокод")
async def promo_cmd(message: Message):
    # TODO: добавить промокоды
    await message.answer(
        "🎟 *Активация промокода*\n\n"
        "Введите промокод для активации:",
        parse_mode="Markdown"
    )

@dp.message(lambda m: m.text == "📞 Поддержка")
async def support_cmd(message: Message):
    await message.answer(
        "📞 *Служба поддержки*\n\n"
        "По всем вопросам обращайтесь:\n"
        "✉ Telegram: @support_username\n"
        "📧 Email: support@iceberg.com\n\n"
        "Мы ответим в ближайшее время!",
        parse_mode="Markdown"
    )

@dp.message(lambda m: m.text == "📜 Правила")
async def rules_cmd(message: Message):
    await message.answer(
        "📜 *Правила магазина*\n\n"
        "1. Ключи активируются сразу после покупки\n"
        "2. Возврат средств осуществляется только при нерабочем ключе\n"
        "3. Запрещено передавать ключи третьим лицам\n"
        "4. Администрация не несет ответственность за баны в играх\n\n"
        "Нарушение правил = блокировка аккаунта",
        parse_mode="Markdown"
    )

# ========== ПОКУПКИ ==========
@dp.callback_query(lambda c: c.data and c.data.startswith("deposit_"))
async def handle_deposit(callback: types.CallbackQuery):
    amount = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    
    # TODO: подключить реальную платежную систему
    # Сейчас просто добавляем баланс для теста
    current_balance = await get_balance(user_id)
    await update_user_balance(user_id, current_balance + amount)
    
    await callback.message.answer(
        f"✅ *Баланс пополнен!*\n\n"
        f"Сумма: `{amount} ₽`\n"
        f"Новый баланс: `{current_balance + amount} ₽`",
        parse_mode="Markdown",
        reply_markup=profile_menu
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data and c.data.startswith("buy_"))
async def handle_buy(callback: types.CallbackQuery):
    product_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    
    products = await get_all_products()
    product = next((p for p in products if p["id"] == product_id), None)
    if not product:
        await callback.answer("❌ Товар не найден")
        return
    
    balance = await get_balance(user_id)
    if balance < product["price"]:
        await callback.answer(f"❌ Недостаточно средств! Нужно {product['price']} ₽")
        return
    
    key_row = await get_unused_key(product_id)
    if not key_row:
        await callback.answer("❌ Ключи закончились. Обратитесь в поддержку")
        return
    
    # Списываем деньги
    await update_user_balance(user_id, balance - product["price"])
    await mark_key_as_used(key_row["id"])
    
    await callback.message.answer(
        f"✅ *Покупка успешна!*\n\n"
        f"🎮 Товар: {product['name']}\n"
        f"💰 Цена: {product['price']} ₽\n"
        f"🔑 Ключ: `{key_row['key_value']}`\n\n"
        f"💡 Сохраните ключ, он не будет показан снова!",
        parse_mode="Markdown"
    )
    await callback.answer("🎉 Спасибо за покупку!")

# ========== АДМИН-КОМАНДЫ ==========
@dp.message(Command("admin"))
async def admin_cmd(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ *Доступ запрещен*", parse_mode="Markdown")
        return
    
    admin_menu = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Добавить товар"), KeyboardButton(text="🔑 Добавить ключи")],
            [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="🏠 Главная")]
        ],
        resize_keyboard=True
    )
    await message.answer(
        "🔐 *Админ-панель*\n\n"
        "Выберите действие:",
        parse_mode="Markdown",
        reply_markup=admin_menu
    )

@dp.message(lambda m: m.text == "➕ Добавить товар")
async def add_product_cmd(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.set_state(AddProductStates.waiting_name)
    await message.answer("📝 Введите *название товара*:", parse_mode="Markdown")

@dp.message(AddProductStates.waiting_name)
async def product_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AddProductStates.waiting_price)
    await message.answer("💰 Введите *цену* (число):", parse_mode="Markdown")

@dp.message(AddProductStates.waiting_price)
async def product_price(message: Message, state: FSMContext):
    try:
        price = int(message.text)
        data = await state.get_data()
        await add_product(data["name"], price)
        await message.answer(
            f"✅ *Товар добавлен!*\n\n"
            f"📛 Название: {data['name']}\n"
            f"💰 Цена: {price} ₽",
            parse_mode="Markdown"
        )
        await state.clear()
    except ValueError:
        await message.answer("❌ Введите *число*!", parse_mode="Markdown")

@dp.message(lambda m: m.text == "🔑 Добавить ключи")
async def add_keys_cmd(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    products = await get_all_products()
    if not products:
        await message.answer("❌ Сначала добавьте товар через *➕ Добавить товар*", parse_mode="Markdown")
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{p['name']} (ID: {p['id']})", callback_data=f"key_product_{p['id']}")]
        for p in products
    ])
    await message.answer("📦 Выберите товар для добавления ключей:", reply_markup=kb)

@dp.callback_query(lambda c: c.data and c.data.startswith("key_product_"))
async def select_product_keys(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔")
        return
    product_id = int(callback.data.split("_")[2])
    await state.update_data(product_id=product_id)
    await state.set_state(AddKeysStates.waiting_keys)
    await callback.message.answer(
        "🔑 Отправьте *ключи* (каждый с новой строки):\n\n"
        "Пример:\n`KEY-123-ABC`\n`KEY-456-DEF`",
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.message(AddKeysStates.waiting_keys)
async def process_keys(message: Message, state: FSMContext):
    data = await state.get_data()
    product_id = data["product_id"]
    keys = [k.strip() for k in message.text.split("\n") if k.strip()]
    
    await add_keys_to_product(product_id, keys)
    await message.answer(
        f"✅ *Добавлено {len(keys)} ключей!*\n\n"
        f"📦 ID товара: {product_id}",
        parse_mode="Markdown"
    )
    await state.clear()

@dp.message(lambda m: m.text == "📊 Статистика")
async def stats_cmd(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    # TODO: добавить реальную статистику
    await message.answer(
        "📊 *Статистика*\n\n"
        "👥 Пользователей: скоро будет\n"
        "💰 Продаж: скоро будет\n"
        "🔑 Выдано ключей: скоро будет",
        parse_mode="Markdown"
    )

# ========== FLASK ДЛЯ ПЛАТЕЖЕЙ ==========
@flask_app.route("/webhook/payment", methods=["POST"])
def payment_webhook():
    data = request.get_json()
    # TODO: подключить реальную платежную систему
    return jsonify({"status": "ok"}), 200

@flask_app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "alive"}), 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host="0.0.0.0", port=port)

# ========== ЗАПУСК ==========
async def main():
    await connect_db()
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Запускаем Flask в отдельном потоке
    thread = Thread(target=run_flask, daemon=True)
    thread.start()
    
    print("🤖 Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
