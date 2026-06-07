from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from database.models import async_session, User, Key
from sqlalchemy import select

user_router = Router()

@user_router.message(CommandStart())
async def cmd_start(message: Message):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == message.from_user.id))
        if not user:
            session.add(User(tg_id=message.from_user.id))
            await session.commit()
    await message.answer("✨ IceBerg Magic Cheat Shop", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍 Магазин", callback_data="catalog")],
        [InlineKeyboardButton(text="👤 Профиль", callback_data="profile")]
    ]))

@user_router.callback_query(F.data == "profile")
async def profile(call: CallbackQuery):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == call.from_user.id))
        await call.message.edit_text(f"👤 Профиль\nID: {call.from_user.id}\n💰 Баланс: {user.balance}₽", 
                                     reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]]))

@user_router.callback_query(F.data == "catalog")
async def catalog(call: CallbackQuery):
    await call.message.edit_text("📂 Выберите категорию:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Oxide", callback_data="view_oxide")],
        [InlineKeyboardButton(text="Android (Non Root)", callback_data="view_android")],
        [InlineKeyboardButton(text="Magic", callback_data="view_magic")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
    ]))

@user_router.callback_query(F.data.startswith("view_"))
async def view_keys(call: CallbackQuery):
    cat = call.data.split("_")[1]
    async with async_session() as session:
        keys = await session.scalars(select(Key).where(Key.product_id == cat, Key.is_sold == False))
        text = f"🔑 Ключи {cat}:\n" + "\n".join([k.key_code for k in keys]) if keys else "Нет ключей."
        await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="catalog")]]))

@user_router.callback_query(F.data == "back")
async def back(call: CallbackQuery):
    await cmd_start(call.message)
    
