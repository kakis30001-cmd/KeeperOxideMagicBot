from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from database.models import async_session, Key
from sqlalchemy import select, update

user_router = Router()

def get_main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Каталог", callback_data="catalog")]
    ])

@user_router.message(F.text == "/start")
async def cmd_start(message: Message):
    await message.answer("Привет! Выбери:", reply_markup=get_main_kb())

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
        [InlineKeyboardButton(text="Magic - 100р", callback_data="buy_magic")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="game_oxide")]
    ])
    await callback.message.edit_text("Выберите продукт:", reply_markup=kb)

@user_router.callback_query(F.data == "buy_magic")
async def buy_key(callback: CallbackQuery):
    async with async_session() as session:
        # Ищем первый свободный ключ
        stmt = select(Key).where(Key.product == "Magic", Key.is_sold == False).limit(1)
        result = await session.execute(stmt)
        key = result.scalar()
        
        if key:
            key.is_sold = True
            await session.commit()
            await callback.message.edit_text(f"✅ Успешно! Ваш ключ: <code>{key.key_code}</code>")
        else:
            await callback.answer("Ключей нет в наличии!")
            
