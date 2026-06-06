from aiogram import Router, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from database.models import async_session, User, Key
from sqlalchemy import select

user_router = Router()

def get_main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍 Магазин", callback_data="catalog")],
        [InlineKeyboardButton(text="👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton(text="🛠 Поддержка", callback_data="support")],
        [InlineKeyboardButton(text="ℹ️ Информация", callback_data="info")]
    ])

@user_router.message(F.text == "/start")
async def cmd_start(message: Message):
    async with async_session() as session:
        user = await session.execute(select(User).where(User.tg_id == message.from_user.id))
        if not user.scalar():
            session.add(User(tg_id=message.from_user.id))
            await session.commit()
    
    await message.answer(
        "✨ <b>Добро пожаловать в IceBerg Magic Cheat Shop</b>\n\n"
        "Для покупки товаров используйте кнопки ниже 👇", 
        reply_markup=get_main_kb()
    )

@user_router.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery):
    await callback.message.edit_text(
        "✨ <b>Добро пожаловать в IceBerg Magic Cheat Shop</b>\n\n"
        "Для покупки товаров используйте кнопки ниже 👇", 
        reply_markup=get_main_kb()
    )

@user_router.callback_query(F.data == "profile")
async def show_profile(callback: CallbackQuery):
    async with async_session() as session:
        result = await session.execute(select(User).where(User.tg_id == callback.from_user.id))
        user = result.scalar()
        balance = user.balance if user else 0
        
    await callback.message.edit_text(
        f"👤 <b>Профиль</b>\n\n"
        f"Имя: {callback.from_user.first_name}\n"
        f"ID: <code>{callback.from_user.id}</code>\n"
        f"💰 Ваш баланс: {balance}₽",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")]
        ])
    )

@user_router.callback_query(F.data == "support")
async def show_support(callback: CallbackQuery):
    await callback.message.edit_text(
        "🛠 <b>Поддержка</b>\n\n"
        "По всем вопросам писать: @nikita1055",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")]
        ])
    )

@user_router.callback_query(F.data == "info")
async def show_info(callback: CallbackQuery):
    text = (
        "ℹ️ <b>ИНФОРМАЦИЯ</b>\n\n"
        "🤖 Бот для продажи подписок LITE и VIP\n\n"
        "💳 Оплата: Platega (СБП, Криптовалюта)\n\n"
        "📌 <b>Как пользоваться:</b>\n"
        "• Купите подписку через меню\n"
        "• После оплаты вы получите ключ\n\n"
        "📞 <b>КОНТАКТЫ:</b>\n"
        "• Техподдержка: @nikita1055\n"
        "• Основной канал: @keepersell\n"
        "• Отзывы: https://t.me/KeeperOtzivi"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 Политика конфиденциальности", url="https://telegra.ph/Politika-konfidencialnosti-04-01-26")],
        [InlineKeyboardButton(text="📄 Пользовательское соглашение", url="https://telegra.ph/Polzovatelskoe-soglashenie-04-01-19")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)

@user_router.callback_query(F.data == "catalog")
async def show_catalog(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Oxide", callback_data="game_oxide")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")]
    ])
    await callback.message.edit_text("📂 <b>Магазин</b>\n\nВыберите игру:", reply_markup=kb)

@user_router.callback_query(F.data == "game_oxide")
async def show_devices(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 Android (non root)", callback_data="dev_android")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="catalog")]
    ])
    await callback.message.edit_text("📱 <b>Выберите устройство:</b>", reply_markup=kb)

@user_router.callback_query(F.data == "dev_android")
async def show_products(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✨ Magic", callback_data="buy_magic")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="game_oxide")]
    ])
    await callback.message.edit_text("💎 <b>Выберите продукт:</b>", reply_markup=kb)

@user_router.callback_query(F.data == "buy_magic")
async def buy_key(callback: CallbackQuery):
    async with async_session() as session:
        stmt = select(Key).where(Key.product == "Magic", Key.is_sold == False).limit(1)
        res = await session.execute(stmt)
        key = res.scalar()
        
        if key:
            key.is_sold = True
            await session.commit()
            await callback.message.edit_text(
                f"✅ <b>Покупка успешна!</b>\n\n"
                f"🔑 Ваш ключ: <code>{key.key_code}</code>",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 В меню", callback_data="back_main")]])
            )
        else:
            await callback.answer("❌ Ключи закончились!", show_alert=True)
    
