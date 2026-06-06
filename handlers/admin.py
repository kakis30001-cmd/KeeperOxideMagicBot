from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ADMIN_ID
from database.requests import get_admin_stats, add_item, get_all_items, add_keys
from keyboards.inline import admin_main_kb
from keyboards.builder import admin_items_kb

admin_router = Router()

class AddItem(StatesGroup):
    name = State()
    price = State()

class AddKeys(StatesGroup):
    item_id = State()
    keys = State()

@admin_router.message(Command("admin"), F.from_user.id == ADMIN_ID)
async def cmd_admin(message: Message):
    await message.answer("<b>⚙️ Админ-панель</b>", reply_markup=admin_main_kb())

@admin_router.callback_query(F.data == "admin_stats", F.from_user.id == ADMIN_ID)
async def show_stats(callback: CallbackQuery):
    users, sold = await get_admin_stats()
    text = (
        "<b>📊 Статистика магазина</b>\n\n"
        "<blockquote>"
        f"<b>👥 Пользователей:</b> <code>{users}</code>\n"
        f"<b>🔑 Продано ключей:</b> <code>{sold}</code>"
        "</blockquote>"
    )
    await callback.message.edit_text(text, reply_markup=admin_main_kb())
    await callback.answer()

@admin_router.callback_query(F.data == "admin_add_item", F.from_user.id == ADMIN_ID)
async def start_add_item(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите название нового товара:")
    await state.set_state(AddItem.name)
    await callback.answer()

@admin_router.message(AddItem.name, F.from_user.id == ADMIN_ID)
async def process_item_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введите цену товара (только число):")
    await state.set_state(AddItem.price)

@admin_router.message(AddItem.price, F.from_user.id == ADMIN_ID)
async def process_item_price(message: Message, state: FSMContext):
    try:
        price = float(message.text)
    except ValueError:
        await message.answer("Неверный формат. Введите число.")
        return

    data = await state.get_data()
    await add_item(data["name"], price)
    await message.answer("✅ Товар успешно добавлен!")
    await state.clear()

@admin_router.callback_query(F.data == "admin_add_keys", F.from_user.id == ADMIN_ID)
async def start_add_keys(callback: CallbackQuery, state: FSMContext):
    items = await get_all_items()
    if not items:
        await callback.answer("Сначала добавьте товар!", show_alert=True)
        return
    
    await callback.message.answer("Выберите товар для загрузки ключей:", reply_markup=admin_items_kb(items))
    await callback.answer()

@admin_router.callback_query(F.data.startswith("admitem_"), F.from_user.id == ADMIN_ID)
async def select_item_for_keys(callback: CallbackQuery, state: FSMContext):
    item_id = int(callback.data.split("_")[1])
    await state.update_data(item_id=item_id)
    await callback.message.answer("Отправьте список ключей. Каждый ключ с новой строки:")
    await state.set_state(AddKeys.keys)
    await callback.answer()

@admin_router.message(AddKeys.keys, F.from_user.id == ADMIN_ID)
async def process_keys(message: Message, state: FSMContext):
    data = await state.get_data()
    item_id = data["item_id"]
    
    keys_list = [k.strip() for k in message.text.split("\n") if k.strip()]
    if not keys_list:
        await message.answer("Ключи не найдены. Попробуйте еще раз.")
        return
        
    await add_keys(item_id, keys_list)
    await message.answer(f"✅ Успешно загружено ключей: {len(keys_list)}")
    await state.clear()
