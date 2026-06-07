import asyncio

from aiogram import Bot
from aiogram import Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.types import ReplyKeyboardMarkup
from aiogram.types import KeyboardButton

from config import BOT_TOKEN
from database import connect_db
from database import add_user
from database import get_balance

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🛒 Магазин"),
            KeyboardButton(text="👤 Профиль")
        ]
    ],
    resize_keyboard=True
)

@dp.message(CommandStart())
async def start(message: Message):

    await add_user(message.from_user.id)

    await message.answer(
        "✨ Добро пожаловать в магазин",
        reply_markup=menu
    )

@dp.message(lambda m: m.text == "👤 Профиль")
async def profile(message: Message):

    balance = await get_balance(
        message.from_user.id
    )

    await message.answer(
        f"""
👤 Ваш профиль

🆔 ID: {message.from_user.id}

💰 Баланс: {balance}₽
"""
    )

async def main():

    await connect_db()

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
