from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.models import async_session, Key, User
from sqlalchemy import select, func

admin_router = Router()

class Mailing(StatesGroup):
    text = State()

@admin_router.message(F.text == "/stats")
async def get_stats(message: Message):
    async with async_session() as session:
        user_count = await session.scalar(select(func.count(User.tg_id)))
        sold_keys = await session.scalar(select(func.count(Key.id)).where(Key.is_sold == True))
        await message.answer(f"📊 Статистика:\nВсего пользователей: {user_count}\nПродано ключей: {sold_keys}")

@admin_router.message(F.text == "/sendall")
async def start_mailing(message: Message, state: FSMContext):
    await message.answer("Введите текст:")
    await state.set_state(Mailing.text)

@admin_router.message(Mailing.text)
async def send_mailing(message: Message, state: FSMContext, bot: Bot):
    async with async_session() as session:
        users = await session.scalars(select(User.tg_id))
        for user_id in users:
            try: await bot.send_message(user_id, message.text)
            except: continue
    await message.answer("Рассылка завершена")
    await state.clear()
    
