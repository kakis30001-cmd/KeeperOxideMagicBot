from aiogram import Router, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from database.models import async_session, User
from sqlalchemy import select

user_router = Router()

def get_main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍 Магазин", callback_data="catalog")],
        [InlineKeyboardButton(text="👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton(text="🛠 Поддержка", callback_data="support")],
        [InlineKeyboardButton(text="ℹ️ Правила", callback_data="info")]
    ])

@user_router.message(F.text == "/start")
async def cmd_start(message: Message):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == message.from_user.id))
        if not user:
            session.add(User(tg_id=message.from_user.id))
            await session.commit()
    await message.answer("✨ Добро пожаловать в IceBerg Magic Cheat Shop\n\nДля покупки товаров используйте кнопки ниже 👇", reply_markup=get_main_kb())

@user_router.callback_query(F.data == "profile")
async def show_profile(callback: CallbackQuery):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == callback.from_user.id))
        await callback.message.edit_text(
            f"👤 <b>Профиль</b>\n\n"
            f"📄 Имя: {callback.from_user.first_name}\n"
            f" </> ID: <code>{callback.from_user.id}</code>\n"
            f" 💰 Ваш баланс: {user.balance} ₽",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="topup")],
                [InlineKeyboardButton(text="📦 История заказов", callback_data="history")],
                [InlineKeyboardButton(text="👥 Реферальная система", callback_data="referral")],
                [InlineKeyboardButton(text="🏷 Активировать промокод", callback_data="promo")],
                [InlineKeyboardButton(text="🏠 Главная", callback_data="back_main")]
            ])
        )

@user_router.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery):
    await callback.message.edit_text("✨ Добро пожаловать в IceBerg Magic Cheat Shop\n\nДля покупки товаров используйте кнопки ниже 👇", reply_markup=get_main_kb())
    
