from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from database.models import async_session, User
from sqlalchemy import select

user_router = Router()

def get_main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍 Магазин", callback_data="catalog")],
        [InlineKeyboardButton(text="👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton(text="🛠 Поддержка", callback_data="support")],
        [InlineKeyboardButton(text="ℹ️ Информация", callback_data="info")]
    ])

@user_router.message(CommandStart())
async def cmd_start(message: Message):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == message.from_user.id))
        if not user:
            session.add(User(tg_id=message.from_user.id))
            await session.commit()
    await message.answer("✨ <b>Добро пожаловать в IceBerg Magic Cheat Shop</b>\n\nДля покупки товаров используйте кнопки ниже 👇", reply_markup=get_main_kb(), parse_mode="HTML")

@user_router.callback_query(F.data == "profile")
async def show_profile(callback: CallbackQuery):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == callback.from_user.id))
        await callback.message.edit_text(
            f"👤 <b>Профиль</b>\n\nID: <code>{callback.from_user.id}</code>\n💰 Баланс: {user.balance}₽",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💰 Пополнить", callback_data="topup")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")]
            ]), parse_mode="HTML"
        )
