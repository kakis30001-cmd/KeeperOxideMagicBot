import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from config import BOT_TOKEN, ADMIN_ID
from database import connect_db, add_user, get_balance, get_all_products, add_product, add_keys_to_product, get_unused_key, mark_key_as_used, update_user_balance

bot = Bot(BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# FSM состояния для админа
class AddProductStates(StatesGroup):
    waiting_name = State()
    waiting_price = State()

class AddKeysStates(StatesGroup):
    waiting_product_id = State()
    waiting_keys = State()

menu = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🛒 Магазин"), KeyboardButton(text="👤 Профиль")]],
    resize_keyboard=True
)

@dp.message(CommandStart())
async def start(message: Message):
    await add_user(message.from_user.id)
    await message.answer("✨ Добро пожаловать в магазин", reply_markup=menu)

@dp.message(lambda m: m.text == "👤 Профиль")
async def profile(message: Message):
    balance = await get_balance(message.from_user.id)
    await message.answer(f"👤 Ваш профиль\n\n🆔 ID: {message.from_user.id}\n💰 Баланс: {balance}₽")

@dp.message(lambda m: m.text == "🛒 Магазин")
async def shop(message: Message):
    products = await get_all_products()
    if not products:
        await message.answer("📭 Товаров пока нет")
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{p['name']} - {p['price']}₽", callback_data=f"buy_{p['id']}")] for p in products
    ])
    await message.answer("🛍 Выберите товар:", reply_markup=kb)

@dp.callback_query(lambda c: c.data and c.data.startswith("buy_"))
async def handle_buy(callback: types.CallbackQuery):
    product_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    
    products = await get_all_products()
    product = next((p for p in products if p["id"] == product_id), None)
    if not product:
        await callback.answer("❌ Товар не найден")
        return
    
    balance = await get_balance(user_id)
    if balance < product["price"]:
        await callback.answer("❌ Недостаточно средств")
        return
    
    key_row = await get_unused_key(product_id)
    if not key_row:
        await callback.answer("❌ Ключи закончились")
        return
    
    # Списываем деньги
    await update_user_balance(user_id, balance - product["price"])
    await mark_key_as_used(key_row["id"])
    
    await callback.message.answer(f"✅ Вы купили {product['name']}\n🔑 Ключ: `{key_row['key_value']}`", parse_mode="Markdown")
    await callback.answer("🎉 Покупка успешна!")

# ----- АДМИН-КОМАНДЫ -----

@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Доступ запрещен")
        return
    await message.answer("🔐 Админ-панель\n\n/add_product — добавить товар\n/add_keys — добавить ключи")

@dp.message(Command("add_product"))
async def cmd_add_product(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.set_state(AddProductStates.waiting_name)
    await message.answer("📝 Введите название товара:")

@dp.message(AddProductStates.waiting_name)
async def process_product_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AddProductStates.waiting_price)
    await message.answer("💰 Введите цену (число):")

@dp.message(AddProductStates.waiting_price)
async def process_product_price(message: Message, state: FSMContext):
    try:
        price = int(message.text)
        data = await state.get_data()
        await add_product(data["name"], price)
        await message.answer(f"✅ Товар '{data['name']}' добавлен за {price}₽")
        await state.clear()
    except ValueError:
        await message.answer("❌ Цена должна быть числом")

@dp.message(Command("add_keys"))
async def cmd_add_keys(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    products = await get_all_products()
    if not products:
        await message.answer("Сначала добавьте товар через /add_product")
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{p['name']} (ID: {p['id']})", callback_data=f"key_product_{p['id']}")] for p in products
    ])
    await message.answer("📦 Выберите товар для добавления ключей:", reply_markup=kb)

@dp.callback_query(lambda c: c.data and c.data.startswith("key_product_"))
async def select_product_for_keys(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔")
        return
    product_id = int(callback.data.split("_")[2])
    await state.update_data(product_id=product_id)
    await state.set_state(AddKeysStates.waiting_keys)
    await callback.message.answer("🔑 Отправьте ключи (каждый с новой строки):")
    await callback.answer()

@dp.message(AddKeysStates.waiting_keys)
async def process_keys(message: Message, state: FSMContext):
    data = await state.get_data()
    product_id = data["product_id"]
    keys = [k.strip() for k in message.text.split("\n") if k.strip()]
    
    await add_keys_to_product(product_id, keys)
    await message.answer(f"✅ Добавлено {len(keys)} ключей для товара ID {product_id}")
    await state.clear()

async def main():
    await connect_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
