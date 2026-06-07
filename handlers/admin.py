from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from database.models import async_session, Product, Key
from sqlalchemy import select

admin_router = Router()

class AddProduct(StatesGroup):
    name = State()
    price = State()
    keys = State()

@admin_router.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id != int(os.getenv("ADMIN_ID")): return
    await message.answer("🛠 Панель админа:\n/add_product - Добавить товар\n/send_all - Рассылка")

@admin_router.message(Command("add_product"))
async def start_add(message: Message, state: FSMContext):
    await message.answer("Введите название товара:")
    await state.set_state(AddProduct.name)

@admin_router.message(AddProduct.name)
async def set_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введите цену:")
    await state.set_state(AddProduct.price)

# И так далее: после ввода всех данных - цикл for по строкам ключей
# для каждого ключа: session.add(Key(product_id=..., key_code=key))
