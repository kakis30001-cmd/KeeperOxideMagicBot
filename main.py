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

# ========== ID АНИМИРОВАННЫХ ПРЕМИУМ ЭМОДЗИ ==========
# ЗАМЕНИ НА СВОИ РЕАЛЬНЫЕ ID (получи через @getidsbot)
EMOJI_IDS = {
    "fire": "5370680183571357151",
    "sparkles": "5370680183571357152",
    "diamond": "5370680183571357153",
    "star": "5370680183571357154",
    "party": "5370680183571357155",
    "money": "5370680183571357156",
    "crown": "5370680183571357157",
    "rocket": "5370680183571357158",
    "heart": "5370680183571357159",
    "shop": "5370680183571357160",
    "profile": "5370680183571357161",
    "info": "5370680183571357162",
    "key": "5370680183571357163",
    "success": "5370680183571357164",
    "error": "5370680183571357165",
    "support": "5370680183571357166",
    "rules": "5370680183571357167",
    "payment": "5370680183571357168",
    "vip": "5370680183571357169",
    "magic": "5370680183571357170",
    "home": "5370680183571357171",
}

def tg_emoji(emoji_id: str, fallback: str = "•") -> str:
    """Правильный HTML-тег для анимированных эмодзи"""
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'

# ========== ИНИЦИАЛИЗАЦИЯ ==========
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
flask_app = Flask(__name__)

pending_payments = {}

# ========== КЛАВИАТУРЫ ==========
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🛍 Магазин"), KeyboardButton(text="👤 Профиль")],
        [KeyboardButton(text="ℹ Информация")]
    ],
    resize_keyboard=True
)

profile_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💰 Пополнить"), KeyboardButton(text="📋 История")],
        [KeyboardButton(text="🏠 Главная")]
    ],
    resize_keyboard=True
)

admin_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Товар"), KeyboardButton(text="🔑 Ключи")],
        [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="🏠 Главная")]
    ],
    resize_keyboard=True
)

# ========== FSM ==========
class AddProductStates(StatesGroup):
    waiting_name = State()
    waiting_price = State()
    waiting_keys = State()

class AddKeysStates(StatesGroup):
    waiting_product_id = State()
    waiting_keys = State()

class DepositStates(StatesGroup):
    waiting_amount = State()

# ========== КОМАНДЫ ==========
@dp.message(CommandStart())
async def start_cmd(message: Message):
    await add_user(message.from_user.id)
    
    sparkles = tg_emoji(EMOJI_IDS["sparkles"], "✨")
    magic = tg_emoji(EMOJI_IDS["magic"], "✨")
    
    text = (
        f"{magic}{sparkles}{magic} "
        f"<b>Добро пожаловать в Magic Shop</b> "
        f"{magic}{sparkles}{magic}\n\n"
        f"Нажми <b>Магазин</b> для покупки ключей"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=main_menu)

@dp.message(lambda m: m.text and "Главная" in m.text)
async def back_to_main(message: Message):
    sparkles = tg_emoji(EMOJI_IDS["sparkles"], "✨")
    text = f"{sparkles} <b>Главное меню</b>"
    await message.answer(text, parse_mode="HTML", reply_markup=main_menu)

# ========== ИНФОРМАЦИЯ ==========
@dp.message(lambda m: m.text and "Информация" in m.text)
async def info_cmd(message: Message):
    info_text = (
        f"ℹ <b>ИНФОРМАЦИЯ</b> ℹ\n\n"
        f"✨ <b>Официальный бот по продаже ключей для Magic</b>\n\n"
        f"💳 <b>Оплата:</b> Platega (СБП, Криптовалюта)\n\n"
        f"<b>📌 Как пользоваться:</b>\n"
        f"• Приобретите ключ через меню\n\n"
        f"📞 <b>КОНТАКТЫ:</b>\n"
        f"• Техподдержка: @nikita1055\n"
        f"• Канал: @keepersell\n"
        f"• Отзывы: https://t.me/KeeperOtzivi\n\n"
        f"⚖ <b>ДОКУМЕНТЫ:</b>\n"
        f"• <a href='https://telegra.ph/Politika-konfidencialnosti-04-01-26'>Политика конфиденциальности</a>\n"
        f"• <a href='https://telegra.ph/Polzovatelskoe-soglashenie-04-01-19'>Пользовательское соглашение</a>"
    )
    await message.answer(info_text, parse_mode="HTML", disable_web_page_preview=True)

# ========== МАГАЗИН ==========
@dp.message(lambda m: m.text and "Магазин" in m.text)
async def shop_cmd(message: Message):
    products = await get_all_products()
    if not products:
        await message.answer("📭 <b>Товаров пока нет</b>", parse_mode="HTML")
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🔑 {p['name']} | {p['price']}₽", callback_data=f"buy_{p['id']}")]
        for p in products
    ])
    
    await message.answer(
        f"🛍 <b>Выберите товар</b>",
        parse_mode="HTML",
        reply_markup=kb
    )

# ========== ПРОФИЛЬ ==========
@dp.message(lambda m: m.text and "Профиль" in m.text)
async def profile_cmd(message: Message):
    balance = await get_balance(message.from_user.id)
    money = tg_emoji(EMOJI_IDS["money"], "💰")
    text = (
        f"👤 <b>Профиль</b>\n\n"
        f"Имя: {message.from_user.full_name}\n"
        f"ID: <code>{message.from_user.id}</code>\n"
        f"{money} Баланс: <code>{balance} ₽</code>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=profile_menu)

# ========== ИСТОРИЯ ==========
@dp.message(lambda m: m.text and "История" in m.text)
async def orders_history(message: Message):
    purchases = await get_user_purchases(message.from_user.id)
    if not purchases:
        await message.answer("📋 <b>История пуста</b>", parse_mode="HTML")
        return
    
    party = tg_emoji(EMOJI_IDS["party"], "🎉")
    text = f"{party} <b>История заказов</b>\n\n"
    for p in purchases[:10]:
        text += f"#{p['id']} | {p['name']} | {p['price']}₽ | {p['created_at'].strftime('%d.%m.%y')}\n"
    await message.answer(text, parse_mode="HTML")

# ========== ПОПОЛНЕНИЕ ==========
@dp.message(lambda m: m.text and "Пополнить" in m.text)
async def deposit_cmd(message: Message, state: FSMContext):
    await state.set_state(DepositStates.waiting_amount)
    money = tg_emoji(EMOJI_IDS["money"], "💰")
    await message.answer(
        f"{money} <b>Сумма пополнения:</b>\n\n"
        f"Введите число от 10 до 50000\nПример: <code>500</code>",
        parse_mode="HTML"
    )

@dp.message(DepositStates.waiting_amount)
async def process_deposit_amount(message: Message, state: FSMContext):
    try:
        amount = int(message.text.strip())
        if amount < 10 or amount > 50000:
            error = tg_emoji(EMOJI_IDS["error"], "❌")
            await message.answer(f"{error} Сумма от 10 до 50000", parse_mode="HTML")
            return
        
        await state.update_data(amount=amount)
        payment_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Platega (СБП/Крипта)", callback_data=f"pay_{amount}")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_pay")]
        ])
        money = tg_emoji(EMOJI_IDS["money"], "💰")
        await message.answer(
            f"{money} <b>Пополнение {amount}₽</b>\nВыбери способ:",
            parse_mode="HTML",
            reply_markup=payment_kb
        )
        await state.clear()
    except ValueError:
        error = tg_emoji(EMOJI_IDS["error"], "❌")
        await message.answer(f"{error} Введи число", parse_mode="HTML")

@dp.callback_query(lambda c: c.data == "cancel_pay")
async def cancel_pay(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.answer("Отменено")

@dp.callback_query(lambda c: c.data and c.data.startswith("pay_"))
async def handle_pay(callback: types.CallbackQuery):
    amount = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    payment_id = str(uuid.uuid4())
    pending_payments[user_id] = {"amount": amount, "payment_id": payment_id}
    
    # ЗАМЕНИ НА РЕАЛЬНУЮ ССЫЛКУ PLATEGA
    url = f"https://platega.com/pay?amount={amount}&user_id={user_id}&payment_id={payment_id}"
    sparkles = tg_emoji(EMOJI_IDS["sparkles"], "⚡")
    
    await callback.message.edit_text(
        f"💳 <b>Оплата {amount}₽</b>\n\n"
        f"🔗 <a href='{url}'>Нажми для оплаты</a>\n\n"
        f"ID: <code>{payment_id}</code>\n\n"
        f"{sparkles} После оплаты баланс пополнится автоматически",
        parse_mode="HTML",
        disable_web_page_preview=True
    )
    await callback.answer()

# ========== ПОКУПКА ==========
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
        await callback.answer(f"❌ Нужно {product['price']}₽")
        return
    
    key_row = await get_unused_key(product_id)
    if not key_row:
        await callback.answer("❌ Ключи закончились")
        return
    
    await update_user_balance(user_id, balance - product["price"])
    await mark_key_as_used(key_row["id"])
    await add_purchase(user_id, product_id, product["price"])
    
    success = tg_emoji(EMOJI_IDS["success"], "✅")
    party = tg_emoji(EMOJI_IDS["party"], "🎉")
    
    await callback.message.answer(
        f"{success} <b>Покупка успешна!</b>\n\n"
        f"Товар: {product['name']}\n"
        f"Цена: {product['price']}₽\n"
        f"🔑 <code>{key_row['key_value']}</code>\n\n"
        f"👉 <a href='https://t.me/joinchat/...'>VIP канал</a>",
        parse_mode="HTML"
    )
    await callback.answer(f"{party} Спасибо!")

# ========== АДМИН ==========
@dp.message(Command("admin"))
async def admin_cmd(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Доступ закрыт")
        return
    crown = tg_emoji(EMOJI_IDS["crown"], "🔐")
    await message.answer(f"{crown} Админ-панель", reply_markup=admin_menu)

@dp.message(lambda m: m.text == "➕ Товар")
async def add_product_cmd(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.set_state(AddProductStates.waiting_name)
    await message.answer("📝 Название товара:")

@dp.message(AddProductStates.waiting_name)
async def product_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AddProductStates.waiting_price)
    await message.answer("💰 Цена (число):")

@dp.message(AddProductStates.waiting_price)
async def product_price(message: Message, state: FSMContext):
    try:
        price = int(message.text)
        await state.update_data(price=price)
        await state.set_state(AddProductStates.waiting_keys)
        await message.answer("🔑 Ключи (каждый с новой строки):")
    except ValueError:
        await message.answer("❌ Введи число")

@dp.message(AddProductStates.waiting_keys)
async def product_keys(message: Message, state: FSMContext):
    data = await state.get_data()
    keys = [k.strip() for k in message.text.split("\n") if k.strip()]
    if not keys:
        await message.answer("❌ Хотя бы один ключ")
        return
    
    product_id = await add_product(data["name"], data["price"])
    await add_keys_to_product(product_id, keys)
    success = tg_emoji(EMOJI_IDS["success"], "✅")
    await message.answer(f"{success} Товар добавлен! {len(keys)} ключей")
    await state.clear()

@dp.message(lambda m: m.text == "🔑 Ключи")
async def add_keys_only(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    products = await get_all_products()
    if not products:
        await message.answer("❌ Сначала добавь товар")
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=p['name'], callback_data=f"addkeys_{p['id']}")] for p in products
    ])
    await message.answer("Выбери товар:", reply_markup=kb)

@dp.callback_query(lambda c: c.data and c.data.startswith("addkeys_"))
async def select_for_keys(callback: types.CallbackQuery, state: FSMContext):
    product_id = int(callback.data.split("_")[1])
    await state.update_data(product_id=product_id)
    await state.set_state(AddKeysStates.waiting_keys)
    await callback.message.answer("🔑 Введи ключи (по одному на строку):")
    await callback.answer()

@dp.message(AddKeysStates.waiting_keys)
async def process_keys_only(message: Message, state: FSMContext):
    data = await state.get_data()
    product_id = data["product_id"]
    keys = [k.strip() for k in message.text.split("\n") if k.strip()]
    await add_keys_to_product(product_id, keys)
    success = tg_emoji(EMOJI_IDS["success"], "✅")
    await message.answer(f"{success} Добавлено {len(keys)} ключей")
    await state.clear()

@dp.message(lambda m: m.text == "📊 Статистика")
async def stats_cmd(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    stats = await get_stats()
    star = tg_emoji(EMOJI_IDS["star"], "📊")
    await message.answer(
        f"{star} Статистика\n\n"
        f"👥 Пользователей: {stats['users']}\n"
        f"💰 Продаж: {stats['total_sales']}₽\n"
        f"🔑 Выдано: {stats['keys_sold']}\n"
        f"🔑 Осталось: {stats['keys_left']}",
        parse_mode="HTML"
    )

# ========== ВЕБХУК ДЛЯ PLATEGA ==========
@flask_app.route("/webhook/payment", methods=["POST"])
def payment_webhook():
    data = request.get_json()
    user_id = data.get("user_id")
    amount = data.get("amount")
    status = data.get("status")
    
    if status == "success" and user_id and amount:
        async def upd():
            current = await get_balance(user_id)
            await update_user_balance(user_id, current + amount)
            success = tg_emoji(EMOJI_IDS["success"], "✅")
            await bot.send_message(
                user_id,
                f"{success} Баланс пополнен на {amount}₽",
                parse_mode="HTML"
            )
        asyncio.run(upd())
        return jsonify({"status": "ok"}), 200
    return jsonify({"status": "error"}), 400

@flask_app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "alive"}), 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host="0.0.0.0", port=port)

async def main():
    await connect_db()
    await bot.delete_webhook(drop_pending_updates=True)
    Thread(target=run_flask, daemon=True).start()
    print("✅ Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
