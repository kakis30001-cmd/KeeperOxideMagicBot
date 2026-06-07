from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database.models import async_session, User, Product, Key
from sqlalchemy import select, update

user_router = Router()

def main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍 Магазин", callback_data="catalog")],
        [InlineKeyboardButton(text="👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton(text="📞 Поддержка", url="https://t.me/nikita1055")],
        [InlineKeyboardButton(text="ℹ️ Информация", callback_data="info")]
    ])

@user_router.message(F.text == "/start")
async def start(message: Message):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == message.from_user.id))
        if not user:
            session.add(User(tg_id=message.from_user.id))
            await session.commit()
    await message.answer("✨ Добро пожаловать в KeeperShop", reply_markup=main_kb())

@user_router.callback_query(F.data == "profile")
async def profile(call: CallbackQuery):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == call.from_user.id))
        await call.message.edit_text(f"👤 Профиль\n🆔 ID: {call.from_user.id}\n💰 Баланс: {user.balance}₽", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]]))

@user_router.callback_query(F.data == "info")
async def info(call: CallbackQuery):
    text = "ℹ️ ИНФОРМАЦИЯ\n\n🤖 Бот для продажи подписок\n\n💳 Оплата: Platega\n\n📞 КОНТАКТЫ:\n• Поддержка: @nikita1055\n• Канал: @keepersell"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Политика", url="https://telegra.ph/Politika-konfidencialnosti-04-01-26")],
        [InlineKeyboardButton(text="Соглашение", url="https://telegra.ph/Polzovatelskoe-soglashenie-04-01-19")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
    ])
    await call.message.edit_text(text, reply_markup=kb)

@user_router.callback_query(F.data == "back")
async def back(call: CallbackQuery):
    await call.message.edit_text("✨ Добро пожаловать в KeeperShop", reply_markup=main_kb())
    
