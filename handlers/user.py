from aiogram import Router, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from database.models import async_session, User, Key, Product
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
        user = await session.scalar(select(User).where(User.tg_id == message.from_user.id))
        if not user:
            session.add(User(tg_id=message.from_user.id))
            await session.commit()
    await message.answer("✨ Добро пожаловать!", reply_markup=get_main_kb())

@user_router.callback_query(F.data == "profile")
async def profile(callback: CallbackQuery):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == callback.from_user.id))
        await callback.message.edit_text(
            f"👤 Профиль\nID: {callback.from_user.id}\n💰 Баланс: {user.balance}₽",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💰 Пополнить", callback_data="topup")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")]
            ])
        )

@user_router.callback_query(F.data == "buy_magic")
async def buy(callback: CallbackQuery):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == callback.from_user.id))
        product = await session.scalar(select(Product).where(Product.id == "magic"))
        key = await session.scalar(select(Key).where(Key.product_id == "magic", Key.is_sold == False).limit(1))
        
        if user.balance < product.price:
            await callback.answer("Недостаточно средств", show_alert=True)
            return
        if not key:
            await callback.answer("Ключи закончились", show_alert=True)
            return
            
        user.balance -= product.price
        key.is_sold = True
        await session.commit()
        await callback.message.edit_text(f"✅ Ключ: <code>{key.key_code}</code>")
        
