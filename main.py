import asyncio
import os
import uuid
from threading import Thread
from flask import Flask, request, jsonify
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
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

# Хранилище ожидающих платежей
pending_payments = {}

# ID VIP канала
VIP_CHANNEL_ID = -1003709565134  # Отрицательный ID для канала

# ========== КЛАВИАТУРЫ ==========
# Главное меню
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🛍 Магазин"), KeyboardButton(text="👤 Профиль")],
        [KeyboardButton(text="ℹ️ Информация")]
    ],
    resize_keyboard=True
)

# Меню профиля
profile_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💰 Пополнить баланс"), KeyboardButton(text="📋 История заказов")],
        [KeyboardButton(text="🏠 Главная")]
    ],
    resize_keyboard=True
)

# Меню ввода своей суммы (только своя сумма)
custom_amount_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="💰 Ввести свою сумму", callback_data="amount_custom")]
])

# Меню выбора способа оплаты
def get_payment_methods_menu(amount: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 СБП / Криптовалюта (Platega)", callback_data=f"payment_platega_{amount}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_profile")]
    ])

# ========== FSM СОСТОЯНИЯ ==========
class AddProductStates(StatesGroup):
    waiting_name = State()
    waiting_price = State()
    waiting_keys = State()  # Новое состояние для ключей

class CustomAmountStates(StatesGroup):
    waiting_amount = State()

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

@dp.message(lambda m: m.text == "🏠 Главная")
async def back_to_main(message: Message):
    await message.answer(
        "✨ *Главное меню*\n\nВыберите действие:",
        parse_mode="Markdown",
        reply_markup=main_menu
    )

# ========== ИНФОРМАЦИЯ ==========
@dp.message(lambda m: m.text == "ℹ️ Информация")
async def info_cmd(message: Message):
    info_text = (
        "ℹ️ *ИНФОРМАЦИЯ*\n\n"
        "🤖 *Официальный бот по продаже ключей для чит клиента Magic*\n\n"
        "💳 *Оплата:* Platega (СБП, Криптовалюта)\n\n"
        "📌 *Как пользоваться:*\n"
        "• Приобретите ключ через меню\n"
        "• После оплаты вы получите ключ и доступ в VIP канал\n\n"
        "📞 *КОНТАКТЫ:*\n"
        "• Техподдержка: @nikita1055\n"
        "• Основной канал: @keepersell\n"
        "• Отзывы: https://t.me/KeeperOtzivi\n\n"
        "⚖️ *ДОКУМЕНТЫ:*\n"
        "• [Политика конфиденциальности](https://telegra.ph/Politika-konfidencialnosti-04-01-26)\n"
        "• [Пользовательское соглашение](https://telegra.ph/Polzovatelskoe-soglashenie-04-01-19)"
    )
    
    await message.answer(
        info_text,
        parse_mode="Markdown",
        disable_web_page_preview=True
    )

# ========== МАГАЗИН ==========
@dp.message(lambda m: m.text == "🛍 Магазин")
async def shop_cmd(message: Message):
    products = await get_all_products()
    if not products:
        await message.answer("📭 *Товаров пока нет*\n\nОжидайте пополнения ассортимента.", parse_mode="Markdown")
        return
    
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

# ========== ПРОФИЛЬ ==========
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

@dp.message(lambda m: m.text == "📋 История заказов")
async def orders_history(message: Message):
    # TODO: добавить вывод истории из БД
    await message.answer(
        "📋 *История заказов*\n\n"
        "У вас пока нет покупок.",
        parse_mode="Markdown"
    )

# ========== ПОПОЛНЕНИЕ БАЛАНСА (ТОЛЬКО СВОЯ СУММА) ==========
@dp.message(lambda m: m.text == "💰 Пополнить баланс")
async def deposit_cmd(message: Message):
    await message.answer(
        "💰 *Пополнение баланса*\n\n"
        "Нажмите кнопку ниже, чтобы ввести сумму пополнения:",
        parse_mode="Markdown",
        reply_markup=custom_amount_menu
    )

@dp.callback_query(lambda c: c.data == "amount_custom")
async def handle_custom_amount(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(CustomAmountStates.waiting_amount)
    await callback.message.answer(
        "💰 Введите сумму пополнения (от 10 до 50000 ₽):\n\n"
        "Пример: `500`",
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.message(CustomAmountStates.waiting_amount)
async def process_custom_amount(message: Message, state: FSMContext):
    try:
        amount = int(message.text.strip())
        if amount < 10:
            await message.answer("❌ Минимальная сумма пополнения: *10 ₽*", parse_mode="Markdown")
            return
        if amount > 50000:
            await message.answer("❌ Максимальная сумма пополнения: *50000 ₽*", parse_mode="Markdown")
            return
        await show_payment_methods(message, amount)
        await state.clear()
    except ValueError:
        await message.answer("❌ Введите *число*!", parse_mode="Markdown")

async def show_payment_methods(target, amount: int):
    await target.answer(
        f"💰 *Пополнение на {amount} ₽*\n\n"
        "Выберите способ оплаты:",
        parse_mode="Markdown",
        reply_markup=get_payment_methods_menu(amount)
    )

@dp.callback_query(lambda c: c.data == "back_to_profile")
async def back_to_profile(callback: types.CallbackQuery):
    await callback.message.delete()
    balance = await get_balance(callback.from_user.id)
    await callback.message.answer(
        f"👤 *Профиль*\n\n"
        f"📛 Имя: {callback.from_user.full_name}\n"
        f"🆔 ID: `{callback.from_user.id}`\n"
        f"💰 Ваш баланс: `{balance} ₽`\n\n"
        f"Выберите действие в меню ниже:",
        parse_mode="Markdown",
        reply_markup=profile_menu
    )
    await callback.answer()

# ========== ГЕНЕРАЦИЯ ССЫЛКИ НА ОПЛАТУ (PLATEGA) ==========
@dp.callback_query(lambda c: c.data and c.data.startswith("payment_platega_"))
async def handle_platega_payment(callback: types.CallbackQuery):
    amount = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    
    payment_id = str(uuid.uuid4())
    pending_payments[user_id] = {
        "amount": amount,
        "payment_id": payment_id,
        "status": "pending"
    }
    
    # ЗАМЕНИ НА РЕАЛЬНЫЙ API PLATEGA
    payment_url = f"https://platega.com/pay?amount={amount}&payment_id={payment_id}&user_id={user_id}"
    
    await callback.message.answer(
        f"💳 *Оплата через Platega*\n\n"
        f"Сумма: `{amount} ₽`\n\n"
        f"🔗 [Нажмите для оплаты]({payment_url})\n\n"
        f"⚡ После оплаты баланс пополнится автоматически.\n\n"
        f"🆔 ID платежа: `{payment_id}`",
        parse_mode="Markdown",
        disable_web_page_preview=True
    )
    await callback.answer()

# ========== ПОКУПКИ ==========
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
    
    # Ссылка на VIP канал
    vip_link = f"https://t.me/joinchat/AAAAAEAAAAAAAAAAAAAAAAAAAAA"
    # ВНИМАНИЕ: реальную ссылку на канал нужно создать через @getmyid бота
    # Или использовать invite link из настроек канала
    
    await callback.message.answer(
        f"✅ *Покупка успешна!*\n\n"
        f"🎮 Товар: {product['name']}\n"
        f"💰 Цена: {product['price']} ₽\n"
        f"🔑 *Ключ:* `{key_row['key_value']}`\n\n"
        f"🔗 *Ссылка на VIP канал:*\n"
        f"[Нажмите для вступления](https://t.me/joinchat/AAAAAEAAAAAAAAAAAAAAAAAAAAA)\n\n"
        f"💡 Сохраните ключ, он не будет показан снова!",
        parse_mode="Markdown",
        disable_web_page_preview=True
    )
    await callback.answer("🎉 Спасибо за покупку!")

# ========== АДМИН-КОМАНДЫ (НАЗВАНИЕ → ЦЕНА → КЛЮЧИ) ==========
@dp.message(Command("admin"))
async def admin_cmd(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ *Доступ запрещен*", parse_mode="Markdown")
        return
    
    admin_menu = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Добавить товар"), KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="🏠 Главная")]
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
        await state.update_data(price=price)
        await state.set_state(AddProductStates.waiting_keys)
        await message.answer(
            "🔑 Введите *ключи* (каждый с новой строки):\n\n"
            "Пример:\n`KEY-123-ABC`\n`KEY-456-DEF`\n`KEY-789-GHI`\n\n"
            "Сколько ключей введете — столько и будет в наличии.",
            parse_mode="Markdown"
        )
    except ValueError:
        await message.answer("❌ Введите *число*!", parse_mode="Markdown")

@dp.message(AddProductStates.waiting_keys)
async def product_keys(message: Message, state: FSMContext):
    data = await state.get_data()
    name = data["name"]
    price = data["price"]
    
    # Разбиваем ключи по строкам
    keys = [k.strip() for k in message.text.split("\n") if k.strip()]
    
    if not keys:
        await message.answer("❌ Необходимо ввести хотя бы один ключ!", parse_mode="Markdown")
        return
    
    # Добавляем товар в БД
    product_id = await add_product(name, price)
    
    # Добавляем все ключи
    await add_keys_to_product(product_id, keys)
    
    await message.answer(
        f"✅ *Товар добавлен!*\n\n"
        f"📛 Название: {name}\n"
        f"💰 Цена: {price} ₽\n"
        f"🔑 Количество ключей: {len(keys)}\n\n"
        f"📦 ID товара: {product_id}",
        parse_mode="Markdown"
    )
    await state.clear()

@dp.message(lambda m: m.text == "📊 Статистика")
async def stats_cmd(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    from database import get_stats
    stats = await get_stats()
    
    await message.answer(
        f"📊 *Статистика*\n\n"
        f"👥 Пользователей: `{stats['users']}`\n"
        f"💰 Продаж на сумму: `{stats['total_sales']} ₽`\n"
        f"🔑 Выдано ключей: `{stats['keys_sold']}`\n"
        f"📦 Товаров в продаже: `{stats['products_count']}`",
        parse_mode="Markdown"
    )

# ========== ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ БД ==========
# Эти функции нужно добавить в database.py
# async def get_stats(): ...
# async def add_product возвращает id

# ========== FLASK ВЕБХУК ==========
@flask_app.route("/webhook/payment", methods=["POST"])
def payment_webhook():
    data = request.get_json()
    
    payment_id = data.get("payment_id")
    user_id = data.get("user_id")
    amount = data.get("amount")
    status = data.get("status")
    
    if status == "success" and user_id and amount:
        async def update_balance():
            current = await get_balance(user_id)
            await update_user_balance(user_id, current + amount)
            await bot.send_message(
                user_id,
                f"✅ *Баланс пополнен!*\n\n"
                f"Сумма: `{amount} ₽`\n"
                f"Новый баланс: `{current + amount} ₽`",
                parse_mode="Markdown"
            )
        
        asyncio.run(update_balance())
        
        if user_id in pending_payments:
            del pending_payments[user_id]
        
        return jsonify({"status": "ok"}), 200
    
    return jsonify({"status": "error"}), 400

@flask_app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "alive"}), 200

# ========== ЗАПУСК ==========
def run_flask():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host="0.0.0.0", port=port)

async def main():
    await connect_db()
    await bot.delete_webhook(drop_pending_updates=True)
    
    thread = Thread(target=run_flask, daemon=True)
    thread.start()
    
    print("🤖 Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
