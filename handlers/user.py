from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from database.models import async_session, User, Product, Key
from sqlalchemy import select

user_router = Router()

def get_main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍 Магазин", callback_data="catalog")],
        [InlineKeyboardButton(text="👤 Профиль", callback_data="profile")]
    ])

@user_router.message(CommandStart())
async def cmd_start(message: Message):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == message.from_user.id))
        if not user:
            session.add(User(tg_id=message.from_user.id))
            await session.commit()
    await message.answer("✨ Добро пожаловать в IceBerg Magic Cheat Shop!", reply_markup=get_main_kb())

@user_router.callback_query(F.data == "profile")
async def show_profile(callback: CallbackQuery):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == callback.from_user.id))
        text = (f"👤 <b>Профиль</b>\n\n"
                f"🆔 ID: <code>{callback.from_user.id}</code>\n"
                f"💰 Баланс: <b>{user.balance} ₽</b>")
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")]
        ]))

@user_router.callback_query(F.data == "catalog")
async def show_catalog(callback: CallbackQuery):
    await callback.message.edit_text("📂 Выберите категорию:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Oxide", callback_data="cat_oxide")],
        [InlineKeyboardButton(text="Android (Non Root)", callback_data="cat_android")],
        [InlineKeyboardButton(text="Magic", callback_data="cat_magic")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")]
    ]))

@user_router.callback_query(F.data.startswith("cat_"))
async def show_items(callback: CallbackQuery):
    cat = callback.data.split("_")[1]
    # Здесь логика получения ключей для конкретной категории
    await callback.message.edit_text(f"🔑 Доступные ключи в категории {cat.upper()}:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Купить (Пример)", callback_data="buy_key")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="catalog")]
    ]))

@user_router.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery):
    await callback.message.edit_text("✨ Добро пожаловать в IceBerg Magic Cheat Shop!", reply_markup=get_main_kb())
    
