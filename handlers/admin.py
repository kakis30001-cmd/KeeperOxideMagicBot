import os
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from database.models import async_session, Product, Key

admin_router = Router()

class AddProd(StatesGroup):
    name = State()
    price = State()
    keys = State()

@admin_router.message(Command("add"))
async def add_prod(message: Message, state: FSMContext):
    if message.from_user.id != int(os.getenv("ADMIN_ID")): return
    await message.answer("Название товара:")
    await state.set_state(AddProd.name)

@admin_router.message(AddProd.name)
async def get_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Цена:")
    await state.set_state(AddProd.price)

@admin_router.message(AddProd.price)
async def get_price(message: Message, state: FSMContext):
    await state.update_data(price=int(message.text))
    await message.answer("Ключи (каждый с новой строки):")
    await state.set_state(AddProd.keys)

@admin_router.message(AddProd.keys)
async def get_keys(message: Message, state: FSMContext):
    data = await state.get_data()
    async with async_session() as session:
        prod = Product(name=data['name'], price=data['price'])
        session.add(prod)
        await session.flush()
        for k in message.text.split('\n'):
            session.add(Key(product_id=prod.id, key_code=k.strip()))
        await session.commit()
    await message.answer("Товар добавлен!")
    await state.clear()
    
