
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from database.models import async_session, Key
from sqlalchemy import select

user_router = Router()

def get_main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 КАТАЛОГ", callback_data="catalog")],
        [InlineKeyboardButton(text="👤 ПРОФИЛЬ", callback_data="profile")],
        [InlineKeyboardButton(text="🛠 ПОДДЕРЖКА", callback_data="support")],
        [InlineKeyboardButton(text="ℹ️ ИНФОРМАЦИЯ", callback_data="info")]
    ])

@user_router.message(F.text == "/start")
async def cmd_start(message: Message):
    await message.answer("✨ <b>Добро пожаловать в KeeperStore</b>\n\nВыберите нужный раздел в меню:", reply_markup=get_main_kb())

@user_router.callback_query(F.data == "catalog")
async def show_games(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Oxide", callback_data="game_oxide")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")]
    ])
    await callback.message.edit_text("📂 <b>Выберите игру:</b>", reply_markup=kb)

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
        [InlineKeyboardButton(text="✨ Magic — 100₽", callback_data="buy_magic")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="game_oxide")]
    ])
    await callback.message.edit_text("💎 <b>Выберите продукт:</b>", reply_markup=kb)

@user_router.callback_query(F.data == "buy_magic")
async def buy_key(callback: CallbackQuery):
    await callback.answer("⏳ Проверяем наличие...")
    async with async_session() as session:
        stmt = select(Key).where(Key.product == "Magic", Key.is_sold == False).limit(1)
        res = await session.execute(stmt)
        key = res.scalar()
        if key:
            key.is_sold = True
            await session.commit()
            await callback.message.edit_text(
                f"✅ <b>Покупка успешна!</b>\n\n"
                f"🎮 Продукт: Magic\n"
                f"🔑 Ваш ключ: <code>{key.key_code}</code>\n\n"
                f"<i>Удачной игры!</i>",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 В меню", callback_data="back_main")]])
            )
        else:
            await callback.answer("❌ К сожалению, ключи закончились!", show_alert=True)

@user_router.callback_query(F.data == "back_main")
async def back(callback: CallbackQuery):
    await callback.message.edit_text("✨ <b>Главное меню:</b>", reply_markup=get_main_kb())

@user_router.callback_query(F.data == "profile")
async def profile(callback: CallbackQuery):
    await callback.message.edit_text("👤 <b>Ваш профиль:</b>\n\n💰 Баланс: 0₽", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")]]))

@user_router.callback_query(F.data == "support")
async def support(callback: CallbackQuery):
    await callback.message.edit_text("🛠 <b>Поддержка:</b>\n\nПо всем вопросам: @admin", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")]]))

@user_router.callback_query(F.data == "info")
async def info(callback: CallbackQuery):
    await callback.message.edit_text("ℹ️ <b>Информация:</b>\n\nЛучший магазин ключей Oxide.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")]]))
    
