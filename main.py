import asyncio
import os
import uuid
import hashlib
from threading import Thread
from flask import Flask, request, jsonify
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
import aiohttp

from config import BOT_TOKEN, ADMIN_ID, DB_URL, RAILWAY_URL
from database import (
    connect_db, add_user, get_balance, get_all_products,
    add_product, add_keys_to_product, get_unused_key,
    mark_key_as_used, update_user_balance, add_purchase, get_user_purchases, get_stats,
    get_all_users, create_promocode, get_promocode, use_promocode, check_promocode_used,
    get_all_promocodes, delete_promocode, add_vip_link, get_active_vip_link, get_all_vip_links, deactivate_vip_link
)

CHANNEL_ID = -1003709565134

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
}

BUTTON_EMOJI = {
    "shop": "5983399041197675256",
    "profile": "5870994129244131212",
    "info": "5870813306826002498",
    "balance": "5807465992363710697",
    "history": "5854776233950188167",
    "home": "5872771279337033184",
    "back": "5872771279337033184",
    "add_product": "5983399041197675256",
    "add_keys": "6005570495603282482",
    "stats": "5807499888245612254",
    "add_balance": "5807465992363710697",
    "broadcast": "5872771279337033184",
    "promocode": "5872771279337033184",
    "vip_link": "5872771279337033184",
}

def tg_emoji(sticker_id: str, fallback: str = "") -> str:
    return f'<tg-emoji emoji-id="{sticker_id}">{fallback}</tg-emoji>'

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
flask_app = Flask(__name__)

pending_payments = {}

class AddProductStates(StatesGroup):
    waiting_name = State()
    waiting_price = State()
    waiting_keys = State()

class AddKeysStates(StatesGroup):
    waiting_product_id = State()
    waiting_keys = State()

class DepositStates(StatesGroup):
    waiting_amount = State()

class AdminAddBalanceStates(StatesGroup):
    waiting_user_id = State()
    waiting_amount = State()

class AdminBroadcastStates(StatesGroup):
    waiting_message = State()

class AdminCreatePromocodeStates(StatesGroup):
    waiting_code = State()
    waiting_type = State()
    waiting_value = State()
    waiting_max_uses = State()

class ProfileActivatePromocodeStates(StatesGroup):
    waiting_code = State()

class AdminVipLinkStates(StatesGroup):
    waiting_action = State()

async def create_platega_payment(amount: int, payment_id: str, user_id: int) -> str:
    return None

def get_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Магазин", callback_data="menu_shop", icon_custom_emoji_id=BUTTON_EMOJI["shop"]),
            InlineKeyboardButton(text="Профиль", callback_data="menu_profile", icon_custom_emoji_id=BUTTON_EMOJI["profile"])
        ],
        [
            InlineKeyboardButton(text="Информация", callback_data="menu_info", icon_custom_emoji_id=BUTTON_EMOJI["info"])
        ]
    ])

def get_profile_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Пополнить баланс", callback_data="profile_deposit", icon_custom_emoji_id=BUTTON_EMOJI["balance"]),
            InlineKeyboardButton(text="История заказов", callback_data="profile_history", icon_custom_emoji_id=BUTTON_EMOJI["history"])
        ],
        [
            InlineKeyboardButton(text="Активировать промокод", callback_data="profile_activate_promocode", icon_custom_emoji_id=BUTTON_EMOJI["promocode"])
        ],
        [
            InlineKeyboardButton(text="Главное меню", callback_data="menu_main", icon_custom_emoji_id=BUTTON_EMOJI["home"])
        ]
    ])

def get_admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Добавить товар", callback_data="admin_add_product", icon_custom_emoji_id=BUTTON_EMOJI["add_product"]),
            InlineKeyboardButton(text="Добавить ключи", callback_data="admin_add_keys", icon_custom_emoji_id=BUTTON_EMOJI["add_keys"])
        ],
        [
            InlineKeyboardButton(text="Выдать баланс", callback_data="admin_add_balance", icon_custom_emoji_id=BUTTON_EMOJI["add_balance"]),
            InlineKeyboardButton(text="Сделать рассылку", callback_data="admin_broadcast", icon_custom_emoji_id=BUTTON_EMOJI["broadcast"])
        ],
        [
            InlineKeyboardButton(text="Создать промокод", callback_data="admin_create_promocode", icon_custom_emoji_id=BUTTON_EMOJI["promocode"]),
            InlineKeyboardButton(text="Список промокодов", callback_data="admin_list_promocodes", icon_custom_emoji_id=BUTTON_EMOJI["promocode"])
        ],
        [
            InlineKeyboardButton(text="Создать ссылку VIP", callback_data="admin_create_vip_link", icon_custom_emoji_id=BUTTON_EMOJI["vip_link"]),
            InlineKeyboardButton(text="Список VIP ссылок", callback_data="admin_list_vip_links", icon_custom_emoji_id=BUTTON_EMOJI["vip_link"])
        ],
        [
            InlineKeyboardButton(text="Статистика", callback_data="admin_stats", icon_custom_emoji_id=BUTTON_EMOJI["stats"]),
            InlineKeyboardButton(text="Главное меню", callback_data="menu_main", icon_custom_emoji_id=BUTTON_EMOJI["home"])
        ]
    ])

@dp.message(CommandStart())
async def start_cmd(message: Message):
    await add_user(message.from_user.id)
    
    text = (
        f"{tg_emoji(STICKERS['welcome'], '✨')} <b>Добро пожаловать в KeeperShop</b>\n\n"
        f"{tg_emoji(STICKERS['magic'], '✨')} <b>Официальный магазин ключей Magic</b>\n\n"
        f"{tg_emoji(STICKERS['click_below'], '👇')} <b>Для покупки товаров используйте кнопки ниже</b>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())

@dp.callback_query(lambda c: c.data == "menu_main")
async def menu_main(callback: CallbackQuery):
    text = f"{tg_emoji(STICKERS['click_below'], '✨')} <b>Главное меню</b>\n\nВыберите действие:"
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_main_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_info")
async def menu_info(callback: CallbackQuery):
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
    await callback.message.edit_text(info_text, parse_mode="HTML", disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="menu_main", icon_custom_emoji_id=BUTTON_EMOJI["back"])]]))
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_shop")
async def menu_shop(callback: CallbackQuery):
    products = await get_all_products()
    if not products:
        await callback.message.edit_text(
            f"{tg_emoji(STICKERS['keys_count'], '📭')} <b>Товаров пока нет</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="menu_main", icon_custom_emoji_id=BUTTON_EMOJI["back"])]])
        )
        await callback.answer()
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{p['name']} | {p['price']}₽", callback_data=f"buy_{p['id']}")]
        for p in products
    ] + [[InlineKeyboardButton(text="Назад", callback_data="menu_main", icon_custom_emoji_id=BUTTON_EMOJI["back"])]])
    
    await callback.message.edit_text(
        f"{tg_emoji(STICKERS['shop_title'], '🛍')} <b>Выберите интересующий вас товар</b>",
        parse_mode="HTML",
        reply_markup=kb
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_profile")
async def menu_profile(callback: CallbackQuery):
    balance = await get_balance(callback.from_user.id)
    text = (
        f"{tg_emoji(STICKERS['profile'], '👤')} <b>Профиль</b>\n\n"
        f"{tg_emoji(STICKERS['id_icon'], '🆔')} ID: <code>{callback.from_user.id}</code>\n"
        f"{tg_emoji(STICKERS['balance_icon'], '💰')} Баланс: <code>{balance} ₽</code>"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_profile_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "profile_history")
async def profile_history(callback: CallbackQuery):
    purchases = await get_user_purchases(callback.from_user.id)
    
    if not purchases:
        await callback.message.edit_text(
            f"{tg_emoji(STICKERS['keys_count'], '📋')} <b>История заказов</b>\n\nУ вас пока нет покупок.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="menu_profile", icon_custom_emoji_id=BUTTON_EMOJI["back"])]])
        )
        await callback.answer()
        return
    
    history_text = f"{tg_emoji(STICKERS['product_selected'], '🎉')} <b>История заказов</b>\n\n"
    for p in purchases[:10]:
        history_text += f"🆔 Заказ #{p['id']}\n"
        history_text += f"🎮 Товар: {p['name']}\n"
        history_text += f"💰 Цена: {p['price']} ₽\n"
        history_text += f"📅 Дата: {p['created_at'].strftime('%d.%m.%Y %H:%M')}\n"
        history_text += "─" * 15 + "\n"
    
    await callback.message.edit_text(history_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="menu_profile", icon_custom_emoji_id=BUTTON_EMOJI["back"])]]))
    await callback.answer()

@dp.callback_query(lambda c: c.data == "profile_deposit")
async def profile_deposit(callback: CallbackQuery, state: FSMContext):
    await state.set_state(DepositStates.waiting_amount)
    await callback.message.edit_text(
        f"{tg_emoji(STICKERS['enter_amount'], '💰')} <b>Укажите сумму пополнения баланса</b>\n\n"
        f"Введите сумму от 10 до 50000 ₽\n\nПример: <code>500</code>\n\n"
        f"Отправьте число в этот чат",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="menu_profile", icon_custom_emoji_id=BUTTON_EMOJI["back"])]])
    )
    await callback.answer()

@dp.message(DepositStates.waiting_amount)
async def process_deposit_amount(message: Message, state: FSMContext):
    try:
        amount = int(message.text.strip())
        if amount < 10 or amount > 50000:
            await message.answer(
                f"{tg_emoji(STICKERS['keys_count'], '❌')} Сумма должна быть от 10 до 50000 ₽\n\nПопробуйте снова:",
                parse_mode="HTML"
            )
            return
        
        await state.update_data(amount=amount)
        await state.clear()
        
        payment_id = str(uuid.uuid4())
        pending_payments[message.from_user.id] = {
            "amount": amount,
            "payment_id": payment_id,
            "status": "pending"
        }
        
        payment_url = await create_platega_payment(amount, payment_id, message.from_user.id)
        
        if not payment_url:
            await message.answer(
                f"{tg_emoji(STICKERS['keys_count'], '❌')} <b>Платежная система временно недоступна</b>\n\n"
                f"Свяжитесь с администратором для пополнения баланса.\n\n"
                f"👤 Админ: @nikita1055",
                parse_mode="HTML",
                reply_markup=get_profile_keyboard()
            )
            return
        
        await message.answer(
            f"{tg_emoji(STICKERS['payment_method'], '💳')} <b>Оплата</b>\n\n"
            f"Сумма: <code>{amount} ₽</code>\n\n"
            f"🔗 <a href='{payment_url}'>Нажмите для оплаты</a>\n\n"
            f"🆔 ID платежа: <code>{payment_id}</code>",
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=get_profile_keyboard()
        )
        
    except ValueError:
        await message.answer(
            f"{tg_emoji(STICKERS['keys_count'], '❌')} Введите <b>число</b>!\n\nПример: <code>500</code>",
            parse_mode="HTML"
        )

@dp.callback_query(lambda c: c.data == "profile_activate_promocode")
async def profile_activate_promocode(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ProfileActivatePromocodeStates.waiting_code)
    await callback.message.edit_text(
        f"{tg_emoji(BUTTON_EMOJI['promocode'], '🎫')} <b>Активация промокода</b>\n\n"
        f"Введите промокод:\n\n"
        f"Пример: <code>SUMMER2024</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="menu_profile", icon_custom_emoji_id=BUTTON_EMOJI["back"])]])
    )
    await callback.answer()

@dp.message(ProfileActivatePromocodeStates.waiting_code)
async def process_activate_promocode(message: Message, state: FSMContext):
    code = message.text.strip().upper()
    
    promocode = await get_promocode(code)
    
    if not promocode:
        await message.answer(
            f"{tg_emoji(STICKERS['keys_count'], '❌')} <b>Промокод не найден или уже использован</b>",
            parse_mode="HTML",
            reply_markup=get_profile_keyboard()
        )
        await state.clear()
        return
    
    already_used = await check_promocode_used(message.from_user.id, promocode["id"])
    
    if already_used:
        await message.answer(
            f"{tg_emoji(STICKERS['keys_count'], '❌')} <b>Вы уже активировали этот промокод</b>",
            parse_mode="HTML",
            reply_markup=get_profile_keyboard()
        )
        await state.clear()
        return
    
    current_balance = await get_balance(message.from_user.id)
    discount_type = promocode["discount_type"]
    discount_value = promocode["discount_value"]
    new_balance = current_balance
    
    if discount_type == "percent":
        new_balance = current_balance + int(current_balance * discount_value / 100)
        bonus_text = f"{discount_value}% от текущего баланса"
    elif discount_type == "rubles":
        new_balance = current_balance + discount_value
        bonus_text = f"{discount_value} ₽"
    else:
        new_balance = current_balance + discount_value
        bonus_text = f"{discount_value} ₽ бонусом"
    
    await update_user_balance(message.from_user.id, new_balance)
    await use_promocode(message.from_user.id, promocode["id"])
    
    await message.answer(
        f"{tg_emoji(STICKERS['product_selected'], '✅')} <b>Промокод успешно активирован!</b>\n\n"
        f"🎫 Промокод: <code>{code}</code>\n"
        f"💰 Вы получили: {bonus_text}\n"
        f"📊 Было: <code>{current_balance} ₽</code>\n"
        f"📊 Стало: <code>{new_balance} ₽</code>",
        parse_mode="HTML",
        reply_markup=get_profile_keyboard()
    )
    await state.clear()

@dp.callback_query(lambda c: c.data and c.data.startswith("buy_"))
async def handle_buy(callback: CallbackQuery):
    product_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    
    products = await get_all_products()
    product = next((p for p in products if p["id"] == product_id), None)
    if not product:
        await callback.answer("Товар не найден")
        return
    
    balance = await get_balance(user_id)
    if balance < product["price"]:
        await callback.answer(f"Недостаточно средств! Нужно {product['price']} ₽")
        return
    
    key_row = await get_unused_key(product_id)
    if not key_row:
        await callback.answer("Ключи закончились")
        return
    
    await update_user_balance(user_id, balance - product["price"])
    await mark_key_as_used(key_row["id"])
    await add_purchase(user_id, product_id, product["price"])
    
    from database import pool
    async with pool.acquire() as conn:
        keys_left = await conn.fetchval("SELECT COUNT(*) FROM keys_store WHERE product_id = $1 AND used = FALSE", product_id)
    
    vip_link_row = await get_active_vip_link()
    vip_link = vip_link_row["link"] if vip_link_row else "https://t.me/+a5AssXS77w01Yjky"
    
    await callback.message.answer(
        f"{tg_emoji(STICKERS['product_selected'], '✅')} <b>Выбран товар • {product['name']}</b>\n\n"
        f"{tg_emoji(STICKERS['keys_count'], '🔑')} <b>Ключей в наличии:</b> {keys_left}\n"
        f"{tg_emoji(STICKERS['price_icon'], '💰')} <b>Цена:</b> {product['price']} ₽\n\n"
        f"{tg_emoji(STICKERS['product_selected'], '🔑')} <b>Ваш ключ:</b> <code>{key_row['key_value']}</code>\n\n"
        f"🔗 <b>Ссылка на VIP канал:</b>\n"
        f"<a href='{vip_link}'>Нажмите для вступления</a>",
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="В меню", callback_data="menu_main", icon_custom_emoji_id=BUTTON_EMOJI["home"])]])
    )
    await callback.message.delete()
    await callback.answer("Покупка успешна!")

@dp.message(Command("admin"))
async def admin_cmd(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Доступ запрещен")
        return
    
    await message.answer(
        f"{tg_emoji(STICKERS['profile'], '🔐')} <b>Админ-панель</b>",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard()
    )

@dp.callback_query(lambda c: c.data == "admin_add_product")
async def admin_add_product(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен")
        return
    await state.set_state(AddProductStates.waiting_name)
    await callback.message.edit_text(
        "📝 Введите название товара:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="admin_back", icon_custom_emoji_id=BUTTON_EMOJI["back"])]])
    )
    await callback.answer()

@dp.message(AddProductStates.waiting_name)
async def product_name(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.update_data(name=message.text)
    await state.set_state(AddProductStates.waiting_price)
    await message.answer("💰 Введите цену (число):")

@dp.message(AddProductStates.waiting_price)
async def product_price(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        price = int(message.text)
        await state.update_data(price=price)
        await state.set_state(AddProductStates.waiting_keys)
        await message.answer("🔑 Введите ключи (каждый с новой строки):\n\nПример:\nKEY-123-ABC\nKEY-456-DEF")
    except ValueError:
        await message.answer("❌ Введите число")

@dp.message(AddProductStates.waiting_keys)
async def product_keys(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    data = await state.get_data()
    keys = [k.strip() for k in message.text.split("\n") if k.strip()]
    if not keys:
        await message.answer("❌ Хотя бы один ключ")
        return
    
    product_id = await add_product(data["name"], data["price"])
    await add_keys_to_product(product_id, keys)
    await message.answer(
        f"✅ Товар добавлен! {len(keys)} ключей\n📦 ID товара: {product_id}",
        reply_markup=get_admin_keyboard()
    )
    await state.clear()

@dp.callback_query(lambda c: c.data == "admin_add_keys")
async def admin_add_keys(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен")
        return
    products = await get_all_products()
    if not products:
        await callback.message.edit_text(
            "❌ Сначала добавьте товар",
            reply_markup=get_admin_keyboard()
        )
        await callback.answer()
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{p['name']} (ID: {p['id']})", callback_data=f"addkeys_{p['id']}")]
        for p in products
    ] + [[InlineKeyboardButton(text="Назад", callback_data="admin_back", icon_custom_emoji_id=BUTTON_EMOJI["back"])]])
    
    await callback.message.edit_text("📦 Выберите товар для добавления ключей:", reply_markup=kb)
    await callback.answer()

@dp.callback_query(lambda c: c.data and c.data.startswith("addkeys_"))
async def select_for_keys(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔")
        return
    product_id = int(callback.data.split("_")[1])
    await state.update_data(product_id=product_id)
    await state.set_state(AddKeysStates.waiting_keys)
    await callback.message.edit_text(
        "🔑 Введите ключи (по одному на строку):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="admin_back", icon_custom_emoji_id=BUTTON_EMOJI["back"])]])
    )
    await callback.answer()

@dp.message(AddKeysStates.waiting_keys)
async def process_keys_only(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    data = await state.get_data()
    product_id = data["product_id"]
    keys = [k.strip() for k in message.text.split("\n") if k.strip()]
    await add_keys_to_product(product_id, keys)
    await message.answer(
        f"✅ Добавлено {len(keys)} ключей для товара ID {product_id}",
        reply_markup=get_admin_keyboard()
    )
    await state.clear()

@dp.callback_query(lambda c: c.data == "admin_add_balance")
async def admin_add_balance(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен")
        return
    await state.set_state(AdminAddBalanceStates.waiting_user_id)
    await callback.message.edit_text(
        "💰 <b>Выдача баланса пользователю</b>\n\n"
        "Введите ID пользователя Telegram:\n\n"
        "Пример: <code>123456789</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="admin_back", icon_custom_emoji_id=BUTTON_EMOJI["back"])]])
    )
    await callback.answer()

@dp.message(AdminAddBalanceStates.waiting_user_id)
async def process_add_balance_user_id(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        user_id = int(message.text.strip())
        await state.update_data(user_id=user_id)
        await state.set_state(AdminAddBalanceStates.waiting_amount)
        await message.answer(
            "💰 Введите сумму для начисления на баланс:\n\n"
            "Пример: <code>500</code>",
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer("❌ Неверный ID. Введите число.")

@dp.message(AdminAddBalanceStates.waiting_amount)
async def process_add_balance_amount(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        amount = int(message.text.strip())
        if amount <= 0:
            await message.answer("❌ Сумма должна быть больше 0")
            return
        
        data = await state.get_data()
        user_id = data["user_id"]
        
        current_balance = await get_balance(user_id)
        await update_user_balance(user_id, current_balance + amount)
        
        await message.answer(
            f"✅ <b>Баланс успешно выдан!</b>\n\n"
            f"👤 Пользователь: <code>{user_id}</code>\n"
            f"💰 Сумма: <code>{amount} ₽</code>\n"
            f"📊 Новый баланс: <code>{current_balance + amount} ₽</code>",
            parse_mode="HTML",
            reply_markup=get_admin_keyboard()
        )
        
        await bot.send_message(
            user_id,
            f"{tg_emoji(STICKERS['product_selected'], '✅')} <b>Баланс пополнен администратором!</b>\n\n"
            f"💰 Сумма: <code>{amount} ₽</code>\n"
            f"📊 Новый баланс: <code>{current_balance + amount} ₽</code>",
            parse_mode="HTML"
        )
        
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Введите число")

@dp.callback_query(lambda c: c.data == "admin_broadcast")
async def admin_broadcast(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен")
        return
    await state.set_state(AdminBroadcastStates.waiting_message)
    await callback.message.edit_text(
        "📢 <b>Рассылка сообщения</b>\n\n"
        "Введите текст сообщения для рассылки всем пользователям:\n\n"
        "Поддерживается HTML разметка",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="admin_back", icon_custom_emoji_id=BUTTON_EMOJI["back"])]])
    )
    await callback.answer()

@dp.message(AdminBroadcastStates.waiting_message)
async def process_broadcast(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    broadcast_text = message.text
    users = await get_all_users()
    
    await message.answer(
        f"📢 <b>Начинаю рассылку...</b>\n\n"
        f"👥 Всего пользователей: <code>{len(users)}</code>",
        parse_mode="HTML"
    )
    
    success_count = 0
    fail_count = 0
    
    for user in users:
        try:
            await bot.send_message(
                user["user_id"],
                f"{tg_emoji(STICKERS['magic'], '📢')} <b>РАССЫЛКА ОТ АДМИНИСТРАТОРА</b>\n\n{broadcast_text}",
                parse_mode="HTML"
            )
            success_count += 1
        except:
            fail_count += 1
        await asyncio.sleep(0.05)
    
    await message.answer(
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"✅ Доставлено: <code>{success_count}</code>\n"
        f"❌ Не доставлено: <code>{fail_count}</code>",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard()
    )
    await state.clear()

@dp.callback_query(lambda c: c.data == "admin_create_promocode")
async def admin_create_promocode(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен")
        return
    await state.set_state(AdminCreatePromocodeStates.waiting_code)
    await callback.message.edit_text(
        "🎫 <b>Создание промокода</b>\n\n"
        "Введите название промокода (только латиница и цифры, без пробелов):\n\n"
        "Пример: <code>SUMMER2024</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="admin_back", icon_custom_emoji_id=BUTTON_EMOJI["back"])]])
    )
    await callback.answer()

@dp.message(AdminCreatePromocodeStates.waiting_code)
async def create_promocode_code(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    code = message.text.strip().upper()
    await state.update_data(code=code)
    await state.set_state(AdminCreatePromocodeStates.waiting_type)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Скидка в процентах (%)", callback_data="promo_type_percent")],
        [InlineKeyboardButton(text="Скидка в рублях (₽)", callback_data="promo_type_rubles")],
        [InlineKeyboardButton(text="Бонусный баланс (₽)", callback_data="promo_type_bonus")],
        [InlineKeyboardButton(text="Отмена", callback_data="admin_back", icon_custom_emoji_id=BUTTON_EMOJI["back"])]
    ])
    
    await message.answer(
        "📊 <b>Выберите тип промокода:</b>",
        parse_mode="HTML",
        reply_markup=kb
    )

@dp.callback_query(lambda c: c.data and c.data.startswith("promo_type_"))
async def create_promocode_type(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔")
        return
    
    discount_type = callback.data.split("_")[2]
    await state.update_data(discount_type=discount_type)
    await state.set_state(AdminCreatePromocodeStates.waiting_value)
    
    if discount_type == "percent":
        await callback.message.edit_text(
            "📊 Введите размер скидки в процентах (число от 1 до 100):\n\nПример: <code>10</code>",
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            "💰 Введите сумму скидки или бонуса в рублях (число):\n\nПример: <code>500</code>",
            parse_mode="HTML"
        )
    await callback.answer()

@dp.message(AdminCreatePromocodeStates.waiting_value)
async def create_promocode_value(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        value = int(message.text.strip())
        if value <= 0:
            await message.answer("❌ Значение должно быть больше 0")
            return
        
        await state.update_data(discount_value=value)
        await state.set_state(AdminCreatePromocodeStates.waiting_max_uses)
        await message.answer(
            "🔢 Введите максимальное количество активаций промокода:\n\nПример: <code>100</code>",
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer("❌ Введите число")

@dp.message(AdminCreatePromocodeStates.waiting_max_uses)
async def create_promocode_max_uses(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        max_uses = int(message.text.strip())
        if max_uses <= 0:
            await message.answer("❌ Количество активаций должно быть больше 0")
            return
        
        data = await state.get_data()
        code = data["code"]
        discount_type = data["discount_type"]
        discount_value = data["discount_value"]
        
        await create_promocode(code, discount_type, discount_value, max_uses)
        
        if discount_type == "percent":
            type_text = f"{discount_value}%"
        elif discount_type == "rubles":
            type_text = f"{discount_value} ₽ (скидка)"
        else:
            type_text = f"{discount_value} ₽ (бонус)"
        
        await message.answer(
            f"✅ <b>Промокод успешно создан!</b>\n\n"
            f"🎫 Код: <code>{code}</code>\n"
            f"📊 Тип: {type_text}\n"
            f"🔢 Максимум активаций: <code>{max_uses}</code>",
            parse_mode="HTML",
            reply_markup=get_admin_keyboard()
        )
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Введите число")

@dp.callback_query(lambda c: c.data == "admin_list_promocodes")
async def admin_list_promocodes(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔")
        return
    
    promocodes = await get_all_promocodes()
    
    if not promocodes:
        await callback.message.edit_text(
            "📭 <b>Список промокодов пуст</b>",
            parse_mode="HTML",
            reply_markup=get_admin_keyboard()
        )
        await callback.answer()
        return
    
    text = "🎫 <b>Список промокодов</b>\n\n"
    for p in promocodes:
        if p["discount_type"] == "percent":
            type_text = f"{p['discount_value']}%"
        elif p["discount_type"] == "rubles":
            type_text = f"{p['discount_value']} ₽ (скидка)"
        else:
            type_text = f"{p['discount_value']} ₽ (бонус)"
        
        text += f"🔹 <code>{p['code']}</code>\n"
        text += f"   📊 {type_text}\n"
        text += f"   📊 Использован: {p['used_count']}/{p['max_uses']}\n"
        text += f"   🗑️ /del_{p['id']} - удалить\n\n"
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_admin_keyboard())
    await callback.answer()

@dp.message(lambda m: m.text and m.text.startswith("/del_"))
async def delete_promocode_cmd(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        promocode_id = int(message.text.split("_")[1])
        await delete_promocode(promocode_id)
        await message.answer("✅ Промокод удален!", reply_markup=get_admin_keyboard())
    except:
        await message.answer("❌ Ошибка при удалении")

@dp.callback_query(lambda c: c.data == "admin_create_vip_link")
async def admin_create_vip_link(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен")
        return
    
    if not CHANNEL_ID:
        await callback.message.edit_text(
            "❌ <b>ID канала не задан!</b>\n\n"
            "Добавьте переменную CHANNEL_ID в Railway.\n"
            "ID канала должен быть отрицательным: -1001822487778",
            parse_mode="HTML",
            reply_markup=get_admin_keyboard()
        )
        await callback.answer()
        return
    
    try:
        invite_link = await bot.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            member_limit=1,
            expire_date=None
        )
        
        await add_vip_link(invite_link.invite_link)
        
        await callback.message.edit_text(
            f"✅ <b>Новая VIP ссылка создана!</b>\n\n"
            f"🔗 {invite_link.invite_link}\n\n"
            f"⚠️ Ссылка одноразовая (действует для 1 человека).\n"
            f"📊 Всего создано: {len(await get_all_vip_links())}",
            parse_mode="HTML",
            reply_markup=get_admin_keyboard()
        )
    except Exception as e:
        await callback.message.edit_text(
            f"❌ <b>Ошибка создания ссылки</b>\n\n"
            f"Проверьте что бот добавлен в канал админом.\n\n"
            f"Ошибка: {str(e)[:200]}",
            parse_mode="HTML",
            reply_markup=get_admin_keyboard()
        )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_list_vip_links")
async def admin_list_vip_links(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔")
        return
    
    links = await get_all_vip_links()
    
    if not links:
        await callback.message.edit_text(
            "📭 <b>Список VIP ссылок пуст</b>\n\n"
            "Создайте новую ссылку через кнопку 'Создать ссылку VIP'",
            parse_mode="HTML",
            reply_markup=get_admin_keyboard()
        )
        await callback.answer()
        return
    
    text = "🔗 <b>Список VIP ссылок</b>\n\n"
    for link in links:
        status = "✅ Активна" if link["is_active"] else "❌ Неактивна"
        text += f"📅 {link['created_at'].strftime('%d.%m.%Y %H:%M')}\n"
        text += f"🔗 {link['link']}\n"
        text += f"📊 {status}\n"
        text += f"🗑️ /dellink_{link['id']} - удалить\n\n"
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_admin_keyboard())
    await callback.answer()

@dp.message(lambda m: m.text and m.text.startswith("/dellink_"))
async def delete_vip_link_cmd(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        link_id = int(message.text.split("_")[1])
        await deactivate_vip_link(link_id)
        await message.answer("✅ VIP ссылка деактивирована!", reply_markup=get_admin_keyboard())
    except:
        await message.answer("❌ Ошибка при удалении")

@dp.callback_query(lambda c: c.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔")
        return
    stats = await get_stats()
    await callback.message.edit_text(
        f"📊 <b>Статистика</b>\n\n"
        f"👥 Пользователей: <code>{stats['users']}</code>\n"
        f"💰 Продаж на сумму: <code>{stats['total_sales']} ₽</code>\n"
        f"🔑 Выдано ключей: <code>{stats['keys_sold']}</code>\n"
        f"🔑 Осталось ключей: <code>{stats['keys_left']}</code>\n"
        f"📦 Товаров в продаже: <code>{stats['products_count']}</code>",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard()
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_back")
async def admin_back(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        f"{tg_emoji(STICKERS['profile'], '🔐')} <b>Админ-панель</b>",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard()
    )
    await callback.answer()

@flask_app.route("/webhook/payment", methods=["POST"])
def payment_webhook():
    data = request.get_json()
    return jsonify({"status": "ok"}), 200

@flask_app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "alive"}), 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host="0.0.0.0", port=port)

async def main():
    await connect_db()
    await bot.delete_webhook(drop_pending_updates=True)
    thread = Thread(target=run_flask, daemon=True)
    thread.start()
    print("Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
