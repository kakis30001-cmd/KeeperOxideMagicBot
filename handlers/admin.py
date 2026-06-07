import os
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database.models import async_session, Product, Key

admin_router = Router()

class AddProd(StatesGroup):
    name = State()
    price = State()
    keys = State()

class Broadcast(StatesGroup):
    text = State()

def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить товар", callback_data="add_prod")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="broadcast")]
    ])

@admin_router.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id != int(os.getenv("ADMIN_ID")): return
    await message.answer("🛠 Панель администратора:", reply_markup=admin_kb())

@admin_router.callback_query(F.data == "add_prod")
async def start_add(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("Введите название товара:")
    await state.set_state(AddProd.name)

@admin_router.message(AddProd.name)
async def get_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введите цену:")
    await state.set_state(AddProd.price)

@admin_router.message(AddProd.price)
async def get_price(message: Message, state: FSMContext):
    await state.update_data(price=int(message.text))
    await message.answer("Введите ключи (каждый с новой строки):")
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
    await message.answer("✅ Товар успешно добавлен!")
    await state.clear()

@admin_router.callback_query(F.data == "broadcast")
async def start_broadcast(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("Введите текст для рассылки:")
    await state.set_state(Broadcast.text)

@admin_router.message(Broadcast.text)
async def send_broadcast(message: Message, state: FSMContext):
    from database.models import User
    from sqlalchemy import select
    async with async_session() as session:
        users = await session.scalars(select(User))
        count = 0
        for user in users:
            try:
                await message.bot.send_message(user.tg_id, message.text)
                count += 1
            except: continue
    await message.answer(f"📢 Рассылка завершена! Получателей: {count}")
    await state.clear()
    
