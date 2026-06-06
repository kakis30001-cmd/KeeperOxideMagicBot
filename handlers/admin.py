from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.models import async_session, Key
from sqlalchemy import insert

admin_router = Router()

class AddKey(StatesGroup):
    waiting_for_keys = State()

@admin_router.message(F.text == "/addkey")
async def start_add_key(message: Message, state: FSMContext):
    await message.answer("Отправь ключи для Magic (через запятую или пробел):")
    await state.set_state(AddKey.waiting_for_keys)

@admin_router.message(AddKey.waiting_for_keys)
async def save_keys(message: Message, state: FSMContext):
    keys = message.text.replace(',', ' ').split()
    async with async_session() as session:
        for k in keys:
            session.add(Key(game="Oxide", device="Android non-root", product="Magic", key_code=k))
        await session.commit()
    await message.answer(f"Добавлено {len(keys)} ключей!")
    await state.clear()
    
