import os
import asyncio
import aiohttp
import hashlib
import hmac
from urllib.parse import urlencode

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from config import (
    PLATEGA_MERCHANT_ID,
    PLATEGA_API_SECRET,
    CRYPTOBOT_TOKEN,
    RAILWAY_URL,
)
from database import (
    save_pending_order,
    get_pending_order,
    update_order_status,
    add_balance,
    get_balance,
    get_crypto_fee,
)
from keyboards import deposit_keyboard, back_keyboard, cancel_keyboard
from utils import generate_order_id, verify_crypto_signature, format_price
from states import DepositStates

router = Router()


# ===================== Platega =====================

def generate_platega_signature(params: dict) -> str:
    sorted_params = sorted(params.items())
    sign_string = urlencode(sorted_params) + f"&{PLATEGA_API_SECRET}"
    return hashlib.md5(sign_string.encode()).hexdigest()


async def create_platega_invoice(user_id: int, amount: int) -> str | None:
    order_id = generate_order_id(user_id, "plg")
    params = {
        "merchant_id": PLATEGA_MERCHANT_ID,
        "amount": amount,
        "order_id": order_id,
        "currency": "RUB",
        "description": f"Пополнение баланса SWEG SHOP #{user_id}",
        "success_url": f"{RAILWAY_URL}/payment/success",
        "fail_url": f"{RAILWAY_URL}/payment/fail",
        "callback_url": f"{RAILWAY_URL}/webhook/platega",
    }
    params["sign"] = generate_platega_signature(params)

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post("https://platega.com/api/create_invoice", data=params, timeout=10) as resp:
                data = await resp.json()
                if data.get("status") == "success":
                    await save_pending_order(user_id, order_id, amount, "platega")
                    return data.get("data", {}).get("payment_url")
                else:
                    print(f"[Platega] Ошибка создания счёта: {data}")
        except Exception as e:
            print(f"[Platega] Исключение: {e}")
    return None


# ===================== CryptoBot =====================

async def create_crypto_invoice(user_id: int, amount: int, bot_username: str = "") -> str | None:
    if not CRYPTOBOT_TOKEN:
        return None

    payload_token = generate_order_id(user_id, "crypto").split("_", 2)[2]
    payload = f"{user_id}_{payload_token}"
    order_id = f"cry_{user_id}_{payload_token}"

    headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
    params = {
        "amount": amount,
        "asset": "USDT",
        "description": f"Пополнение баланса SWEG SHOP #{user_id}",
        "payload": payload,
        "paid_btn_name": "openBot",
        "paid_btn_url": f"https://t.me/{bot_username}" if bot_username else "https://t.me/",
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                "https://pay.crypt.bot/api/createInvoice",
                headers=headers,
                json=params,
                timeout=10
            ) as resp:
                data = await resp.json()
                if data.get("ok"):
                    await save_pending_order(user_id, order_id, amount, "crypto")
                    return data["result"]["pay_url"]
                else:
                    print(f"[CryptoBot] Ошибка: {data}")
        except Exception as e:
            print(f"[CryptoBot] Исключение: {e}")
    return None


# ===================== Handlers =====================

@router.callback_query(F.data.startswith("dep_amount_"))
async def deposit_preset(callback: CallbackQuery, state: FSMContext):
    amount = int(callback.data.split("_")[2])
    await state.update_data(amount=amount)
    await callback.message.edit_text(
        f"💰 <b>Пополнение на {format_price(amount)}</b>\n\nВыберите способ оплаты:",
        reply_markup=deposit_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "dep_custom")
async def deposit_custom(callback: CallbackQuery, state: FSMContext):
    await state.set_state(DepositStates.waiting_amount)
    await callback.message.edit_text(
        "✏️ <b>Введите сумму пополнения</b> (минимум 10 ₽):",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(DepositStates.waiting_amount)
async def deposit_custom_amount(message: Message, state: FSMContext):
    if not message.text.isdigit() or int(message.text) < 10:
        await message.answer("❌ Введите сумму от 10 ₽:", reply_markup=cancel_keyboard())
        return
    await state.update_data(amount=int(message.text))
    await message.answer(
        f"💰 <b>Пополнение на {format_price(int(message.text))}</b>\n\nВыберите способ оплаты:",
        reply_markup=deposit_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "deposit_platega")
async def deposit_platega_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    amount = data.get("amount")
    if not amount:
        await callback.answer("Сначала выберите сумму", show_alert=True)
        return

    await callback.answer("⏳ Создаём счёт...")
    url = await create_platega_invoice(callback.from_user.id, amount)
    if url:
        await callback.message.edit_text(
            f"💳 <b>Счёт Platega на {format_price(amount)}</b>\n\n"
            f"Нажмите кнопку ниже, чтобы оплатить:\n"
            f"<a href='{url}'>Перейти к оплате</a>",
            reply_markup=back_keyboard(),
            parse_mode="HTML",
            disable_web_page_preview=True
        )
    else:
        await callback.message.answer(
            "❌ Не удалось создать счёт. Попробуйте позже.",
            reply_markup=back_keyboard()
        )


@router.callback_query(F.data == "deposit_crypto")
async def deposit_crypto_handler(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    amount = data.get("amount")
    if not amount:
        await callback.answer("Сначала выберите сумму", show_alert=True)
        return

    await callback.answer("⏳ Создаём счёт...")
    me = await bot.me()
    url = await create_crypto_invoice(callback.from_user.id, amount, me.username)
    if url:
        await callback.message.edit_text(
            f"₿ <b>Счёт CryptoBot на {format_price(amount)}</b>\n\n"
            f"Нажмите кнопку ниже, чтобы оплатить:\n"
            f"<a href='{url}'>Перейти к оплате</a>",
            reply_markup=back_keyboard(),
            parse_mode="HTML",
            disable_web_page_preview=True
        )
    else:
        await callback.message.answer(
            "❌ Не удалось создать счёт. Проверьте настройки CryptoBot.",
            reply_markup=back_keyboard()
        )


# ===================== Webhooks =====================

# Глобальный event loop, задаётся из main.py
main_loop = None


def setup_payment_webhooks(flask_app, bot: Bot):
    from flask import request, jsonify

    @flask_app.route("/webhook/platega", methods=["POST"])
    def platega_webhook():
        data = request.json or {}
        print(f"[Platega Webhook] {data}")

        status = data.get("status")
        order_id = data.get("order_id")

        signature = data.get("sign")
        if signature:
            check_params = {k: v for k, v in data.items() if k != "sign"}
            expected = generate_platega_signature(check_params)
            if not hmac.compare_digest(signature, expected):
                return jsonify({"status": "invalid_signature"}), 403

        if status == "CONFIRMED" and order_id:
            order = get_pending_order_sync(order_id)
            if order and order["status"] == "pending":
                user_id = order["user_id"]
                amount = order["amount"]

                async def process():
                    await update_order_status(order_id, "paid")
                    current = await get_balance(user_id)
                    await add_balance(user_id, amount)
                    try:
                        await bot.send_message(
                            user_id,
                            f"✅ <b>Оплата через Platega получена!</b>\n\n"
                            f"💰 Сумма: <code>{format_price(amount)}</code>\n"
                            f"📊 Баланс: <code>{format_price(current + amount)}</code>",
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        print(f"[Platega Webhook] Не удалось уведомить {user_id}: {e}")

                asyncio.run_coroutine_threadsafe(process(), main_loop)
                return jsonify({"status": "ok"}), 200

        return jsonify({"status": "ignored"}), 200

    @flask_app.route("/webhook/crypto", methods=["POST"])
    def crypto_webhook():
        signature = request.headers.get("crypto-pay-api-signature")
        body = request.data

        if not verify_crypto_signature(signature, body):
            return jsonify({"status": "invalid_signature"}), 403

        data = request.json or {}
        print(f"[Crypto Webhook] {data}")

        if data.get("update_type") == "invoice_paid":
            obj = data.get("update_object", {})
            payload = obj.get("payload", "")
            try:
                user_id_str, token = payload.split("_", 1)
                user_id = int(user_id_str)
                amount = int(float(obj.get("amount", 0)))
                order_id = f"cry_{user_id}_{token}"

                async def process():
                    order = await get_pending_order(order_id)
                    if order and order["status"] == "pending":
                        await update_order_status(order_id, "paid")
                        current = await get_balance(user_id)
                        await add_balance(user_id, amount)
                        try:
                            await bot.send_message(
                                user_id,
                                f"✅ <b>Оплата через Crypto Pay получена!</b>\n\n"
                                f"💰 Баланс пополнен на <code>{format_price(amount)}</code>\n"
                                f"📊 Текущий баланс: <code>{format_price(current + amount)}</code>",
                                parse_mode="HTML"
                            )
                        except Exception as e:
                            print(f"[Crypto Webhook] Не удалось уведомить {user_id}: {e}")

                asyncio.run_coroutine_threadsafe(process(), main_loop)
            except Exception as e:
                print(f"[Crypto Webhook] Ошибка: {e}")

        return jsonify({"status": "ok"}), 200

    @flask_app.route("/payment/success", methods=["GET"])
    def payment_success():
        return "✅ Оплата прошла успешно! Возвращайтесь в бот.", 200

    @flask_app.route("/payment/fail", methods=["GET"])
    def payment_fail():
        return "❌ Оплата не прошла. Попробуйте снова.", 200

    @flask_app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "alive"}), 200


def get_pending_order_sync(order_id: str):
    from database import pool
    if not pool or not main_loop:
        return None
    try:
        return asyncio.run_coroutine_threadsafe(
            _fetch_order(order_id), main_loop
        ).result(timeout=5)
    except Exception as e:
        print(f"[get_pending_order_sync] {e}")
        return None


async def _fetch_order(order_id: str):
    from database import get_pending_order
    return await get_pending_order(order_id)
