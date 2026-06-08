import asyncio
import os
import uuid
import hashlib
import hmac
import socket        
import json           
import urllib.request  
from datetime import datetime, timedelta
from threading import Thread
from flask import Flask, request, jsonify
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
import aiohttp
import requests  

from config import BOT_TOKEN, ADMIN_IDS, RAILWAY_URL, CHANNEL_ID, MERCHANT_ID, API_SECRET
try:
    from config import CRYPTO_PAY_TOKEN
except ImportError:
    CRYPTO_PAY_TOKEN = "YOUR_CRYPTO_BOT_TOKEN"

from database import (
    connect_db, add_user, get_balance, get_all_products,
    add_product, add_keys_to_product, get_unused_key,
    mark_key_as_used, update_user_balance, add_purchase, get_user_purchases, get_stats,
    get_all_users, create_promocode, get_promocode, use_promocode, check_promocode_used,
    get_all_promocodes, delete_promocode, get_referrer, get_referrals_count, get_paid_referrals_count,
    get_referral_config, update_referral_config, add_balance, get_product_by_id,
    delete_product, get_keys_by_product, delete_key, mark_purchased, has_user_purchased,
    get_setting, update_setting
)

_orig_getaddrinfo = socket.getaddrinfo

def _patched_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    if host == "pay.cryptobot.net":
        try:
            req = urllib.request.Request(
                "https://1.1.1.1/dns-query?name=pay.cryptobot.net",
                headers={"Accept": "application/dns-json"}
            )
            with urllib.request.urlopen(req, timeout=3) as response:
                dns_data = json.loads(response.read().decode())
                if "Answer" in dns_data:
                    ips = [item["data"] for item in dns_data["Answer"] if item["type"] == 1]
                    if ips:
                        return _orig_getaddrinfo(ips[0], port, family, type, proto, flags)
        except Exception as e:
            print(f"[DNS Патч] Ошибка динамического разрешения, откат на резерв: {e}", flush=True)
            return _orig_getaddrinfo("172.67.73.187", port, family, type, proto, flags)
            
    return _orig_getaddrinfo(host, port, family, type, proto, flags)

socket.getaddrinfo = _patched_getaddrinfo

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
main_loop = None  

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
    waiting_method = State() 

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

class AdminCustomTextStates(StatesGroup):
    waiting_text = State() 

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

async def create_crypto_payment(amount: int, order_id: str, user_id: int) -> str:
    url = "https://pay.cryptobot.net/api/createInvoice"
    
    headers = {
        "Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN
    }
    
    payload = {
        "amount": str(amount),
        "fiat": "RUB",
        "currency_type": "fiat",
        "accepted_assets": ["USDT", "TON", "BTC", "ETH"],
        "description": f"Пополнение баланса №{order_id}",
        "payload": f"{user_id}_{amount}"
    }
    
    from aiohttp.resolver import ThreadedResolver
    connector = aiohttp.TCPConnector(resolver=ThreadedResolver())
    
    try:
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("ok"):
                        return data["result"]["pay_url"]
                    else:
                        print(f"[CryptoBot] Ошибка API: {data}", flush=True)
                else:
                    print(f"[CryptoBot] Ошибка сервера: {resp.status}", flush=True)
                    
    except Exception as e:
        print(f"[CryptoBot] Ошибка сети: {e}", flush=True)
        
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
            InlineKeyboardButton(text="Активировать промокод", callback_data="profile_activate_promocode", icon_custom_emoji_id=BUTTON_EMOJI["promocode"]),
            InlineKeyboardButton(text="Реферальная система", callback_data="profile_referral", icon_custom_emoji_id=BUTTON_EMOJI["referral"])
        ],
        [
            InlineKeyboardButton(text="Главное меню", callback_data="menu_main", icon_custom_emoji_id=BUTTON_EMOJI["home"])
        ]
    ])

def get_admin_keyboard(shop_mode="auto"):
    mode_text = "🤖 Режим: Авто" if shop_mode == "auto" else "👨‍💻 Режим: Ручной"
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
            InlineKeyboardButton(text="Настройка рефералов", callback_data="admin_ref_config", icon_custom_emoji_id=BUTTON_EMOJI["referral"]),
        ],
        [
            InlineKeyboardButton(text=mode_text, callback_data="admin_toggle_mode"),
            InlineKeyboardButton(text="📝 Текст кастома", callback_data="admin_change_custom_text")
        ],
        [
            InlineKeyboardButton(text="Управление товарами", callback_data="admin_manage_products", icon_custom_emoji_id=BUTTON_EMOJI["delete_product"]),
            InlineKeyboardButton(text="Управление ключами", callback_data="admin_manage_keys", icon_custom_emoji_id=BUTTON_EMOJI["delete_key"])
        ],
        [
            InlineKeyboardButton(text="Статистика", callback_data="admin_stats", icon_custom_emoji_id=BUTTON_EMOJI["stats"]),
            InlineKeyboardButton(text="Главное меню", callback_data="menu_main", icon_custom_emoji_id=BUTTON_EMOJI["home"])
        ]
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
        f"{tg_emoji(STICKERS['payment_icon'], '💳')} <b>Оплата:</b> Platega (СБП), Crypto Pay (Криптовалюта)\n\n"
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

@dp.callback_query(lambda c: c.data == "profile_referral")
async def profile_referral(callback: CallbackQuery):
    user_id = callback.from_user.id
    bot_username = (await bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    total_referrals = await get_referrals_count(user_id)
    paid_referrals = await get_paid_referrals_count(user_id)
    config = await get_referral_config()
    
    if config["bonus_type"] == "rubles":
        bonus_text = f"{config['bonus_value']} ₽"
    else:
        bonus_text = f"{config['bonus_value']}% от покупки"
    
    text = (
        f"{tg_emoji(BUTTON_EMOJI['referral'], '👥')} <b>Реферальная система</b>\n\n"
        f"🔗 <b>Ваша ссылка:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"👥 Приглашено друзей: <code>{total_referrals}</code>\n"
        f"✅ Из них купили: <code>{paid_referrals}</code>\n"
        f"🎁 <b>Награда за покупку друга:</b> {bonus_text}\n\n"
        f"💡 Награда начисляется после первой покупки вашего друга!"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="menu_profile", icon_custom_emoji_id=BUTTON_EMOJI["back"])]]))
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
    shop_mode = await get_setting("shop_mode")
    if shop_mode == "custom":
        custom_text = await get_setting("custom_text")
        await callback.message.answer(custom_text, parse_mode="HTML")
        await callback.answer()
        return

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
    shop_mode = await get_setting("shop_mode")
    if shop_mode == "custom":
        custom_text = await get_setting("custom_text")
        await message.answer(custom_text, parse_mode="HTML")
        await state.clear()
        return

    try:
        amount = int(message.text.strip())
        if amount < 10 or amount > 50000:
            await message.answer(
                f"{tg_emoji(STICKERS['keys_count'], '❌')} Сумма должна быть от 10 до 50000 ₽\n\nПопробуйте снова:",
                parse_mode="HTML"
            )
            return
        
        await state.update_data(amount=amount)
        await state.set_state(DepositStates.waiting_method)
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="💳 СБП (Platega)", callback_data="pay_method_platega"),
                InlineKeyboardButton(text="🪙 Криптовалюта (CryptoPay)", callback_data="pay_method_crypto")
            ],
            [InlineKeyboardButton(text="Отмена", callback_data="menu_profile", icon_custom_emoji_id=BUTTON_EMOJI["back"])]
        ])
        
        await message.answer(
            f"✨ <b>Сумма пополнения: {amount} ₽</b>\n\nВыберите предпочтительный метод оплаты:",
            parse_mode="HTML",
            reply_markup=kb
        )
        
    except ValueError:
        await message.answer(
            f"{tg_emoji(STICKERS['keys_count'], '❌')} Введите <b>число</b>!\n\nПример: <code>500</code>",
            parse_mode="HTML"
        )

@dp.callback_query(DepositStates.waiting_method, lambda c: c.data in ["pay_method_platega", "pay_method_crypto"])
async def process_deposit_method(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    amount = data.get("amount")
    await state.clear()
    
    order_id = str(uuid.uuid4())[:8]
    pending_payments[callback.from_user.id] = {
        "amount": amount,
        "order_id": order_id,
        "status": "pending"
    }
    
    await callback.answer("Генерируем счёт...")
    
    if callback.data == "pay_method_platega":
        await callback.message.edit_text(
            f"⏳ <b>Создаем безопасную сессию СБП...</b>\nПожалуйста, подождите.", parse_mode="HTML"
        )
        payment_url = await create_platega_payment(amount, order_id, callback.from_user.id)
        method_name = "Platega (СБП)"
    else:
        await callback.message.edit_text(
            f"⏳ <b>Связываемся со шлюзом CryptoBot API...</b>\nПожалуйста, подождите пару секунд.", parse_mode="HTML"
        )
        payment_url = await create_crypto_payment(amount, order_id, callback.from_user.id)
        method_name = "Crypto Pay (Криптовалюта)"
    
    if not payment_url:
        await callback.message.edit_text(
            f"{tg_emoji(STICKERS['keys_count'], '❌')} <b>Платежная система временно недоступна</b>\n\n"
            f"Свяжитесь с администратором для ручного пополнения баланса.\n\n"
            f"👤 Админ: @nikita1055",
            parse_mode="HTML",
            reply_markup=get_profile_keyboard()
        )
        return
    
    await callback.message.edit_text(
        f"{tg_emoji(STICKERS['payment_method'], '💳')} <b>Оплата через {method_name}</b>\n\n"
        f"Сумма к оплате: <code>{amount} ₽</code>\n\n"
        f"🔗 <a href='{payment_url}'>НАЖМИТЕ ТУТ ЧТOБЫ ОПЛАТИТЬ</a>\n\n"
        f"🆔 Транзакция: <code>{order_id}</code>\n\n"
        f"⚡ Баланс обновится автоматически в течение 5 секунд после оплаты!",
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=get_profile_keyboard()
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
    shop_mode = await get_setting("shop_mode")
    if shop_mode == "custom":
        custom_text = await get_setting("custom_text")
        await callback.message.answer(custom_text, parse_mode="HTML")
        await callback.answer()
        return

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
    
    if not await has_user_purchased(user_id):
        await mark_purchased(user_id)
        
        referrer_id = await get_referrer(user_id)
        if referrer_id:
            config = await get_referral_config()
            if config and config["bonus_value"] > 0:
                if config["bonus_type"] == "rubles":
                    await add_balance(referrer_id, config["bonus_value"])
                    await bot.send_message(
                        referrer_id,
                        f"🎉 <b>Реферальный бонус!</b>\n\n"
                        f"Ваш друг @{callback.from_user.username or callback.from_user.first_name} совершил первую покупку!\n"
                        f"💰 Вы получили: <code>{config['bonus_value']} ₽</code>",
                        parse_mode="HTML"
                    )
                elif config["bonus_type"] == "percent":
                    bonus_amount = int(product["price"] * config["bonus_value"] / 100)
                    await add_balance(referrer_id, bonus_amount)
                    await bot.send_message(
                        referrer_id,
                        f"🎉 <b>Реферальный бонус!</b>\n\n"
                        f"Ваш друг @{callback.from_user.username or callback.from_user.first_name} совершил первую покупку на {product['price']} ₽!\n"
                        f"💰 Вы получили: <code>{bonus_amount} ₽ ({config['bonus_value']}% от покупки)</code>",
                        parse_mode="HTML"
                    )
    
    from database import pool
    async with pool.acquire() as conn:
        keys_left = await conn.fetchval("SELECT COUNT(*) FROM keys_store WHERE product_id = $1 AND used = FALSE", product_id)
    
    vip_link = await create_vip_link(user_id, 30)
    if not vip_link:
        vip_link = "https://t.me/+a5AssXS77w01Yjky"
    
    await callback.message.answer(
        f"{tg_emoji(STICKERS['product_selected'], '✅')} <b>Покупка успешна!</b>\n\n"
        f"{tg_emoji(STICKERS['keys_count'], '🔑')} <b>Ключей в наличии:</b> {keys_left}\n"
        f"{tg_emoji(STICKERS['price_icon'], '💰')} <b>Цена:</b> {product['price']} ₽\n\n"
        f"{tg_emoji(STICKERS['product_selected'], '🔑')} <b>Ваш ключ:</b> <code>{key_row['key_value']}</code>\n\n"
        f"🔗 <b>Ссылка на VIP канал (одноразовая):</b>\n"
        f"<a href='{vip_link}'>Нажмите для вступления</a>\n\n"
        f"⚠️ Ссылка действительна 30 дней и только для вас!",
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="В меню", callback_data="menu_main", icon_custom_emoji_id=BUTTON_EMOJI["home"])]])
    )
    await callback.message.delete()
    await callback.answer("Покупка успешна!")

@dp.message(Command("admin"))
async def admin_cmd(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return
    
    shop_mode = await get_setting("shop_mode")
    await message.answer(
        f"{tg_emoji(STICKERS['profile'], '🔐')} <b>Админ-панель</b>",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard(shop_mode)
    )

@dp.callback_query(lambda c: c.data == "admin_toggle_mode")
async def admin_toggle_mode(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен")
        return
    
    current_mode = await get_setting("shop_mode")
    new_mode = "custom" if current_mode == "auto" else "auto"
    await update_setting("shop_mode", new_mode)
    
    status_text = "👨‍💻 РУЧНОЙ (Кастомный текст)" if new_mode == "custom" else "🤖 АВТО (Автоплатежи)"
    await callback.answer(f"Режим изменен на: {status_text}")
    await callback.message.edit_reply_markup(reply_markup=get_admin_keyboard(new_mode))

@dp.callback_query(lambda c: c.data == "admin_change_custom_text")
async def admin_change_custom_text(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен")
        return
        
    current_text = await get_setting("custom_text")
    await state.set_state(AdminCustomTextStates.waiting_text)
    await callback.message.answer(
        f"📝 <b>Текущий текст ручной продажи:</b>\n\n{current_text}\n\n"
        f"Введите новый текст, который будут видеть пользователи в режиме ручной продажи (поддерживается HTML разметка):",
        parse_mode="HTML"
    )
    await callback.answer()

@dp.message(AdminCustomTextStates.waiting_text)
async def process_custom_text_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
        
    new_text = message.text.strip()
    await update_setting("custom_text", new_text)
    await state.clear()
    
    shop_mode = await get_setting("shop_mode")
    await message.answer(
        "✅ <b>Текст ручной продажи успешно обновлен!</b>",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard(shop_mode)
    )

@dp.callback_query(lambda c: c.data == "admin_add_product")
async def admin_add_product(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
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
    
    shop_mode = await get_setting("shop_mode")
    await message.answer(
        f"✅ Товар добавлен! {len(keys)} ключей\n📦 ID товара: {product_id}",
        reply_markup=get_admin_keyboard(shop_mode)
    )
    await state.clear()

@dp.callback_query(lambda c: c.data == "admin_add_keys")
async def admin_add_keys(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен")
        return
    products = await get_all_products()
    if not products:
        shop_mode = await get_setting("shop_mode")
        await callback.message.edit_text(
            "❌ Сначала добавьте товар",
            reply_markup=get_admin_keyboard(shop_mode)
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
    if not is_admin(callback.from_user.id):
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
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    product_id = data["product_id"]
    keys = [k.strip() for k in message.text.split("\n") if k.strip()]
    await add_keys_to_product(product_id, keys)
    
    shop_mode = await get_setting("shop_mode")
    await message.answer(
        f"✅ Добавлено {len(keys)} ключей для товара ID {product_id}",
        reply_markup=get_admin_keyboard(shop_mode)
    )
    await state.clear()

@dp.callback_query(lambda c: c.data == "admin_manage_products")
async def admin_manage_products(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔")
        return
    
    products = await get_all_products()
    if not products:
        await callback.message.edit_text(
            "📭 <b>Список товаров пуст</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="admin_back", icon_custom_emoji_id=BUTTON_EMOJI["back"])]])
        )
        await callback.answer()
        return
    
    text = "📦 <b>Список товаров</b>\n\n"
    for p in products:
        text += f"🆔 ID: {p['id']}\n"
        text += f"📛 Название: {p['name']}\n"
        text += f"💰 Цена: {p['price']} ₽\n"
        text += f"🗑️ /delproduct_{p['id']} - удалить товар\n\n"
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="admin_back", icon_custom_emoji_id=BUTTON_EMOJI["back"])]]))
    await callback.answer()

@dp.message(lambda m: m.text and m.text.startswith("/delproduct_"))
async def delete_product_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return
    try:
        product_id = int(message.text.split("_")[1])
        await delete_product(product_id)
        shop_mode = await get_setting("shop_mode")
        await message.answer("✅ Товар удален!", reply_markup=get_admin_keyboard(shop_mode))
    except:
        await message.answer("❌ Ошибка при удалении")

@dp.callback_query(lambda c: c.data == "admin_manage_keys")
async def admin_manage_keys(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔")
        return
    
    products = await get_all_products()
    if not products:
        await callback.message.edit_text(
            "📭 <b>Сначала добавьте товар</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="admin_back", icon_custom_emoji_id=BUTTON_EMOJI["back"])]])
        )
        await callback.answer()
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{p['name']} (ID: {p['id']})", callback_data=f"showkeys_{p['id']}")]
        for p in products
    ] + [[InlineKeyboardButton(text="Назад", callback_data="admin_back", icon_custom_emoji_id=BUTTON_EMOJI["back"])]])
    
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
        await callback.message.edit_text(
            f"🔑 <b>Ключи для товара {product['name']}</b>\n\nСписок пуст",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="admin_manage_keys", icon_custom_emoji_id=BUTTON_EMOJI["back"])]])
        )
        await callback.answer()
        return
    
    text = f"🔑 <b>Ключи для товара {product['name']}</b>\n\n"
    for k in keys:
        status = "✅ Использован" if k["used"] else "🟢 Доступен"
        text += f"🆔 ID: {k['id']} | {k['key_value']} | {status}\n"
        text += f"🗑️ /delkey_{k['id']} - удалить ключ\n\n"
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="admin_manage_keys", icon_custom_emoji_id=BUTTON_EMOJI["back"])]]))
    await callback.answer()

@dp.message(lambda m: m.text and m.text.startswith("/delkey_"))
async def delete_key_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return
    try:
        key_id = int(message.text.split("_")[1])
        await delete_key(key_id)
        shop_mode = await get_setting("shop_mode")
        await message.answer("✅ Ключ удален!", reply_markup=get_admin_keyboard(shop_mode))
    except:
        await message.answer("❌ Ошибка при удалении")

@dp.callback_query(lambda c: c.data == "admin_add_balance")
async def admin_add_balance(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
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
    if not is_admin(message.from_user.id):
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
        
        shop_mode = await get_setting("shop_mode")
        await message.answer(
            f"✅ <b>Баланс успешно выдан!</b>\n\n"
            f"👤 Пользователь: <code>{user_id}</code>\n"
            f"💰 Сумма: <code>{amount} ₽</code>\n"
            f"📊 Новый баланс: <code>{current_balance + amount} ₽</code>",
            parse_mode="HTML",
            reply_markup=get_admin_keyboard(shop_mode)
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
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен")
        return
    await state.set_state(AdminBroadcastStates.waiting_message)
    await callback.message.edit_text(
        "📢 <b>Рассылка сообщения</b>\n\n"
        "Введите text сообщения для рассылки всем пользователям:\n\n"
        "Поддерживается HTML разметка",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="admin_back", icon_custom_emoji_id=BUTTON_EMOJI["back"])]])
    )
    await callback.answer()

@dp.message(AdminBroadcastStates.waiting_message)
async def process_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
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
    
    shop_mode = await get_setting("shop_mode")
    await message.answer(
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"✅ Доставлено: <code>{success_count}</code>\n"
        f"❌ Не доставлено: <code>{fail_count}</code>",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard(shop_mode)
    )
    await state.clear()

@dp.callback_query(lambda c: c.data == "admin_create_promocode")
async def admin_create_promocode(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
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
    
    await message.answer(
        "📊 <b>Выберите тип промокода:</b>",
        parse_mode="HTML",
        reply_markup=kb
    )

@dp.callback_query(lambda c: c.data and c.data.startswith("promo_type_"))
async def create_promocode_type(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
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
    if not is_admin(message.from_user.id):
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
        
        shop_mode = await get_setting("shop_mode")
        await message.answer(
            f"✅ <b>Промокод успешно создан!</b>\n\n"
            f"🎫 Код: <code>{code}</code>\n"
            f"📊 Тип: {type_text}\n"
            f"🔢 : <code>{max_uses}</code>",
            parse_mode="HTML",
            reply_markup=get_admin_keyboard(shop_mode)
        )
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Введите число")

@dp.callback_query(lambda c: c.data == "admin_list_promocodes")
async def admin_list_promocodes(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔")
        return
    
    promocodes = await get_all_promocodes()
    shop_mode = await get_setting("shop_mode")
    
    if not promocodes:
        await callback.message.edit_text(
            "📭 <b>Список промокодов пуст</b>",
            parse_mode="HTML",
            reply_markup=get_admin_keyboard(shop_mode)
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
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_admin_keyboard(shop_mode))
    await callback.answer()

@dp.message(lambda m: m.text and m.text.startswith("/del_"))
async def delete_promocode_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return
    try:
        promocode_id = int(message.text.split("_")[1])
        await delete_promocode(promocode_id)
        shop_mode = await get_setting("shop_mode")
        await message.answer("✅ Промокод удален!", reply_markup=get_admin_keyboard(shop_mode))
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
    await callback.message.edit_text(
        "🎁 <b>Настройка реферального бонуса</b>\n\n"
        "Выберите тип бонуса за первую покупку приглашённого друга:",
        parse_mode="HTML",
        reply_markup=kb
    )
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
        await callback.message.edit_text(
            "💰 Введите фиксированную сумму бонуса в рублях:\n\nПример: <code>50</code>",
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            "📊 Введите процент от покупки (число от 1 до 100):\n\nПример: <code>10</code>",
            parse_mode="HTML"
        )
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
        
        shop_mode = await get_setting("shop_mode")
        await message.answer(
            f"✅ <b>Настройки реферальной системы обновлены!</b>\n\n"
            f"🎁 Тип бонуса: {bonus_text}",
            parse_mode="HTML",
            reply_markup=get_admin_keyboard(shop_mode)
        )
        await state.clear()
    except ValueError:
        await message.answer("❌ Введите число")

@dp.callback_query(lambda c: c.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔")
        return
    stats = await get_stats()
    shop_mode = await get_setting("shop_mode")
    await callback.message.edit_text(
        f"📊 <b>Статистика</b>\n\n"
        f"👥 Пользователей: <code>{stats['users']}</code>\n"
        f"💰 Продаж на сумму: <code>{stats['total_sales']} ₽</code>\n"
        f"🔑 Выдано ключей: <code>{stats['keys_sold']}</code>\n"
        f"🔑 Осталось ключей: <code>{stats['keys_left']}</code>\n"
        f"📦 Товаров в продаже: <code>{stats['products_count']}</code>",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard(shop_mode)
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_back")
async def admin_back(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    shop_mode = await get_setting("shop_mode")
    await callback.message.edit_text(
        f"{tg_emoji(STICKERS['profile'], '🔐')} <b>Админ-панель</b>",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard(shop_mode)
    )
    await callback.answer()
    
async def process_successful_payment(user_id: int, rub_amount: int):
    try:
        current_balance = await get_balance(user_id)
        new_balance = current_balance + rub_amount
        await update_user_balance(user_id, new_balance)
        
        await bot.send_message(
            chat_id=user_id,
            text=f"✅ {tg_emoji(STICKERS['product_selected'], '✨')} <b>Оплата успешно получена!</b>\n\n"
                 f"💰 Ваш игровой баланс пополнен на <b>{rub_amount} ₽</b>\n"
                 f"📊 Актуальный профиль: <code>{new_balance} ₽</code>",
            parse_mode="HTML"
        )
        print(f"[Выдача] Успешно начислен баланс {rub_amount} руб для пользователя {user_id}", flush=True)
    except Exception as e:
        print(f"[Выдача] Ошибка уведомления пользователя {user_id}: {e}", flush=True)


@flask_app.route("/webhook/payment", methods=["POST"])
def payment_webhook():
    return jsonify({"status": "ok"}), 200

@flask_app.route("/webhook/crypto", methods=["POST"])
def crypto_webhook():
    signature = request.headers.get("crypto-pay-api-signature")
    if not signature:
        return "Unauthorized", 401
        
    body = request.data
    secret = hashlib.sha256(CRYPTO_PAY_TOKEN.encode()).digest()
    calc_signature = hmac.new(secret, body, hashlib.sha256).hexdigest()
    
    if signature != calc_signature:
        print("[Webhook] Попытка подделки подписи заблокирована!", flush=True)
        return "Forbidden", 403
        
    data = request.json
    if data.get("update_type") == "invoice_paid":
        payload_str = data["update_object"].get("payload")
        if payload_str:
            try:
                user_id_str, rub_amount_str = payload_str.split("_")
                user_id = int(user_id_str)
                rub_amount = int(rub_amount_str)
                
                if main_loop:
                    asyncio.run_coroutine_threadsafe(
                        process_successful_payment(user_id, rub_amount), main_loop
                    )
            except Exception as e:
                print(f"[Webhook] Ошибка разбора payload: {e}", flush=True)
                
    return jsonify({"status": "ok"}), 200

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
    global main_loop
    main_loop = asyncio.get_running_loop() 
    
    await connect_db()
    await bot.delete_webhook(drop_pending_updates=True)
    
    thread = Thread(target=run_flask, daemon=True)
    thread.start()
    
    print("Бот успешно запущен и готов к работе!", flush=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
