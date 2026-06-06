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
        if not (await session.execute(select(User).where(User.tg_id == message.from_user.id))).scalar():
            session.add(User(tg_id=message.from_user.id))
            await session.commit()
    await message.answer("✨ Добро пожаловать!", reply_markup=get_main_kb())

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

@user_router.callback_query(F.data == "back_main")
async def back(callback: CallbackQuery):
    await callback.message.edit_text("✨ Главное меню:", reply_markup=get_main_kb())
    
