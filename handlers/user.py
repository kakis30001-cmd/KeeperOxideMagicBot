from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from database.models import async_session, Key
from sqlalchemy import select

user_router = Router()

def get_main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Каталог", callback_data="catalog")],
        [InlineKeyboardButton(text="👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton(text="🛠 Поддержка", callback_data="support")],
        [InlineKeyboardButton(text="ℹ️ Информация", callback_data="info")]
    ])

@user_router.message(F.text == "/start")
async def cmd_start(message: Message):
    await message.answer("Главное меню:", reply_markup=get_main_kb())

@user_router.callback_query(F.data == "catalog")
async def show_games(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Oxide", callback_data="game_oxide")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")]
    ])
    await callback.message.edit_text("Выберите игру:", reply_markup=kb)

@user_router.callback_query(F.data == "game_oxide")
async def show_devices(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Android (non root)", callback_data="dev_android")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="catalog")]
    ])
    await callback.message.edit_text("Выберите устройство:", reply_markup=kb)

@user_router.callback_query(F.data == "dev_android")
async def show_products(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Magic", callback_data="buy_magic")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="game_oxide")]
    ])
    await callback.message.edit_text("Выберите продукт:", reply_markup=kb)

@user_router.callback_query(F.data == "buy_magic")
async def buy_key(callback: CallbackQuery):
    async with async_session() as session:
        stmt = select(Key).where(Key.product == "Magic", Key.is_sold == False).limit(1)
        res = await session.execute(stmt)
        key = res.scalar()
        if key:
            key.is_sold = True
            await session.commit()
            await callback.message.edit_text(f"Ключ: <code>{key.key_code}</code>")
        else:
            await callback.answer("Нет ключей!")

@user_router.callback_query(F.data == "back_main")
async def back(callback: CallbackQuery):
    await callback.message.edit_text("Главное меню:", reply_markup=get_main_kb())

@user_router.callback_query(F.data == "profile")
async def profile(callback: CallbackQuery):
    await callback.message.edit_text("Профиль:\nБаланс: 0", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="back_main")]]))

@user_router.callback_query(F.data == "support")
async def support(callback: CallbackQuery):
    await callback.message.edit_text("Поддержка: @admin", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="back_main")]]))

@user_router.callback_query(F.data == "info")
async def info(callback: CallbackQuery):
    await callback.message.edit_text("Инфо: Описание...", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="back_main")]]))
    
