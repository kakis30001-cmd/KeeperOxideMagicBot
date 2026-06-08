import asyncio
import os
import uuid
from datetime import datetime, timedelta
from threading import Thread
from flask import Flask, request, jsonify
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from config import BOT_TOKEN, ADMIN_IDS, RAILWAY_URL, CHANNEL_ID
from database import (
    connect_db, add_user, get_balance, get_all_products,
    add_product, add_keys_to_product, get_unused_key,
    mark_key_as_used, update_user_balance, add_purchase, get_user_purchases, get_stats,
    get_all_users, create_promocode, get_promocode, use_promocode, check_promocode_used,
    get_all_promocodes, delete_promocode, get_referrer, get_referrals_count, get_paid_referrals_count,
    get_referral_config, update_referral_config, add_balance, get_product_by_id,
    delete_product, get_keys_by_product, delete_key, mark_purchased, has_user_purchased,
    add_crypto_payment, get_crypto_payment, update_crypto_payment_status,
    get_crypto_config, update_crypto_config, get_bot_message, update_bot_message, get_all_message_keys
)

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
    "referral": "5872771279337033184",
    "delete_product": "5872771279337033184",
    "delete_key": "5872771279337033184",
}

def tg_emoji(sticker_id: str, fallback: str = "") -> str:
    return f'<tg-emoji emoji-id="{sticker_id}">{fallback}</tg-emoji>'

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
flask_app = Flask(__name__)

pending_payments = {}

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

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

class AdminRefBonusStates(StatesGroup):
    waiting_type = State()
    waiting_value = State()

class AdminCryptoSettingsStates(StatesGroup):
    waiting_currency = State()
    waiting_amount = State()
    waiting_manual_text = State()
    waiting_manual_photo = State()

class AdminEditMessageStates(StatesGroup):
    waiting_key = State()
    waiting_text = State()
    waiting_photo = State()

async def create_vip_link(user_id: int, days: int = 30):
    try:
        invite_link = await bot.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            member_limit=1,
            expire_date=datetime.now() + timedelta(days=days)
        )
        return invite_link.invite_link
    except:
        return None

async def create_platega_payment(amount: int, order_id: str, user_id: int) -> str:
    return None

def get_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Магазин", callback_data="menu_shop", icon_custom_emoji_id=BUTTON_EMOJI["shop"]), InlineKeyboardButton(text="Профиль", callback_data="menu_profile", icon_custom_emoji_id=BUTTON_EMOJI["profile"])],
        [InlineKeyboardButton(text="Информация", callback_data="menu_info", icon_custom_emoji_id=BUTTON_EMOJI["info"])]
    ])

def get_profile_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пополнить баланс", callback_data="profile_deposit", icon_custom_emoji_id=BUTTON_EMOJI["balance"]), InlineKeyboardButton(text="История заказов", callback_data="profile_history", icon_custom_emoji_id=BUTTON_EMOJI["history"])],
        [InlineKeyboardButton(text="Активировать промокод", callback_data="profile_activate_promocode", icon_custom_emoji_id=BUTTON_EMOJI["promocode"]), InlineKeyboardButton(text="Реферальная система", callback_data="profile_referral", icon_custom_emoji_id=BUTTON_EMOJI["referral"])],
        [InlineKeyboardButton(text="Главное меню", callback_data="menu_main", icon_custom_emoji_id=BUTTON_EMOJI["home"])]
    ])

def get_admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить товар", callback_data="admin_add_product", icon_custom_emoji_id=BUTTON_EMOJI["add_product"]), InlineKeyboardButton(text="Добавить ключи", callback_data="admin_add_keys", icon_custom_emoji_id=BUTTON_EMOJI["add_keys"])],
        [InlineKeyboardButton(text="Выдать баланс", callback_data="admin_add_balance", icon_custom_emoji_id=BUTTON_EMOJI["add_balance"]), InlineKeyboardButton(text="Сделать рассылку", callback_data="admin_broadcast", icon_custom_emoji_id=BUTTON_EMOJI["broadcast"])],
        [InlineKeyboardButton(text="Создать промокод", callback_data="admin_create_promocode", icon_custom_emoji_id=BUTTON_EMOJI["promocode"]), InlineKeyboardButton(text="Список промокодов", callback_data="admin_list_promocodes", icon_custom_emoji_id=BUTTON_EMOJI["promocode"])],
        [InlineKeyboardButton(text="Настройка рефералов", callback_data="admin_ref_config", icon_custom_emoji_id=BUTTON_EMOJI["referral"])],
        [InlineKeyboardButton(text="Настройка криптооплаты", callback_data="admin_crypto_settings", icon_custom_emoji_id=BUTTON_EMOJI["stats"])],
        [InlineKeyboardButton(text="✏️ Редактировать сообщения", callback_data="admin_edit_messages", icon_custom_emoji_id=BUTTON_EMOJI["stats"])],
        [InlineKeyboardButton(text="Управление товарами", callback_data="admin_manage_products", icon_custom_emoji_id=BUTTON_EMOJI["delete_product"]), InlineKeyboardButton(text="Управление ключами", callback_data="admin_manage_keys", icon_custom_emoji_id=BUTTON_EMOJI["delete_key"])],
        [InlineKeyboardButton(text="Статистика", callback_data="admin_stats", icon_custom_emoji_id=BUTTON_EMOJI["stats"]), InlineKeyboardButton(text="Главное меню", callback_data="menu_main", icon_custom_emoji_id=BUTTON_EMOJI["home"])]
    ])

@dp.message(CommandStart())
async def start_cmd(message: Message):
    args = message.text.split()
    referrer_id = None
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            referrer_id = int(args[1].split("_")[1])
            if referrer_id == message.from_user.id:
                referrer_id = None
        except:
            pass
    await add_user(message.from_user.id, referrer_id)
    
    msg_data = await get_bot_message("welcome")
    text = msg_data["text"] if msg_data else "Добро пожаловать!"
    photo_file_id = msg_data["photo_file_id"] if msg_data else None
    
    if photo_file_id:
        await message.answer_photo(
            photo=photo_file_id,
            caption=text,
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())

@dp.callback_query(lambda c: c.data == "menu_main")
async def menu_main(callback: CallbackQuery):
    text = f"{tg_emoji(STICKERS['click_below'], '✨')} <b>Главное меню</b>\n\nВыберите действие:"
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_main_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_info")
async def menu_info(callback: CallbackQuery):
    msg_data = await get_bot_message("info")
    text = msg_data["text"] if msg_data else "Информация"
    photo_file_id = msg_data["photo_file_id"] if msg_data else None
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="menu_main", icon_custom_emoji_id=BUTTON_EMOJI["back"])]])
    
    if photo_file_id:
        await callback.message.delete()
        await bot.send_photo(
            chat_id=callback.from_user.id,
            photo=photo_file_id,
            caption=text,
            parse_mode="HTML",
            reply_markup=kb
        )
    else:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_shop")
async def menu_shop(callback: CallbackQuery):
    products = await get_all_products()
    if not products:
        await callback.message.edit_text(f"{tg_emoji(STICKERS['keys_count'], '📭')} <b>Товаров пока нет</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="menu_main", icon_custom_emoji_id=BUTTON_EMOJI["back"])]]))
        await callback.answer()
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{p['name']} | {p['price']}₽", callback_data=f"select_{p['id']}")] for p in products] + [[InlineKeyboardButton(text="Назад", callback_data="menu_main", icon_custom_emoji_id=BUTTON_EMOJI["back"])]])
    await callback.message.edit_text(f"{tg_emoji(STICKERS['shop_title'], '🛍')} <b>Выберите интересующий вас товар</b>", parse_mode="HTML", reply_markup=kb)
    await callback.answer()

@dp.callback_query(lambda c: c.data and c.data.startswith("select_"))
async def select_product(callback: CallbackQuery):
    product_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    products = await get_all_products()
    product = next((p for p in products if p["id"] == product_id), None)
    if not product:
        await callback.answer("Товар не найден")
        return
    balance = await get_balance(user_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Оплатить с баланса", callback_data=f"pay_balance_{product_id}")],
        [InlineKeyboardButton(text="💎 Оплатить криптовалютой", callback_data=f"pay_crypto_{product_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="menu_shop", icon_custom_emoji_id=BUTTON_EMOJI["back"])]
    ])
    await callback.message.edit_text(f"{tg_emoji(STICKERS['product_selected'], '💎')} <b>Выбран товар: {product['name']}</b>\n\n💰 Цена: <code>{product['price']} ₽</code>\n💎 Ваш баланс: <code>{balance} ₽</code>\n\nВыберите способ оплаты:", parse_mode="HTML", reply_markup=kb)
    await callback.answer()

@dp.callback_query(lambda c: c.data and c.data.startswith("pay_balance_"))
async def pay_balance(callback: CallbackQuery):
    product_id = int(callback.data.split("_")[2])
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
    if not await has_user_purchased(user_id):
        await mark_purchased(user_id)
        referrer_id = await get_referrer(user_id)
        if referrer_id:
            config = await get_referral_config()
            if config and config["bonus_value"] > 0:
                if config["bonus_type"] == "rubles":
                    await add_balance(referrer_id, config["bonus_value"])
                    await bot.send_message(referrer_id, f"🎉 Реферальный бонус! Вы получили {config['bonus_value']} ₽")
                elif config["bonus_type"] == "percent":
                    bonus_amount = int(product["price"] * config["bonus_value"] / 100)
                    await add_balance(referrer_id, bonus_amount)
                    await bot.send_message(referrer_id, f"🎉 Реферальный бонус! Вы получили {bonus_amount} ₽ ({config['bonus_value']}%)")
    from database import pool
    async with pool.acquire() as conn:
        keys_left = await conn.fetchval("SELECT COUNT(*) FROM keys_store WHERE product_id = $1 AND used = FALSE", product_id)
    vip_link = await create_vip_link(user_id, 30)
    if not vip_link:
        vip_link = "https://t.me/+a5AssXS77w01Yjky"
    await callback.message.edit_text(f"{tg_emoji(STICKERS['product_selected'], '✅')} <b>Покупка успешна!</b>\n\n{tg_emoji(STICKERS['keys_count'], '🔑')} <b>Ключей в наличии:</b> {keys_left}\n{tg_emoji(STICKERS['price_icon'], '💰')} <b>Цена:</b> {product['price']} ₽\n\n{tg_emoji(STICKERS['product_selected'], '🔑')} <b>Ваш ключ:</b> <code>{key_row['key_value']}</code>\n\n🔗 <b>Ссылка на VIP канал (одноразовая):</b>\n<a href='{vip_link}'>Нажмите для вступления</a>\n\n⚠️ Ссылка действительна 30 дней и только для вас!", parse_mode="HTML", disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="В меню", callback_data="menu_main", icon_custom_emoji_id=BUTTON_EMOJI["home"])]]))
    await callback.answer("Покупка успешна!")

@dp.callback_query(lambda c: c.data and c.data.startswith("pay_crypto_"))
async def pay_crypto(callback: CallbackQuery):
    product_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    products = await get_all_products()
    product = next((p for p in products if p["id"] == product_id), None)
    if not product:
        await callback.answer("Товар не найден")
        return
    crypto_config = await get_crypto_config()
    mode = crypto_config["payment_mode"]
    if mode == "auto":
        payment_id = str(uuid.uuid4())
        currency = crypto_config["currency"]
        amount = crypto_config["amount"]
        await add_crypto_payment(user_id, product_id, amount, currency, payment_id)
        await callback.message.edit_text(
            f"💎 <b>Оплата криптовалютой</b>\n\n"
            f"💰 Сумма: <code>{amount} {currency}</code>\n"
            f"🆔 ID платежа: <code>{payment_id}</code>\n\n"
            f"⚡ После оплаты ключ будет выдан автоматически.\n"
            f"🔗 Ссылка для оплаты будет сгенерирована после подключения @CryptoBot",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="menu_shop", icon_custom_emoji_id=BUTTON_EMOJI["back"])]])
        )
    else:
        manual_text = crypto_config["manual_text"]
        manual_photo = crypto_config["manual_photo"]
        if manual_photo:
            await callback.message.delete()
            await bot.send_photo(
                chat_id=user_id,
                photo=manual_photo,
                caption=f"💎 <b>Оплата криптовалютой (ручной режим)</b>\n\n{manual_text}\n\n💰 Сумма: <code>{product['price']} ₽</code>\n\n📞 После оплаты напишите администратору @nikita1055",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="menu_shop", icon_custom_emoji_id=BUTTON_EMOJI["back"])]])
            )
        else:
            await callback.message.edit_text(
                f"💎 <b>Оплата криптовалютой (ручной режим)</b>\n\n"
                f"{manual_text}\n\n"
                f"💰 Сумма: <code>{product['price']} ₽</code>\n\n"
                f"📞 После оплаты напишите администратору @nikita1055",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="menu_shop", icon_custom_emoji_id=BUTTON_EMOJI["back"])]])
            )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_profile")
async def menu_profile(callback: CallbackQuery):
    balance = await get_balance(callback.from_user.id)
    text = f"{tg_emoji(STICKERS['profile'], '👤')} <b>Профиль</b>\n\n{tg_emoji(STICKERS['id_icon'], '🆔')} ID: <code>{callback.from_user.id}</code>\n{tg_emoji(STICKERS['balance_icon'], '💰')} Баланс: <code>{balance} ₽</code>"
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_profile_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "profile_referral")
async def profile_referral(callback: CallbackQuery):
    user_id = callback.from_user.id
    bot_username = (await bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    total_referrals = await get_referrals_count(user_id)
    paid_referrals = await get_paid_referrals_count(user_id)
    config = await get_referral_config()
    bonus_text = f"{config['bonus_value']} ₽" if config["bonus_type"] == "rubles" else f"{config['bonus_value']}% от покупки"
    text = f"{tg_emoji(BUTTON_EMOJI['referral'], '👥')} <b>Реферальная система</b>\n\n🔗 <b>Ваша ссылка:</b>\n<code>{ref_link}</code>\n\n👥 Приглашено друзей: <code>{total_referrals}</code>\n✅ Из них купили: <code>{paid_referrals}</code>\n🎁 <b>Награда за покупку друга:</b> {bonus_text}\n\n💡 Награда начисляется после первой покупки вашего друга!"
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="menu_profile", icon_custom_emoji_id=BUTTON_EMOJI["back"])]]))
    await callback.answer()

@dp.callback_query(lambda c: c.data == "profile_history")
async def profile_history(callback: CallbackQuery):
    purchases = await get_user_purchases(callback.from_user.id)
    if not purchases:
        await callback.message.edit_text(f"{tg_emoji(STICKERS['keys_count'], '📋')} <b>История заказов</b>\n\nУ вас пока нет покупок.", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="menu_profile", icon_custom_emoji_id=BUTTON_EMOJI["back"])]]))
        await callback.answer()
        return
    history_text = f"{tg_emoji(STICKERS['product_selected'], '🎉')} <b>История заказов</b>\n\n"
    for p in purchases[:10]:
        history_text += f"🆔 Заказ #{p['id']}\n🎮 Товар: {p['name']}\n💰 Цена: {p['price']} ₽\n📅 Дата: {p['created_at'].strftime('%d.%m.%Y %H:%M')}\n─" * 15 + "\n"
    await callback.message.edit_text(history_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="menu_profile", icon_custom_emoji_id=BUTTON_EMOJI["back"])]]))
    await callback.answer()

@dp.callback_query(lambda c: c.data == "profile_deposit")
async def profile_deposit(callback: CallbackQuery, state: FSMContext):
    await state.set_state(DepositStates.waiting_amount)
    await callback.message.edit_text(f"{tg_emoji(STICKERS['enter_amount'], '💰')} <b>Укажите сумму пополнения баланса</b>\n\nВведите сумму от 10 до 50000 ₽\n\nПример: <code>500</code>\n\nОтправьте число в этот чат", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="menu_profile", icon_custom_emoji_id=BUTTON_EMOJI["back"])]]))
    await callback.answer()

@dp.message(DepositStates.waiting_amount)
async def process_deposit_amount(message: Message, state: FSMContext):
    try:
        amount = int(message.text.strip())
        if amount < 10 or amount > 50000:
            await message.answer(f"{tg_emoji(STICKERS['keys_count'], '❌')} Сумма должна быть от 10 до 50000 ₽\n\nПопробуйте снова:", parse_mode="HTML")
            return
        await state.update_data(amount=amount)
        await state.clear()
        await message.answer(f"{tg_emoji(STICKERS['payment_method'], '💳')} <b>Платежная система временно недоступна</b>\n\nСвяжитесь с администратором для пополнения баланса.\n\n👤 Админ: @nikita1055", parse_mode="HTML", reply_markup=get_profile_keyboard())
    except ValueError:
        await message.answer(f"{tg_emoji(STICKERS['keys_count'], '❌')} Введите <b>число</b>!\n\nПример: <code>500</code>", parse_mode="HTML")

@dp.callback_query(lambda c: c.data == "profile_activate_promocode")
async def profile_activate_promocode(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ProfileActivatePromocodeStates.waiting_code)
    await callback.message.edit_text(f"{tg_emoji(BUTTON_EMOJI['promocode'], '🎫')} <b>Активация промокода</b>\n\nВведите промокод:\n\nПример: <code>SUMMER2024</code>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="menu_profile", icon_custom_emoji_id=BUTTON_EMOJI["back"])]]))
    await callback.answer()

@dp.message(ProfileActivatePromocodeStates.waiting_code)
async def process_activate_promocode(message: Message, state: FSMContext):
    code = message.text.strip().upper()
    promocode = await get_promocode(code)
    if not promocode:
        await message.answer(f"{tg_emoji(STICKERS['keys_count'], '❌')} <b>Промокод не найден или уже использован</b>", parse_mode="HTML", reply_markup=get_profile_keyboard())
        await state.clear()
        return
    already_used = await check_promocode_used(message.from_user.id, promocode["id"])
    if already_used:
        await message.answer(f"{tg_emoji(STICKERS['keys_count'], '❌')} <b>Вы уже активировали этот промокод</b>", parse_mode="HTML", reply_markup=get_profile_keyboard())
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
    await message.answer(f"{tg_emoji(STICKERS['product_selected'], '✅')} <b>Промокод успешно активирован!</b>\n\n🎫 Промокод: <code>{code}</code>\n💰 Вы получили: {bonus_text}\n📊 Было: <code>{current_balance} ₽</code>\n📊 Стало: <code>{new_balance} ₽</code>", parse_mode="HTML", reply_markup=get_profile_keyboard())
    await state.clear()

@dp.message(Command("admin"))
async def admin_cmd(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return
    await message.answer(f"{tg_emoji(STICKERS['profile'], '🔐')} <b>Админ-панель</b>", parse_mode="HTML", reply_markup=get_admin_keyboard())

@dp.callback_query(lambda c: c.data == "admin_add_product")
async def admin_add_product(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен")
        return
    await state.set_state(AddProductStates.waiting_name)
    await callback.message.edit_text("📝 Введите название товара:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="admin_back", icon_custom_emoji_id=BUTTON_EMOJI["back"])]]))
    await callback.answer()

@dp.message(AddProductStates.waiting_name)
async def product_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(name=message.text)
    await state.set_state(AddProductStates.waiting_price)
    await message.answer("💰 Введите цену (число):")

@dp.message(AddProductStates.waiting_price)
async def product_price(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
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
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    keys = [k.strip() for k in message.text.split("\n") if k.strip()]
    if not keys:
        await message.answer("❌ Хотя бы один ключ")
        return
    product_id = await add_product(data["name"], data["price"])
    await add_keys_to_product(product_id, keys)
    await message.answer(f"✅ Товар добавлен! {len(keys)} ключей\n📦 ID товара: {product_id}", reply_markup=get_admin_keyboard())
    await state.clear()

@dp.callback_query(lambda c: c.data == "admin_add_keys")
async def admin_add_keys(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен")
        return
    products = await get_all_products()
    if not products:
        await callback.message.edit_text("❌ Сначала добавьте товар", reply_markup=get_admin_keyboard())
        await callback.answer()
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{p['name']} (ID: {p['id']})", callback_data=f"addkeys_{p['id']}")] for p in products] + [[InlineKeyboardButton(text="Назад", callback_data="admin_back", icon_custom_emoji_id=BUTTON_EMOJI["back"])]])
    await callback.message.edit_text("📦 Выберите товар для добавления ключей:", reply_markup=kb)
    await callback.answer()

@dp.callback_query(lambda c: c.data and c.data.startswith("addkeys_"))
async def select_for_keys(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔")
        return
    product_id = int(callback.data.split("_")[1])
    await state.update_data(product_id=product_id)
    await state.set_state(AddKeysStates.waiting_keys)
    await callback.message.edit_text("🔑 Введите ключи (по одному на строку):", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="admin_back", icon_custom_emoji_id=BUTTON_EMOJI["back"])]]))
    await callback.answer()

@dp.message(AddKeysStates.waiting_keys)
async def process_keys_only(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    product_id = data["product_id"]
    keys = [k.strip() for k in message.text.split("\n") if k.strip()]
    await add_keys_to_product(product_id, keys)
    await message.answer(f"✅ Добавлено {len(keys)} ключей для товара ID {product_id}", reply_markup=get_admin_keyboard())
    await state.clear()

@dp.callback_query(lambda c: c.data == "admin_manage_products")
async def admin_manage_products(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔")
        return
    products = await get_all_products()
    if not products:
        await callback.message.edit_text("📭 <b>Список товаров пуст</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="admin_back", icon_custom_emoji_id=BUTTON_EMOJI["back"])]]))
        await callback.answer()
        return
    text = "📦 <b>Список товаров</b>\n\n"
    for p in products:
        text += f"🆔 ID: {p['id']}\n📛 Название: {p['name']}\n💰 Цена: {p['price']} ₽\n🗑️ /delproduct_{p['id']} - удалить товар\n\n"
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="admin_back", icon_custom_emoji_id=BUTTON_EMOJI["back"])]]))
    await callback.answer()

@dp.message(lambda m: m.text and m.text.startswith("/delproduct_"))
async def delete_product_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return
    try:
        product_id = int(message.text.split("_")[1])
        await delete_product(product_id)
        await message.answer("✅ Товар удален!", reply_markup=get_admin_keyboard())
    except:
        await message.answer("❌ Ошибка при удалении")

@dp.callback_query(lambda c: c.data == "admin_manage_keys")
async def admin_manage_keys(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔")
        return
    products = await get_all_products()
    if not products:
        await callback.message.edit_text("📭 <b>Сначала добавьте товар</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="admin_back", icon_custom_emoji_id=BUTTON_EMOJI["back"])]]))
        await callback.answer()
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{p['name']} (ID: {p['id']})", callback_data=f"showkeys_{p['id']}")] for p in products] + [[InlineKeyboardButton(text="Назад", callback_data="admin_back", icon_custom_emoji_id=BUTTON_EMOJI["back"])]])
    await callback.message.edit_text("🔑 Выберите товар для просмотра ключей:", reply_markup=kb)
    await callback.answer()

@dp.callback_query(lambda c: c.data and c.data.startswith("showkeys_"))
async def show_keys(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔")
        return
    product_id = int(callback.data.split("_")[1])
    product = await get_product_by_id(product_id)
    keys = await get_keys_by_product(product_id)
    if not keys:
        await callback.message.edit_text(f"🔑 <b>Ключи для товара {product['name']}</b>\n\nСписок пуст", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="admin_manage_keys", icon_custom_emoji_id=BUTTON_EMOJI["back"])]]))
        await callback.answer()
        return
    text = f"🔑 <b>Ключи для товара {product['name']}</b>\n\n"
    for k in keys:
        status = "✅ Использован" if k["used"] else "🟢 Доступен"
        text += f"🆔 ID: {k['id']} | {k['key_value']} | {status}\n🗑️ /delkey_{k['id']} - удалить ключ\n\n"
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="admin_manage_keys", icon_custom_emoji_id=BUTTON_EMOJI["back"])]]))
    await callback.answer()

@dp.message(lambda m: m.text and m.text.startswith("/delkey_"))
async def delete_key_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return
    try:
        key_id = int(message.text.split("_")[1])
        await delete_key(key_id)
        await message.answer("✅ Ключ удален!", reply_markup=get_admin_keyboard())
    except:
        await message.answer("❌ Ошибка при удалении")

@dp.callback_query(lambda c: c.data == "admin_add_balance")
async def admin_add_balance(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен")
        return
    await state.set_state(AdminAddBalanceStates.waiting_user_id)
    await callback.message.edit_text("💰 <b>Выдача баланса пользователю</b>\n\nВведите ID пользователя Telegram:\n\nПример: <code>123456789</code>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="admin_back", icon_custom_emoji_id=BUTTON_EMOJI["back"])]]))
    await callback.answer()

@dp.message(AdminAddBalanceStates.waiting_user_id)
async def process_add_balance_user_id(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        user_id = int(message.text.strip())
        await state.update_data(user_id=user_id)
        await state.set_state(AdminAddBalanceStates.waiting_amount)
        await message.answer("💰 Введите сумму для начисления на баланс:\n\nПример: <code>500</code>", parse_mode="HTML")
    except ValueError:
        await message.answer("❌ Неверный ID. Введите число.")

@dp.message(AdminAddBalanceStates.waiting_amount)
async def process_add_balance_amount(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
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
        await message.answer(f"✅ <b>Баланс успешно выдан!</b>\n\n👤 Пользователь: <code>{user_id}</code>\n💰 Сумма: <code>{amount} ₽</code>\n📊 Новый баланс: <code>{current_balance + amount} ₽</code>", parse_mode="HTML", reply_markup=get_admin_keyboard())
        await bot.send_message(user_id, f"{tg_emoji(STICKERS['product_selected'], '✅')} <b>Баланс пополнен администратором!</b>\n\n💰 Сумма: <code>{amount} ₽</code>\n📊 Новый баланс: <code>{current_balance + amount} ₽</code>", parse_mode="HTML")
        await state.clear()
    except ValueError:
        await message.answer("❌ Введите число")

@dp.callback_query(lambda c: c.data == "admin_broadcast")
async def admin_broadcast(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен")
        return
    await state.set_state(AdminBroadcastStates.waiting_message)
    await callback.message.edit_text("📢 <b>Рассылка сообщения</b>\n\nВведите текст сообщения для рассылки всем пользователям:\n\nПоддерживается HTML разметка", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="admin_back", icon_custom_emoji_id=BUTTON_EMOJI["back"])]]))
    await callback.answer()

@dp.message(AdminBroadcastStates.waiting_message)
async def process_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    broadcast_text = message.text
    users = await get_all_users()
    await message.answer(f"📢 <b>Начинаю рассылку...</b>\n\n👥 Всего пользователей: <code>{len(users)}</code>", parse_mode="HTML")
    success_count = 0
    fail_count = 0
    for user in users:
        try:
            await bot.send_message(user["user_id"], f"{tg_emoji(STICKERS['magic'], '📢')} <b>РАССЫЛКА ОТ АДМИНИСТРАТОРА</b>\n\n{broadcast_text}", parse_mode="HTML")
            success_count += 1
        except:
            fail_count += 1
        await asyncio.sleep(0.05)
    await message.answer(f"✅ <b>Рассылка завершена!</b>\n\n✅ Доставлено: <code>{success_count}</code>\n❌ Не доставлено: <code>{fail_count}</code>", parse_mode="HTML", reply_markup=get_admin_keyboard())
    await state.clear()

@dp.callback_query(lambda c: c.data == "admin_create_promocode")
async def admin_create_promocode(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен")
        return
    await state.set_state(AdminCreatePromocodeStates.waiting_code)
    await callback.message.edit_text("🎫 <b>Создание промокода</b>\n\nВведите название промокода (только латиница и цифры, без пробелов):\n\nПример: <code>SUMMER2024</code>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="admin_back", icon_custom_emoji_id=BUTTON_EMOJI["back"])]]))
    await callback.answer()

@dp.message(AdminCreatePromocodeStates.waiting_code)
async def create_promocode_code(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
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
    await message.answer("📊 <b>Выберите тип промокода:</b>", parse_mode="HTML", reply_markup=kb)

@dp.callback_query(lambda c: c.data and c.data.startswith("promo_type_"))
async def create_promocode_type(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔")
        return
    discount_type = callback.data.split("_")[2]
    await state.update_data(discount_type=discount_type)
    await state.set_state(AdminCreatePromocodeStates.waiting_value)
    if discount_type == "percent":
        await callback.message.edit_text("📊 Введите размер скидки в процентах (число от 1 до 100):\n\nПример: <code>10</code>", parse_mode="HTML")
    else:
        await callback.message.edit_text("💰 Введите сумму скидки или бонуса в рублях (число):\n\nПример: <code>500</code>", parse_mode="HTML")
    await callback.answer()

@dp.message(AdminCreatePromocodeStates.waiting_value)
async def create_promocode_value(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        value = int(message.text.strip())
        if value <= 0:
            await message.answer("❌ Значение должно быть больше 0")
            return
        await state.update_data(discount_value=value)
        await state.set_state(AdminCreatePromocodeStates.waiting_max_uses)
        await message.answer("🔢 Введите максимальное количество активаций промокода:\n\nПример: <code>100</code>", parse_mode="HTML")
    except ValueError:
        await message.answer("❌ Введите число")

@dp.message(AdminCreatePromocodeStates.waiting_max_uses)
async def create_promocode_max_uses(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
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
        await message.answer(f"✅ <b>Промокод успешно создан!</b>\n\n🎫 Код: <code>{code}</code>\n📊 Тип: {type_text}\n🔢 Максимум активаций: <code>{max_uses}</code>", parse_mode="HTML", reply_markup=get_admin_keyboard())
        await state.clear()
    except ValueError:
        await message.answer("❌ Введите число")

@dp.callback_query(lambda c: c.data == "admin_list_promocodes")
async def admin_list_promocodes(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔")
        return
    promocodes = await get_all_promocodes()
    if not promocodes:
        await callback.message.edit_text("📭 <b>Список промокодов пуст</b>", parse_mode="HTML", reply_markup=get_admin_keyboard())
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
        text += f"🔹 <code>{p['code']}</code>\n   📊 {type_text}\n   📊 Использован: {p['used_count']}/{p['max_uses']}\n   🗑️ /del_{p['id']} - удалить\n\n"
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_admin_keyboard())
    await callback.answer()

@dp.message(lambda m: m.text and m.text.startswith("/del_"))
async def delete_promocode_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return
    try:
        promocode_id = int(message.text.split("_")[1])
        await delete_promocode(promocode_id)
        await message.answer("✅ Промокод удален!", reply_markup=get_admin_keyboard())
    except:
        await message.answer("❌ Ошибка при удалении")

@dp.callback_query(lambda c: c.data == "admin_ref_config")
async def admin_ref_config(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔")
        return
    await state.set_state(AdminRefBonusStates.waiting_type)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Фиксированная сумма (₽)", callback_data="ref_type_rubles")],
        [InlineKeyboardButton(text="Процент от покупки (%)", callback_data="ref_type_percent")],
        [InlineKeyboardButton(text="Отмена", callback_data="admin_back", icon_custom_emoji_id=BUTTON_EMOJI["back"])]
    ])
    await callback.message.edit_text("🎁 <b>Настройка реферального бонуса</b>\n\nВыберите тип бонуса за первую покупку приглашённого друга:", parse_mode="HTML", reply_markup=kb)
    await callback.answer()

@dp.callback_query(lambda c: c.data and c.data.startswith("ref_type_"))
async def ref_type_callback(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔")
        return
    bonus_type = callback.data.split("_")[2]
    await state.update_data(bonus_type=bonus_type)
    await state.set_state(AdminRefBonusStates.waiting_value)
    if bonus_type == "rubles":
        await callback.message.edit_text("💰 Введите фиксированную сумму бонуса в рублях:\n\nПример: <code>50</code>", parse_mode="HTML")
    else:
        await callback.message.edit_text("📊 Введите процент от покупки (число от 1 до 100):\n\nПример: <code>10</code>", parse_mode="HTML")
    await callback.answer()

@dp.message(AdminRefBonusStates.waiting_value)
async def ref_value_callback(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        value = int(message.text.strip())
        if value <= 0:
            await message.answer("❌ Значение должно быть больше 0")
            return
        data = await state.get_data()
        bonus_type = data["bonus_type"]
        await update_referral_config(bonus_type, value)
        bonus_text = f"{value} ₽" if bonus_type == "rubles" else f"{value}% от покупки"
        await message.answer(f"✅ <b>Настройки реферальной системы обновлены!</b>\n\n🎁 Тип бонуса: {bonus_text}", parse_mode="HTML", reply_markup=get_admin_keyboard())
        await state.clear()
    except ValueError:
        await message.answer("❌ Введите число")

@dp.callback_query(lambda c: c.data == "admin_crypto_settings")
async def admin_crypto_settings(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔")
        return
    crypto_config = await get_crypto_config()
    mode = crypto_config["payment_mode"]
    currency = crypto_config["currency"]
    amount = crypto_config["amount"]
    manual_text = crypto_config["manual_text"]
    manual_photo = crypto_config["manual_photo"] or "нет"
    text = f"💎 <b>Настройки криптооплаты</b>\n\n📊 Режим: <code>{'Автоматический' if mode == 'auto' else 'Ручной'}</code>\n💰 Валюта: <code>{currency}</code>\n💲 Сумма: <code>{amount}</code>\n📝 Текст ручного режима: <code>{manual_text[:50]}...</code>\n🖼 Фото: <code>{manual_photo}</code>\n\nВыберите действие:"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Переключить режим (авто/ручной)", callback_data="crypto_toggle_mode")],
        [InlineKeyboardButton(text="💰 Настроить валюту и сумму", callback_data="crypto_set_currency")],
        [InlineKeyboardButton(text="📝 Настроить текст ручного режима", callback_data="crypto_set_manual_text")],
        [InlineKeyboardButton(text="🖼 Настроить фото для ручного режима", callback_data="crypto_set_manual_photo")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back", icon_custom_emoji_id=BUTTON_EMOJI["back"])]
    ])
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "crypto_toggle_mode")
async def crypto_toggle_mode(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔")
        return
    crypto_config = await get_crypto_config()
    new_mode = "manual" if crypto_config["payment_mode"] == "auto" else "auto"
    await update_crypto_config(new_mode, crypto_config["currency"], crypto_config["amount"], crypto_config["manual_text"], crypto_config["manual_photo"])
    await callback.answer(f"Режим изменён на {'автоматический' if new_mode == 'auto' else 'ручной'}")
    await admin_crypto_settings(callback, FSMContext())

@dp.callback_query(lambda c: c.data == "crypto_set_currency")
async def crypto_set_currency(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔")
        return
    await state.set_state(AdminCryptoSettingsStates.waiting_currency)
    await callback.message.edit_text("💰 Введите валюту (USDT, BTC, ETH):\n\nПример: <code>USDT</code>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="admin_crypto_settings", icon_custom_emoji_id=BUTTON_EMOJI["back"])]]))
    await callback.answer()

@dp.message(AdminCryptoSettingsStates.waiting_currency)
async def crypto_set_currency_value(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    currency = message.text.strip().upper()
    await state.update_data(currency=currency)
    await state.set_state(AdminCryptoSettingsStates.waiting_amount)
    await message.answer(f"💰 Введите сумму в {currency}:\n\nПример: <code>10</code>", parse_mode="HTML")

@dp.message(AdminCryptoSettingsStates.waiting_amount)
async def crypto_set_amount_value(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        amount = int(message.text.strip())
        data = await state.get_data()
        currency = data.get("currency", "USDT")
        crypto_config = await get_crypto_config()
        await update_crypto_config(crypto_config["payment_mode"], currency, amount, crypto_config["manual_text"], crypto_config["manual_photo"])
        await state.clear()
        await message.answer(f"✅ Настройки криптооплаты обновлены!\n\n💰 Валюта: {currency}\n💲 Сумма: {amount}", parse_mode="HTML", reply_markup=get_admin_keyboard())
    except ValueError:
        await message.answer("❌ Введите число")

@dp.callback_query(lambda c: c.data == "crypto_set_manual_text")
async def crypto_set_manual_text(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔")
        return
    await state.set_state(AdminCryptoSettingsStates.waiting_manual_text)
    await callback.message.edit_text("📝 Введите текст для ручного режима оплаты криптовалютой:\n\nПример:\n<code>Для оплаты переведите USDT TRC20 на кошелек: TXXXX...\nПосле оплаты отправьте скриншот и хэш администратору.</code>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="admin_crypto_settings", icon_custom_emoji_id=BUTTON_EMOJI["back"])]]))
    await callback.answer()

@dp.message(AdminCryptoSettingsStates.waiting_manual_text)
async def crypto_set_manual_text_value(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    manual_text = message.text.strip()
    crypto_config = await get_crypto_config()
    await update_crypto_config(crypto_config["payment_mode"], crypto_config["currency"], crypto_config["amount"], manual_text, crypto_config["manual_photo"])
    await state.clear()
    await message.answer("✅ Текст ручного режима обновлён!", parse_mode="HTML", reply_markup=get_admin_keyboard())

@dp.callback_query(lambda c: c.data == "crypto_set_manual_photo")
async def crypto_set_manual_photo(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔")
        return
    await state.set_state(AdminCryptoSettingsStates.waiting_manual_photo)
    await callback.message.edit_text(
        "🖼 Отправьте фото для ручного режима оплаты.\n\n"
        "Просто отправьте фото в этот чат (как обычное сообщение).\n"
        "Нажмите /skip чтобы пропустить.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="admin_crypto_settings", icon_custom_emoji_id=BUTTON_EMOJI["back"])]])
    )
    await callback.answer()

@dp.message(AdminCryptoSettingsStates.waiting_manual_photo)
async def crypto_set_manual_photo_value(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    photo_file_id = None
    if message.photo:
        photo_file_id = message.photo[-1].file_id
        await message.answer("✅ Фото получено!")
    
    crypto_config = await get_crypto_config()
    await update_crypto_config(crypto_config["payment_mode"], crypto_config["currency"], crypto_config["amount"], crypto_config["manual_text"], photo_file_id)
    
    await state.clear()
    await message.answer("✅ Фото для ручного режима обновлено!", parse_mode="HTML", reply_markup=get_admin_keyboard())

@dp.callback_query(lambda c: c.data == "admin_edit_messages")
async def admin_edit_messages(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔")
        return
    
    messages = await get_all_message_keys()
    text = "✏️ <b>Редактирование сообщений бота</b>\n\nВыберите сообщение для редактирования:\n\n"
    kb = []
    for msg in messages:
        key = msg["message_key"]
        text += f"• <code>{key}</code>\n"
        kb.append([InlineKeyboardButton(text=f"📝 {key}", callback_data=f"edit_msg_{key}")])
    kb.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back", icon_custom_emoji_id=BUTTON_EMOJI["back"])])
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@dp.callback_query(lambda c: c.data and c.data.startswith("edit_msg_"))
async def edit_message_select(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔")
        return
    
    message_key = callback.data.split("_")[2]
    await state.update_data(message_key=message_key)
    await state.set_state(AdminEditMessageStates.waiting_text)
    
    await callback.message.edit_text(
        f"✏️ <b>Редактирование сообщения: {message_key}</b>\n\n"
        f"Отправьте новый текст сообщения (поддерживается HTML):\n\n"
        f"Пример: <code>Привет, это новое сообщение!</code>\n\n"
        f"Нажмите /skip чтобы пропустить изменение текста.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="admin_edit_messages", icon_custom_emoji_id=BUTTON_EMOJI["back"])]])
    )
    await callback.answer()

@dp.message(AdminEditMessageStates.waiting_text)
async def edit_message_text(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    new_text = message.text
    await state.update_data(new_text=new_text)
    await state.set_state(AdminEditMessageStates.waiting_photo)
    
    await message.answer(
        f"✏️ Текст сохранён!\n\n"
        f"Теперь отправьте ФОТО для этого сообщения (или нажмите /skip, чтобы оставить без фото):",
        parse_mode="HTML"
    )

@dp.message(Command("skip"))
async def skip_photo(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    message_key = data["message_key"]
    new_text = data.get("new_text")
    
    if new_text:
        await update_bot_message(message_key, new_text, None)
    else:
        msg_data = await get_bot_message(message_key)
        current_text = msg_data["text"] if msg_data else ""
        await update_bot_message(message_key, current_text, None)
    
    await message.answer(
        f"✅ <b>Сообщение обновлено!</b>\n\n"
        f"🔑 Ключ: <code>{message_key}</code>\n"
        f"📝 Текст обновлён\n"
        f"🖼 Фото удалено",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard()
    )
    await state.clear()

@dp.message(AdminEditMessageStates.waiting_photo)
async def edit_message_photo(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    message_key = data["message_key"]
    new_text = data["new_text"]
    
    photo_file_id = None
    if message.photo:
        photo_file_id = message.photo[-1].file_id
    
    await update_bot_message(message_key, new_text, photo_file_id)
    
    await message.answer(
        f"✅ <b>Сообщение обновлено!</b>\n\n"
        f"🔑 Ключ: <code>{message_key}</code>\n"
        f"📝 Текст обновлён\n"
        f"🖼 Фото: {'добавлено' if photo_file_id else 'не изменено'}",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard()
    )
    await state.clear()

@dp.callback_query(lambda c: c.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔")
        return
    stats = await get_stats()
    await callback.message.edit_text(f"📊 <b>Статистика</b>\n\n👥 Пользователей: <code>{stats['users']}</code>\n💰 Продаж на сумму: <code>{stats['total_sales']} ₽</code>\n🔑 Выдано ключей: <code>{stats['keys_sold']}</code>\n🔑 Осталось ключей: <code>{stats['keys_left']}</code>\n📦 Товаров в продаже: <code>{stats['products_count']}</code>", parse_mode="HTML", reply_markup=get_admin_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_back")
async def admin_back(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(f"{tg_emoji(STICKERS['profile'], '🔐')} <b>Админ-панель</b>", parse_mode="HTML", reply_markup=get_admin_keyboard())
    await callback.answer()

@flask_app.route("/webhook/payment", methods=["POST"])
def payment_webhook():
    data = request.get_json()
    status = data.get("status")
    order_id = data.get("order_id")
    amount = int(data.get("amount", 0))
    if status == "success" and order_id:
        user_id = None
        for uid, info in pending_payments.items():
            if info["payment_id"] == order_id:
                user_id = uid
                break
        if user_id:
            async def update_balance():
                current = await get_balance(user_id)
                await update_user_balance(user_id, current + amount)
                await bot.send_message(user_id, f"✅ <b>Баланс пополнен!</b>\n\nСумма: <code>{amount} ₽</code>\nНовый баланс: <code>{current + amount} ₽</code>", parse_mode="HTML")
                del pending_payments[user_id]
            asyncio.run(update_balance())
            return jsonify({"status": "ok"}), 200
    return jsonify({"status": "error"}), 400

@flask_app.route("/payment/success", methods=["GET"])
def payment_success():
    return "Оплата прошла успешно! Можете вернуться в бота.", 200

@flask_app.route("/payment/fail", methods=["GET"])
def payment_fail():
    return "Оплата не прошла. Попробуйте снова.", 200

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
