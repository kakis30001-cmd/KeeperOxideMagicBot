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
    mark_key_as_used, update_user_balance, add_purchase, get_user_purchases, get_stats
)

# ========== ID АНИМИРОВАННЫХ PREMIUM ЭМОДЗИ ==========
# (вставь свои ID, если хочешь другие)
EMOJI = {
    "fire": "5370680183571357151",      # 🔥 анимированный
    "sparkles": "5370680183571357152",   # ✨ анимированный
    "diamond": "5370680183571357153",    # 💎 анимированный
    "star": "5370680183571357154",       # 🌟 анимированный
    "party": "5370680183571357155",      # 🎉 анимированный
    "money": "5370680183571357156",      # 💰 анимированный
    "crown": "5370680183571357157",      # 👑 анимированный
    "rocket": "5370680183571357158",     # 🚀 анимированный
    "heart": "5370680183571357159",      # ❤️ анимированный
    "shop": "5370680183571357160",       # 🛍️ анимированный
    "profile": "5370680183571357161",    # 👤 анимированный
    "info": "5370680183571357162",       # ℹ️ анимированный
    "key": "5370680183571357163",        # 🔑 анимированный
    "success": "5370680183571357164",    # ✅ анимированный
    "error": "5370680183571357165",      # ❌ анимированный
    "support": "5370680183571357166",    # 📞 анимированный
    "rules": "5370680183571357167",      # 📜 анимированный
    "payment": "5370680183571357168",    # 💳 анимированный
    "vip": "5370680183571357169",        # 💎 VIP
    "magic": "5370680183571357170",      # ✨ магия
}

def emoji_tag(emoji_id: str, fallback: str = "😎") -> str:
    """Формирует HTML-тег для анимированного эмодзи"""
    return f"<emoji document_id='{emoji_id}'>{fallback}</emoji>"

# ========== ИНИЦИАЛИЗАЦИЯ ==========
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
flask_app = Flask(__name__)

# Хранилище ожидающих платежей
pending_payments = {}

# ========== КЛАВИАТУРЫ ==========
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=f"{emoji_tag(EMOJI['shop'], '🛍️')} Магазин"), KeyboardButton(text=f"{emoji_tag(EMOJI['profile'], '👤')} Профиль")],
        [KeyboardButton(text=f"{emoji_tag(EMOJI['info'], 'ℹ️')} Информация")]
    ],
    resize_keyboard=True
)

profile_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=f"{emoji_tag(EMOJI['money'], '💰')} Пополнить баланс"), KeyboardButton(text=f"{emoji_tag(EMOJI['party'], '🎉')} История заказов")],
        [KeyboardButton(text=f"{emoji_tag(EMOJI['home'], '🏠')} Главная")]
    ],
    resize_keyboard=True
)

# ========== FSM СОСТОЯНИЯ ==========
class AddProductStates(StatesGroup):
    waiting_name = State()
    waiting_price = State()
    waiting_keys = State()

class DepositStates(StatesGroup):
    waiting_amount = State()

# ========== КОМАНДЫ БОТА ==========
@dp.message(CommandStart())
async def start_cmd(message: Message):
    await add_user(message.from_user.id)
    
    text = (
        f"{emoji_tag(EMOJI['magic'], '✨')}{emoji_tag(EMOJI['sparkles'], '✨')}{emoji_tag(EMOJI['magic'], '✨')} "
        f"<b>Добро пожаловать в IceBerg Magic Cheat Shop</b> "
        f"{emoji_tag(EMOJI['magic'], '✨')}{emoji_tag(EMOJI['sparkles'], '✨')}{emoji_tag(EMOJI['magic'], '✨')}\n\n"
        f"Для покупки товаров используйте кнопки ниже ↓"
    )
    
    await message.answer(text, parse_mode="HTML", reply_markup=main_menu)

@dp.message(lambda m: m.text and "Главная" in m.text)
async def back_to_main(message: Message):
    text = (
        f"{emoji_tag(EMOJI['sparkles'], '✨')} <b>Главное меню</b> {emoji_tag(EMOJI['sparkles'], '✨')}\n\n"
        f"Выберите действие:"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=main_menu)

# ========== ИНФОРМАЦИЯ ==========
@dp.message(lambda m: m.text and "Информация" in m.text)
async def info_cmd(message: Message):
    info_text = (
        f"{emoji_tag(EMOJI['info'], 'ℹ️')} <b>ИНФОРМАЦИЯ</b> {emoji_tag(EMOJI['info'], 'ℹ️')}\n\n"
        f"{emoji_tag(EMOJI['magic'], '✨')} <b>Официальный бот по продаже ключей для чит клиента Magic</b>\n\n"
        f"{emoji_tag(EMOJI['payment'], '💳')} <b>Оплата:</b> Platega (СБП, Криптовалюта)\n\n"
        f"<b>📌 Как пользоваться:</b>\n"
        f"• Приобретите ключ через меню\n"
        f"• После оплаты вы получите ключ и доступ в VIP канал\n\n"
        f"{emoji_tag(EMOJI['support'], '📞')} <b>КОНТАКТЫ:</b>\n"
        f"• Техподдержка: @nikita1055\n"
        f"• Основной канал: @keepersell\n"
        f"• Отзывы: https://t.me/KeeperOtzivi\n\n"
        f"{emoji_tag(EMOJI['rules'], '⚖️')} <b>ДОКУМЕНТЫ:</b>\n"
        f"• <a href='https://telegra.ph/Politika-konfidencialnosti-04-01-26'>Политика конфиденциальности</a>\n"
        f"• <a href='https://telegra.ph/Polzovatelskoe-soglashenie-04-01-19'>Пользовательское соглашение</a>"
    )
    
    await message.answer(info_text, parse_mode="HTML", disable_web_page_preview=True)

# ========== МАГАЗИН ==========
@dp.message(lambda m: m.text and "Магазин" in m.text)
async def shop_cmd(message: Message):
    products = await get_all_products()
    if not products:
        await message.answer(
            f"{emoji_tag(EMOJI['error'], '📭')} <b>Товаров пока нет</b>\n\nОжидайте пополнения ассортимента.",
            parse_mode="HTML"
        )
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{emoji_tag(EMOJI['key'], '🎮')} {p['name']} | {p['price']}₽", callback_data=f"buy_{p['id']}")]
        for p in products
    ])
    
    await message.answer(
        f"{emoji_tag(EMOJI['shop'], '🛍️')} <b>Выберите нужный товар</b>\n\n"
        f"Нажмите на кнопку с товаром для покупки:",
        parse_mode="HTML",
        reply_markup=kb
    )

# ========== ПРОФИЛЬ ==========
@dp.message(lambda m: m.text and "Профиль" in m.text)
async def profile_cmd(message: Message):
    balance = await get_balance(message.from_user.id)
    text = (
        f"{emoji_tag(EMOJI['profile'], '👤')} <b>Профиль</b>\n\n"
        f"📛 Имя: {message.from_user.full_name}\n"
        f"🆔 ID: <code>{message.from_user.id}</code>\n"
        f"{emoji_tag(EMOJI['money'], '💰')} Ваш баланс: <code>{balance} ₽</code>\n\n"
        f"Выберите действие в меню ниже:"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=profile_menu)

@dp.message(lambda m: m.text and "История заказов" in m.text)
async def orders_history(message: Message):
    purchases = await get_user_purchases(message.from_user.id)
    
    if not purchases:
        await message.answer(
            f"{emoji_tag(EMOJI['error'], '📋')} <b>История заказов</b>\n\n"
            f"У вас пока нет покупок.",
            parse_mode="HTML"
        )
        return
    
    history_text = f"{emoji_tag(EMOJI['party'], '📋')} <b>История заказов</b>\n\n"
    for p in purchases:
        history_text += f"🆔 Заказ #{p['id']}\n"
        history_text += f"{emoji_tag(EMOJI['key'], '🎮')} Товар: {p['name']}\n"
        history_text += f"{emoji_tag(EMOJI['money'], '💰')} Цена: {p['price']} ₽\n"
        history_text += f"📅 Дата: {p['created_at'].strftime('%d.%m.%Y %H:%M')}\n"
        history_text += "─" * 15 + "\n"
    
    await message.answer(history_text, parse_mode="HTML")

# ========== ПОПОЛНЕНИЕ БАЛАНСА ==========
@dp.message(lambda m: m.text and "Пополнить баланс" in m.text)
async def deposit_cmd(message: Message, state: FSMContext):
    await state.set_state(DepositStates.waiting_amount)
    await message.answer(
        f"{emoji_tag(EMOJI['money'], '💰')} <b>Пополнение баланса</b>\n\n"
        f"Введите сумму пополнения (от 10 до 50000 ₽):\n\n"
        f"Пример: <code>500</code>",
        parse_mode="HTML"
    )

@dp.message(DepositStates.waiting_amount)
async def process_deposit_amount(message: Message, state: FSMContext):
    try:
        amount = int(message.text.strip())
        if amount < 10:
            await message.answer(
                f"{emoji_tag(EMOJI['error'], '❌')} Минимальная сумма пополнения: <b>10 ₽</b>\n\nВведите другую сумму:",
                parse_mode="HTML"
            )
            return
        if amount > 50000:
            await message.answer(
                f"{emoji_tag(EMOJI['error'], '❌')} Максимальная сумма пополнения: <b>50000 ₽</b>\n\nВведите другую сумму:",
                parse_mode="HTML"
            )
            return
        
        await state.update_data(amount=amount)
        
        payment_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{emoji_tag(EMOJI['payment'], '💳')} СБП / Криптовалюта (Platega)", callback_data=f"payment_platega_{amount}")],
            [InlineKeyboardButton(text=f"{emoji_tag(EMOJI['error'], '❌')} Отмена", callback_data="cancel_payment")]
        ])
        
        await message.answer(
            f"{emoji_tag(EMOJI['money'], '💰')} <b>Пополнение на {amount} ₽</b>\n\n"
            f"Выберите способ оплаты:",
            parse_mode="HTML",
            reply_markup=payment_kb
        )
        await state.clear()
        
    except ValueError:
        await message.answer(
            f"{emoji_tag(EMOJI['error'], '❌')} Введите <b>число</b>!\n\nПример: <code>500</code>",
            parse_mode="HTML"
        )

@dp.callback_query(lambda c: c.data == "cancel_payment")
async def cancel_payment(callback: types.CallbackQuery):
    await callback.message.delete()
    balance = await get_balance(callback.from_user.id)
    text = (
        f"{emoji_tag(EMOJI['profile'], '👤')} <b>Профиль</b>\n\n"
        f"📛 Имя: {callback.from_user.full_name}\n"
        f"🆔 ID: <code>{callback.from_user.id}</code>\n"
        f"{emoji_tag(EMOJI['money'], '💰')} Ваш баланс: <code>{balance} ₽</code>\n\n"
        f"Выберите действие в меню ниже:"
    )
    await callback.message.answer(text, parse_mode="HTML", reply_markup=profile_menu)
    await callback.answer()

# ========== ОПЛАТА PLATEGA ==========
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
    
    await callback.message.edit_text(
        f"{emoji_tag(EMOJI['payment'], '💳')} <b>Оплата через Platega</b>\n\n"
        f"Сумма: <code>{amount} ₽</code>\n\n"
        f"🔗 <a href='{payment_url}'>Нажмите для оплаты</a>\n\n"
        f"{emoji_tag(EMOJI['sparkles'], '⚡')} После оплаты баланс пополнится автоматически.\n\n"
        f"🆔 ID платежа: <code>{payment_id}</code>\n\n"
        f"Способы оплаты: СБП, Криптовалюта",
        parse_mode="HTML",
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
    
    await update_user_balance(user_id, balance - product["price"])
    await mark_key_as_used(key_row["id"])
    await add_purchase(user_id, product_id, product["price"])
    
    vip_link = "https://t.me/joinchat/AAAAAEAAAAAAAAAAAAAAAAAAAAA"
    
    await callback.message.answer(
        f"{emoji_tag(EMOJI['success'], '✅')} <b>Покупка успешна!</b>\n\n"
        f"{emoji_tag(EMOJI['key'], '🎮')} Товар: {product['name']}\n"
        f"{emoji_tag(EMOJI['money'], '💰')} Цена: {product['price']} ₽\n"
        f"{emoji_tag(EMOJI['key'], '🔑')} <b>Ключ:</b> <code>{key_row['key_value']}</code>\n\n"
        f"{emoji_tag(EMOJI['vip'], '🔗')} <b>Ссылка на VIP канал:</b>\n"
        f"<a href='{vip_link}'>Нажмите для вступления</a>\n\n"
        f"{emoji_tag(EMOJI['sparkles'], '💡')} Сохраните ключ, он не будет показан снова!",
        parse_mode="HTML",
        disable_web_page_preview=True
    )
    await callback.answer(f"{emoji_tag(EMOJI['party'], '🎉')} Спасибо за покупку!")

# ========== АДМИН-КОМАНДЫ ==========
@dp.message(Command("admin"))
async def admin_cmd(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer(f"{emoji_tag(EMOJI['error'], '⛔')} <b>Доступ запрещен</b>", parse_mode="HTML")
        return
    
    admin_menu = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Добавить товар"), KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="🏠 Главная")]
        ],
        resize_keyboard=True
    )
    await message.answer(
        f"{emoji_tag(EMOJI['crown'], '🔐')} <b>Админ-панель</b>\n\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=admin_menu
    )

@dp.message(lambda m: m.text == "➕ Добавить товар")
async def add_product_cmd(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.set_state(AddProductStates.waiting_name)
    await message.answer(
        f"{emoji_tag(EMOJI['key'], '📝')} Введите <b>название товара</b>:",
        parse_mode="HTML"
    )

@dp.message(AddProductStates.waiting_name)
async def product_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AddProductStates.waiting_price)
    await message.answer(
        f"{emoji_tag(EMOJI['money'], '💰')} Введите <b>цену</b> (число):",
        parse_mode="HTML"
    )

@dp.message(AddProductStates.waiting_price)
async def product_price(message: Message, state: FSMContext):
    try:
        price = int(message.text)
        await state.update_data(price=price)
        await state.set_state(AddProductStates.waiting_keys)
        await message.answer(
            f"{emoji_tag(EMOJI['key'], '🔑')} Введите <b>ключи</b> (каждый с новой строки):\n\n"
            f"Пример:\n<code>KEY-123-ABC</code>\n<code>KEY-456-DEF</code>\n\n"
            f"Сколько ключей введете — столько и будет в наличии.",
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer(
            f"{emoji_tag(EMOJI['error'], '❌')} Введите <b>число</b>!",
            parse_mode="HTML"
        )

@dp.message(AddProductStates.waiting_keys)
async def product_keys(message: Message, state: FSMContext):
    data = await state.get_data()
    name = data["name"]
    price = data["price"]
    
    keys = [k.strip() for k in message.text.split("\n") if k.strip()]
    
    if not keys:
        await message.answer(
            f"{emoji_tag(EMOJI['error'], '❌')} Необходимо ввести хотя бы один ключ!",
            parse_mode="HTML"
        )
        return
    
    product_id = await add_product(name, price)
    await add_keys_to_product(product_id, keys)
    
    await message.answer(
        f"{emoji_tag(EMOJI['success'], '✅')} <b>Товар добавлен!</b>\n\n"
        f"📛 Название: {name}\n"
        f"{emoji_tag(EMOJI['money'], '💰')} Цена: {price} ₽\n"
        f"{emoji_tag(EMOJI['key'], '🔑')} Количество ключей: {len(keys)}\n\n"
        f"📦 ID товара: {product_id}",
        parse_mode="HTML"
    )
    await state.clear()

@dp.message(lambda m: m.text == "📊 Статистика")
async def stats_cmd(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    stats = await get_stats()
    
    await message.answer(
        f"{emoji_tag(EMOJI['star'], '📊')} <b>Статистика</b>\n\n"
        f"👥 Пользователей: <code>{stats['users']}</code>\n"
        f"{emoji_tag(EMOJI['money'], '💰')} Продаж на сумму: <code>{stats['total_sales']} ₽</code>\n"
        f"{emoji_tag(EMOJI['key'], '🔑')} Выдано ключей: <code>{stats['keys_sold']}</code>\n"
        f"{emoji_tag(EMOJI['key'], '🔑')} Осталось ключей: <code>{stats['keys_left']}</code>\n"
        f"📦 Товаров в продаже: <code>{stats['products_count']}</code>",
        parse_mode="HTML"
    )

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
                f"{emoji_tag(EMOJI['success'], '✅')} <b>Баланс пополнен!</b>\n\n"
                f"Сумма: <code>{amount} ₽</code>\n"
                f"Новый баланс: <code>{current + amount} ₽</code>",
                parse_mode="HTML"
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
