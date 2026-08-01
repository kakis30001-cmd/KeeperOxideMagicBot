from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext

from database import (
    ensure_user,
    get_balance,
    get_all_categories,
    get_products_by_category,
    get_product_by_id,
    count_keys,
    get_unused_key,
    mark_key_as_used,
    add_purchase,
    add_balance,
    get_user_purchases,
    get_referrals_count,
    get_paid_referrals_count,
    mark_purchased,
    get_promocode,
    use_promocode,
    check_promocode_used,
    get_referral_config,
    get_referrer,
)
from keyboards import (
    main_menu_keyboard,
    categories_keyboard,
    products_keyboard,
    product_detail_keyboard,
    back_keyboard,
    cancel_keyboard,
)
from utils import is_admin, escape_html, format_price, apply_discount
from states import DepositStates

router = Router()


async def send_main_menu(message: Message, user_id: int):
    balance = await get_balance(user_id)
    text = (
        f"👋 <b>Добро пожаловать в SWEG SHOP</b>\n\n"
        f"🛍 Выбирай товары из каталога и получай ключи мгновенно.\n"
        f"💰 Баланс: <code>{format_price(balance)}</code>\n\n"
        f"<i>Используй меню ниже 👇</i>"
    )
    await message.answer(
        text,
        reply_markup=main_menu_keyboard(is_admin=is_admin(user_id)),
        parse_mode="HTML"
    )


@router.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    args = message.text.split()[1] if len(message.text.split()) > 1 else None
    referrer_id = None

    if args and args.isdigit() and int(args) != user_id:
        referrer_id = int(args)

    await ensure_user(user_id, referrer_id)
    await send_main_menu(message, user_id)


@router.callback_query(F.data == "main_menu")
async def main_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "👋 <b>Главное меню</b>\n\nВыбери раздел:",
        reply_markup=main_menu_keyboard(is_admin=is_admin(callback.from_user.id)),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "catalog")
async def catalog(callback: CallbackQuery):
    categories = await get_all_categories()
    if not categories:
        await callback.answer("Каталог пока пуст", show_alert=True)
        return

    await callback.message.edit_text(
        "🛍 <b>Каталог</b>\n\nВыберите категорию:",
        reply_markup=categories_keyboard(categories),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cat_"))
async def category_products(callback: CallbackQuery):
    category_id = int(callback.data.split("_")[1])
    products = await get_products_by_category(category_id)
    if not products:
        await callback.answer("В этой категории пока нет товаров", show_alert=True)
        return

    await callback.message.edit_text(
        "📦 <b>Товары</b>\n\nВыберите товар:",
        reply_markup=products_keyboard(products, back_callback="catalog"),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("product_"))
async def product_detail(callback: CallbackQuery):
    product_id = int(callback.data.split("_")[1])
    product = await get_product_by_id(product_id)
    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return

    counts = await count_keys(product_id)
    cat_name = product.get("category_name") or "Без категории"
    cat_emoji = product.get("category_emoji") or "🔹"

    text = (
        f"{cat_emoji} <b>{escape_html(product['name'])}</b>\n\n"
        f"📝 {escape_html(product['description']) or 'Описание отсутствует'}\n\n"
        f"💰 Цена: <code>{format_price(product['price'])}</code>\n"
        f"📦 В наличии: <code>{counts['left']}</code> шт.\n"
        f"📁 Категория: {escape_html(cat_name)}"
    )

    photo_id = product.get("photo_id")
    keyboard = product_detail_keyboard(product_id, counts["left"] > 0, back_callback=f"cat_{product['category_id']}")

    if callback.message.photo and not photo_id:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    elif photo_id:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer_photo(photo_id, caption=text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()


@router.callback_query(F.data.startswith("buy_"))
async def buy_product(callback: CallbackQuery):
    user_id = callback.from_user.id
    product_id = int(callback.data.split("_")[1])

    product = await get_product_by_id(product_id)
    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return

    balance = await get_balance(user_id)
    price = product["price"]

    if balance < price:
        await callback.answer("Недостаточно средств. Пополните баланс!", show_alert=True)
        return

    key = await get_unused_key(product_id)
    if not key:
        await callback.answer("К сожалению, товар закончился", show_alert=True)
        return

    await add_balance(user_id, -price)
    await mark_key_as_used(key["id"])
    await add_purchase(user_id, product_id, price)
    await mark_purchased(user_id)

    # Реферальное вознаграждение
    ref_config = await get_referral_config()
    referrer_id = await get_referrer(user_id)
    if referrer_id and ref_config and ref_config["bonus_value"]:
        bonus = ref_config["bonus_value"]
        if ref_config["bonus_type"] == "percent":
            bonus = int(price * ref_config["bonus_value"] / 100)
        if bonus > 0:
            await add_balance(referrer_id, bonus)
            try:
                await callback.bot.send_message(
                    referrer_id,
                    f"🎁 Ваш реферал совершил покупку! Вам начислено <code>{format_price(bonus)}</code>",
                    parse_mode="HTML"
                )
            except Exception:
                pass

    await callback.message.edit_text(
        f"✅ <b>Покупка совершена!</b>\n\n"
        f"🏷 {escape_html(product['name'])}\n"
        f"🔑 <code>{escape_html(key['key_value'])}</code>\n\n"
        f"Спасибо за покупку!",
        reply_markup=back_keyboard("main_menu"),
        parse_mode="HTML"
    )
    await callback.answer("Успешно!")


@router.callback_query(F.data == "profile")
async def profile(callback: CallbackQuery):
    user_id = callback.from_user.id
    balance = await get_balance(user_id)
    purchases = await get_user_purchases(user_id)
    referrals = await get_referrals_count(user_id)
    paid_refs = await get_paid_referrals_count(user_id)
    me = await callback.bot.me()

    text = (
        f"💼 <b>Ваш профиль</b>\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"💰 Баланс: <code>{format_price(balance)}</code>\n"
        f"🛒 Покупок: <code>{len(purchases)}</code>\n"
        f"👥 Рефералов: <code>{referrals}</code> (покупали: <code>{paid_refs}</code>)\n\n"
        f"🔗 Ваша реферальная ссылка:\n"
        f"<code>https://t.me/{me.username}?start={user_id}</code>"
    )
    await callback.message.edit_text(text, reply_markup=back_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "deposit")
async def deposit(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "💰 <b>Пополнение баланса</b>\n\n"
        "Выберите удобный способ и сумму:",
        reply_markup=deposit_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "promo")
async def promo_input(callback: CallbackQuery, state: FSMContext):
    await state.set_state(DepositStates.waiting_promo)
    await callback.message.edit_text(
        "🎁 <b>Активация промокода</b>\n\nВведите промокод:",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(DepositStates.waiting_promo)
async def process_promo(message: Message, state: FSMContext):
    code = message.text.strip().upper()
    user_id = message.from_user.id

    promo = await get_promocode(code)
    if not promo:
        await message.answer("❌ Промокод не найден или недействителен", reply_markup=cancel_keyboard())
        return

    if await check_promocode_used(user_id, promo["id"]):
        await message.answer("❌ Вы уже использовали этот промокод", reply_markup=cancel_keyboard())
        return

    # Здесь можно добавить логику бонуса: фиксированная сумма на баланс или скидка
    await use_promocode(user_id, promo["id"])
    await message.answer(
        f"✅ Промокод <code>{escape_html(code)}</code> активирован!",
        reply_markup=back_keyboard(),
        parse_mode="HTML"
    )
    await state.clear()


@router.callback_query(F.data == "empty")
async def empty_callback(callback: CallbackQuery):
    await callback.answer("Этот товар временно недоступен", show_alert=True)


@router.callback_query(F.data == "ai_support")
async def ai_support(callback: CallbackQuery):
    await callback.message.edit_text(
        "🤖 <b>ИИ-поддержка</b>\n\n"
        "Просто напишите свой вопрос — я постараюсь помочь.\n\n"
        "<i>Или обратитесь к живому админу: @ZOJlOTOY / @SBveg</i>",
        reply_markup=back_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(F.text)
async def text_handler(message: Message, state: FSMContext):
    current = await state.get_state()
    if current:
        return

    from ai_assistant import get_ai_response
    await message.answer_chat_action("typing")
    answer = await get_ai_response(message.from_user.id, message.text)
    await message.answer(answer, parse_mode="HTML")
