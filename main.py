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

# ========== ТВОИ АНИМИРОВАННЫЕ СТИКЕРЫ (ID) ==========
STICKERS = {
    "welcome": "5388795032775968174",
    "magic": "5474144592817318927",
    "click_below": "5872771279337033184",
    "shop_title": "5983399041197675256",
    "product_selected": "5854776233950188167",
    "keys_count": "6005570495603282482",
    "price_icon": "5807465992363710697",
    "select_payment": "5872771279337033184",
    "profile": "5870994129244131212",
    "id_icon": "5870813306826002498",
    "balance_icon": "5807465992363710697",
    "enter_amount": "5807465992363710697",
    "payment_method": "5807499888245612254",
    "info_title": "5870813306826002498",
    "official_bot": "5870813306826002498",
    "payment_icon": "5807499888245612254",
    "how_to_use": "5771695636411847302",
    "how_to_use2": "5771695636411847302",
}

def tg_emoji(sticker_id: str, fallback: str = "•") -> str:
    return f'<tg-emoji emoji-id="{sticker_id}">{fallback}</tg-emoji>'

# ========== ИНИЦИАЛИЗАЦИЯ ==========
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
flask_app = Flask(__name__)

pending_payments = {}

# ========== КЛАВИАТУРЫ ==========
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=f"{tg_emoji(STICKERS['shop_title'], '🛍')} Магазин"), KeyboardButton(text=f"{tg_emoji(STICKERS['profile'], '👤')} Профиль")],
        [KeyboardButton(text=f"{tg_emoji(STICKERS['info_title'], 'ℹ')} Информация")]
    ],
    resize_keyboard=True
)

profile_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=f"{tg_emoji(STICKERS['balance_icon'], '💰')} Пополнить баланс"), KeyboardButton(text=f"{tg_emoji(STICKERS['product_selected'], '📋')} История заказов")],
        [KeyboardButton(text="🏠 Главная")]
    ],
    resize_keyboard=True
)

admin_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Добавить товар"), KeyboardButton(text="🔑 Добавить ключи")],
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
    
    text = (
        f"{tg_emoji(STICKERS['welcome'], '✨')}\n\n"
        f"{tg_emoji(STICKERS['magic'], '✨')}\n\n"
        f"{tg_emoji(STICKERS['click_below'], '👇')}"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=main_menu)

@dp.message(lambda m: m.text and "Главная" in m.text)
async def back_to_main(message: Message):
    text = f"{tg_emoji(STICKERS['click_below'], '✨')} <b>Главное меню</b>"
    await message.answer(text, parse_mode="HTML", reply_markup=main_menu)

# ========== ИНФОРМАЦИЯ ==========
@dp.message(lambda m: m.text and "Информация" in m.text)
async def info_cmd(message: Message):
    info_text = (
        f"{tg_emoji(STICKERS['info_title'], 'ℹ')} <b>ИНФОРМАЦИЯ</b> {tg_emoji(STICKERS['info_title'], 'ℹ')}\n\n"
        f"{tg_emoji(STICKERS['official_bot'], '✨')} <b>Официальный бот по продаже ключей для чит клиента Magic</b>\n\n"
        f"{tg_emoji(STICKERS['payment_icon'], '💳')} <b>Оплата:</b> Platega (СБП, Криптовалюта)\n\n"
        f"{tg_emoji(STICKERS['how_to_use'], '📌')} <b>Как пользоваться:</b>\n"
        f"• Приобретите ключ через меню\n"
        f"• После оплаты вы получите ключ и доступ в VIP канал\n\n"
        f"📞 <b>КОНТАКТЫ:</b>\n"
        f"• Техподдержка: @nikita1055\n"
        f"• Основной канал: @keepersell\n"
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
        await message.answer(
            f"{tg_emoji(STICKERS['keys_count'], '📭')} <b>Товаров пока нет</b>",
            parse_mode="HTML"
        )
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{tg_emoji(STICKERS['product_selected'], '🎮')} {p['name']} | {p['price']}₽", callback_data=f"buy_{p['id']}")]
        for p in products
    ])
    
    await message.answer(
        f"{tg_emoji(STICKERS['shop_title'], '🛍')} <b>Выберите интересующий вас товар</b>",
        parse_mode="HTML",
        reply_markup=kb
    )

# ========== ПРОФИЛЬ ==========
@dp.message(lambda m: m.text and "Профиль" in m.text)
async def profile_cmd(message: Message):
    balance = await get_balance(message.from_user.id)
    text = (
        f"{tg_emoji(STICKERS['profile'], '👤')} <b>Профиль</b>\n\n"
        f"{tg_emoji(STICKERS['id_icon'], '🆔')} ID: <code>{message.from_user.id}</code>\n"
        f"{tg_emoji(STICKERS['balance_icon'], '💰')} Баланс: <code>{balance} ₽</code>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=profile_menu)

# ========== ИСТОРИЯ ЗАКАЗОВ ==========
@dp.message(lambda m: m.text and "История заказов" in m.text)
async def orders_history(message: Message):
    purchases = await get_user_purchases(message.from_user.id)
    
    if not purchases:
        await message.answer(
            f"{tg_emoji(STICKERS['keys_count'], '📋')} <b>История заказов</b>\n\nУ вас пока нет покупок.",
            parse_mode="HTML"
        )
        return
    
    history_text = f"{tg_emoji(STICKERS['product_selected'], '🎉')} <b>История заказов</b>\n\n"
    for p in purchases[:10]:
        history_text += f"🆔 Заказ #{p['id']}\n"
        history_text += f"{tg_emoji(STICKERS['magic'], '🎮')} Товар: {p['name']}\n"
        history_text += f"{tg_emoji(STICKERS['price_icon'], '💰')} Цена: {p['price']} ₽\n"
        history_text += f"📅 Дата: {p['created_at'].strftime('%d.%m.%Y %H:%M')}\n"
        history_text += "─" * 15 + "\n"
    
    await message.answer(history_text, parse_mode="HTML")

# ========== ПОПОЛНЕНИЕ БАЛАНСА ==========
@dp.message(lambda m: m.text and "Пополнить баланс" in m.text)
async def deposit_cmd(message: Message, state: FSMContext):
    await state.set_state(DepositStates.waiting_amount)
    await message.answer(
        f"{tg_emoji(STICKERS['enter_amount'], '💰')} <b>Укажите сумму пополнения баланса</b>\n\n"
        f"Введите сумму от 10 до 50000 ₽\nПример: <code>500</code>",
        parse_mode="HTML"
    )

@dp.message(DepositStates.waiting_amount)
async def process_deposit_amount(message: Message, state: FSMContext):
    try:
        amount = int(message.text.strip())
        if amount < 10 or amount > 50000:
            await message.answer(
                f"{tg_emoji(STICKERS['keys_count'], '❌')} Сумма от 10 до 50000",
                parse_mode="HTML"
            )
            return
        
        await state.update_data(amount=amount)
        
        payment_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{tg_emoji(STICKERS['payment_method'], '💳')} СБП / Криптовалюта (Platega)", callback_data=f"payment_platega_{amount}")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_payment")]
        ])
        
        await message.answer(
            f"{tg_emoji(STICKERS['payment_method'], '💰')} <b>Пополнение на {amount} ₽</b>\n\n{tg_emoji(STICKERS['select_payment'], '👇')} <b>Выберите способ оплаты</b>",
            parse_mode="HTML",
            reply_markup=payment_kb
        )
        await state.clear()
        
    except ValueError:
        await message.answer(
            f"{tg_emoji(STICKERS['keys_count'], '❌')} Введите <b>число</b>!\nПример: <code>500</code>",
            parse_mode="HTML"
        )

@dp.callback_query(lambda c: c.data == "cancel_payment")
async def cancel_payment(callback: types.CallbackQuery):
    await callback.message.delete()
    balance = await get_balance(callback.from_user.id)
    text = (
        f"{tg_emoji(STICKERS['profile'], '👤')} <b>Профиль</b>\n\n"
        f"{tg_emoji(STICKERS['id_icon'], '🆔')} ID: <code>{callback.from_user.id}</code>\n"
        f"{tg_emoji(STICKERS['balance_icon'], '💰')} Баланс: <code>{balance} ₽</code>"
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
        f"{tg_emoji(STICKERS['payment_method'], '💳')} <b>Оплата через Platega</b>\n\n"
        f"Сумма: <code>{amount} ₽</code>\n\n"
        f"🔗 <a href='{payment_url}'>Нажмите для оплаты</a>\n\n"
        f"⚡ После оплаты баланс пополнится автоматически.\n\n"
        f"🆔 ID платежа: <code>{payment_id}</code>",
        parse_mode="HTML",
        disable_web_page_preview=True
    )
    await callback.answer()

# ========== ПОКУПКА ТОВАРА ==========
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
        await callback.answer("❌ Ключи закончились")
        return
    
    await update_user_balance(user_id, balance - product["price"])
    await mark_key_as_used(key_row["id"])
    await add_purchase(user_id, product_id, product["price"])
    
    from database import pool
    async with pool.acquire() as conn:
        keys_left = await conn.fetchval("SELECT COUNT(*) FROM keys_store WHERE product_id = $1 AND used = FALSE", product_id)
    
    vip_link = "https://t.me/joinchat/AAAAAEAAAAAAAAAAAAAAAAAAAAA"
    
    await callback.message.answer(
        f"{tg_emoji(STICKERS['product_selected'], '✅')} <b>Выбран товар • {product['name']}</b>\n\n"
        f"{tg_emoji(STICKERS['keys_count'], '🔑')} <b>Ключей в наличии:</b> {keys_left}\n"
        f"{tg_emoji(STICKERS['price_icon'], '💰')} <b>Цена:</b> {product['price']} ₽\n\n"
        f"{tg_emoji(STICKERS['product_selected'], '🔑')} <b>Ваш ключ:</b> <code>{key_row['key_value']}</code>\n\n"
        f"🔗 <b>Ссылка на VIP канал:</b>\n"
        f"<a href='{vip_link}'>Нажмите для вступления</a>",
        parse_mode="HTML",
        disable_web_page_preview=True
    )
    await callback.answer("✅ Покупка успешна!")

# ========== АДМИН-КОМАНДЫ ==========
@dp.message(Command("admin"))
async def admin_cmd(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Доступ запрещен")
        return
    
    await message.answer(
        f"{tg_emoji(STICKERS['profile'], '🔐')} <b>Админ-панель</b>",
        parse_mode="HTML",
        reply_markup=admin_menu
    )

@dp.message(lambda m: m.text == "➕ Добавить товар")
async def add_product_cmd(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.set_state(AddProductStates.waiting_name)
    await message.answer("📝 Введите название товара:")

@dp.message(AddProductStates.waiting_name)
async def product_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AddProductStates.waiting_price)
    await message.answer("💰 Введите цену (число):")

@dp.message(AddProductStates.waiting_price)
async def product_price(message: Message, state: FSMContext):
    try:
        price = int(message.text)
        await state.update_data(price=price)
        await state.set_state(AddProductStates.waiting_keys)
        await message.answer("🔑 Введите ключи (каждый с новой строки):\n\nПример:\nKEY-123-ABC\nKEY-456-DEF")
    except ValueError:
        await message.answer("❌ Введите число")

@dp.message(AddProductStates.waiting_keys)
async def product_keys(message: Message, state: FSMContext):
    data = await state.get_data()
    keys = [k.strip() for k in message.text.split("\n") if k.strip()]
    if not keys:
        await message.answer("❌ Хотя бы один ключ")
        return
    
    product_id = await add_product(data["name"], data["price"])
    await add_keys_to_product(product_id, keys)
    await message.answer(f"✅ Товар добавлен! {len(keys)} ключей\n📦 ID товара: {product_id}")
    await state.clear()

@dp.message(lambda m: m.text == "🔑 Добавить ключи")
async def add_keys_cmd(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    products = await get_all_products()
    if not products:
        await message.answer("❌ Сначала добавьте товар командой ➕ Добавить товар")
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{p['name']} (ID: {p['id']})", callback_data=f"addkeys_{p['id']}")] for p in products
    ])
    await message.answer("📦 Выберите товар для добавления ключей:", reply_markup=kb)

@dp.callback_query(lambda c: c.data and c.data.startswith("addkeys_"))
async def select_for_keys(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔")
        return
    product_id = int(callback.data.split("_")[1])
    await state.update_data(product_id=product_id)
    await state.set_state(AddKeysStates.waiting_keys)
    await callback.message.answer("🔑 Введите ключи (по одному на строку):")
    await callback.answer()

@dp.message(AddKeysStates.waiting_keys)
async def process_keys_only(message: Message, state: FSMContext):
    data = await state.get_data()
    product_id = data["product_id"]
    keys = [k.strip() for k in message.text.split("\n") if k.strip()]
    await add_keys_to_product(product_id, keys)
    await message.answer(f"✅ Добавлено {len(keys)} ключей для товара ID {product_id}")
    await state.clear()

@dp.message(lambda m: m.text == "📊 Статистика")
async def stats_cmd(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    stats = await get_stats()
    await message.answer(
        f"📊 <b>Статистика</b>\n\n"
        f"👥 Пользователей: <code>{stats['users']}</code>\n"
        f"💰 Продаж на сумму: <code>{stats['total_sales']} ₽</code>\n"
        f"🔑 Выдано ключей: <code>{stats['keys_sold']}</code>\n"
        f"🔑 Осталось ключей: <code>{stats['keys_left']}</code>\n"
        f"📦 Товаров в продаже: <code>{stats['products_count']}</code>",
        parse_mode="HTML"
    )

# ========== FLASK ВЕБХУК ДЛЯ PLATEGA ==========
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
                f"{tg_emoji(STICKERS['product_selected'], '✅')} <b>Баланс пополнен!</b>\n\n"
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
