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
pending_payments = {}  # {user_id: {"amount": int, "payment_id": str}}

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

# Меню выбора суммы пополнения
amount_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="100 ₽", callback_data="amount_100")],
    [InlineKeyboardButton(text="500 ₽", callback_data="amount_500")],
    [InlineKeyboardButton(text="1000 ₽", callback_data="amount_1000")],
    [InlineKeyboardButton(text="2000 ₽", callback_data="amount_2000")],
    [InlineKeyboardButton(text="5000 ₽", callback_data="amount_5000")],
    [InlineKeyboardButton(text="❌ Своя сумма", callback_data="amount_custom")]
])

# Меню выбора способа оплаты (только Platiga)
def get_payment_methods_menu(amount: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 СБП / Криптовалюта (Platega)", callback_data=f"payment_platega_{amount}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_amount")]
    ])

# ========== FSM СОСТОЯНИЯ ==========
class AddProductStates(StatesGroup):
    waiting_name = State()
    waiting_price = State()

class AddKeysStates(StatesGroup):
    waiting_product_id = State()
    waiting_keys = State()

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
        "🤖 *Бот для продажи подписок LITE и VIP*\n\n"
        "💳 *Оплата:* Platega (СБП, Криптовалюта)\n\n"
        "📌 *Как пользоваться:*\n"
        "• Купите подписку через меню\n"
        "• После оплаты вы получите ключ и ссылку на группу\n\n"
        "📞 *КОНТАКТЫ:*\n"
        "• Техподдержка: @nikita1055\n"
        "• Основной канал: @keepersell\n"
        "• Отзывы: https://t.me/KeeperOtzivi\n\n"
        "⚖️ *ДОКУМЕНТЫ:*\n"
        "• [Политика конфиденциальности](https://telegra.ph/Politika-konfidencialnosti-04-01-26)\n"
        "• [Пользовательское соглашение](https://telegra.ph/Polzovatelskoe-soglashenie-04-01-19)"
    )
    
    # Инлайн кнопки для документов
    docs_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 Политика конфиденциальности", url="https://telegra.ph/Politika-konfidencialnosti-04-01-26")],
        [InlineKeyboardButton(text="📄 Пользовательское соглашение", url="https://telegra.ph/Polzovatelskoe-soglashenie-04-01-19")],
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="back_to_main")]
    ])
    
    await message.answer(
        info_text,
        parse_mode="Markdown",
        disable_web_page_preview=True,
        reply_markup=docs_kb
    )

@dp.callback_query(lambda c: c.data == "back_to_main")
async def back_to_main_callback(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.message.answer(
        "✨ *Главное меню*\n\nВыберите действие:",
        parse_mode="Markdown",
        reply_markup=main_menu
    )
    await callback.answer()

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

# ========== ПОПОЛНЕНИЕ БАЛАНСА ==========
@dp.message(lambda m: m.text == "💰 Пополнить баланс")
async def deposit_cmd(message: Message):
    await message.answer(
        "💰 *Пополнение баланса*\n\n"
        "Выберите сумму пополнения:",
        parse_mode="Markdown",
        reply_markup=amount_menu
    )

@dp.callback_query(lambda c: c.data and c.data.startswith("amount_"))
async def handle_amount_selection(callback: types.CallbackQuery, state: FSMContext):
    amount_str = callback.data.split("_")[1]
    
    if amount_str == "custom":
        await state.set_state(CustomAmountStates.waiting_amount)
        await callback.message.answer(
            "💰 Введите сумму пополнения (от 10 до 50000 ₽):\n\n"
            "Пример: `500`",
            parse_mode="Markdown"
        )
        await callback.answer()
        return
    
    amount = int(amount_str)
    await show_payment_methods(callback.message, amount)
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
        "Выберите удобный способ оплаты:",
        parse_mode="Markdown",
        reply_markup=get_payment_methods_menu(amount)
    )

@dp.callback_query(lambda c: c.data == "back_to_amount")
async def back_to_amount(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "💰 *Пополнение баланса*\n\nВыберите сумму пополнения:",
        parse_mode="Markdown",
        reply_markup=amount_menu
    )
    await callback.answer()

# ========== ГЕНЕРАЦИЯ ССЫЛКИ НА ОПЛАТУ (PLATEGA) ==========
@dp.callback_query(lambda c: c.data and c.data.startswith("payment_platega_"))
async def handle_platega_payment(callback: types.CallbackQuery):
    amount = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    
    # Создаем уникальный ID платежа
    payment_id = str(uuid.uuid4())
    pending_payments[user_id] = {
        "amount": amount,
        "payment_id": payment_id,
        "status": "pending"
    }
    
    # ЗДЕСЬ ТЫ ПОДСТАВЛЯЕШЬ API PLATEGA
    # Нужно заменить на реальный запрос к Platega API
    # Документация: https://platega.com/docs
    
    # ПРИМЕР ссылки (замени на реальную)
    payment_url = f"https://platega.com/pay?amount={amount}&payment_id={payment_id}&user_id={user_id}"
    
    await callback.message.answer(
        f"💳 *Оплата через Platega*\n\n"
        f"Сумма: `{amount} ₽`\n\n"
        f"🔗 [Нажмите для оплаты]({payment_url})\n\n"
        f"⚡ После оплаты баланс пополнится автоматически в течение 1-2 минут.\n\n"
        f"🆔 ID платежа: `{payment_id}`\n\n"
        f"Поддерживаемые способы: СБП, Криптовалюта",
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
    
    await callback.message.answer(
        f"✅ *Покупка успешна!*\n\n"
        f"🎮 Товар: {product['name']}\n"
        f"💰 Цена: {product['price']} ₽\n"
        f"🔑 Ключ: `{key_row['key_value']}`\n\n"
        f"💡 Сохраните ключ, он не будет показан снова!\n\n"
        f"🔗 Вступить в группу: @your_group_username",
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
        "Пример:\n`KEY-123-ABC`\n`KEY-456-DEF`\n\n"
        "Также можно указать ссылку на группу как ключ",
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

# ========== FLASK ВЕБХУК ДЛЯ PLATEGA ==========
@flask_app.route("/webhook/payment", methods=["POST"])
def payment_webhook():
    """
    Вебхук от Platega
    Адаптируй под реальный формат ответа от Platega
    """
    data = request.get_json()
    
    # ПРИМЕР (замени на реальный формат Platega)
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
