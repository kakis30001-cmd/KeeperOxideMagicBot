from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.models import async_session, Key, User, ADMIN_IDS
from sqlalchemy import select

admin_router = Router()

class AddKey(StatesGroup):
    waiting_for_keys = State()

class Mailing(StatesGroup):
    text = State()

@admin_router.message(F.text == "/admin")
async def admin_panel(message: Message):
    if message.from_user.id in ADMIN_IDS:
        await message.answer("🛠 <b>Панель администратора:</b>\n/addkey - Добавить ключи\n/sendall - Рассылка")

@admin_router.message(F.text == "/addkey")
async def start_add_key(message: Message, state: FSMContext):
    if message.from_user.id in ADMIN_IDS:
        await message.answer("Отправь ключи:")
        await state.set_state(AddKey.waiting_for_keys)

@admin_router.message(AddKey.waiting_for_keys)
async def save_keys(message: Message, state: FSMContext):
    keys = message.text.replace(',', ' ').split()
    async with async_session() as session:
        for k in keys:
            session.add(Key(game="Oxide", device="Android non-root", product="Magic", key_code=k))
        await session.commit()
    await message.answer(f"Добавлено: {len(keys)}")
    await state.clear()

@admin_router.message(F.text == "/sendall")
async def start_mailing(message: Message, state: FSMContext):
    if message.from_user.id in ADMIN_IDS:
        await message.answer("Введите текст рассылки:")
        await state.set_state(Mailing.text)

@admin_router.message(Mailing.text)
async def send_mailing(message: Message, state: FSMContext, bot: Bot):
    async with async_session() as session:
        users = await session.execute(select(User.tg_id))
        for user_id in users.scalars():
            try: await bot.send_message(user_id, message.text)
            except: continue
    await message.answer("Рассылка завершена!")
    await state.clear()
    
