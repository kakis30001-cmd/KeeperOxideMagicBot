import asyncio
import os
import asyncpg
from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

# Загружаем переменные (локально из .env, на Railway подхватит автоматом)
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
DB_URL = os.getenv("DB_URL")

bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher()
router = Router()

# ==================== БАЗА ДАННЫХ ====================
class Database:
    def __init__(self):
        self.pool = None

    async def connect(self):
        self.pool = await asyncpg.create_pool(DB_URL)
        async with self.pool.acquire() as conn:
            # Создаем таблицы, если их нет
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    balance INTEGER DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS products (
                    id SERIAL PRIMARY KEY,
                    name TEXT,
                    price INTEGER
                );
                CREATE TABLE IF NOT EXISTS keys (
                    id SERIAL PRIMARY KEY,
                    product_id INTEGER REFERENCES products(id),
                    key_value TEXT,
                    is_sold BOOLEAN DEFAULT FALSE
                );
            ''')

    async def add_user(self, user_id):
        async with self.pool.acquire() as conn:
            await conn.execute('INSERT INTO users (user_id) VALUES ($1) ON CONFLICT DO NOTHING', user_id)

    async def get_user(self, user_id):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow('SELECT * FROM users WHERE user_id = $1', user_id)

    async def add_product(self, name, price):
        async with self.pool.acquire() as conn:
            return await conn.fetchval('INSERT INTO products (name, price) VALUES ($1, $2) RETURNING id', name, price)

    async def add_keys(self, product_id, keys_list):
        async with self.pool.acquire() as conn:
            query = 'INSERT INTO keys (product_id, key_value) VALUES ($1, $2)'
            await conn.executemany(query, [(product_id, k) for k in keys_list])

db = Database()

# ==================== КЛАВИАТУРЫ ====================
def main_menu():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🏪 Магазин", callback_data="shop"))
    builder.row(InlineKeyboardButton(text="👤 Профиль", callback_data="profile"))
    builder.row(InlineKeyboardButton(text="📢 Поддержка", callback_data="support"))
    builder.row(InlineKeyboardButton(text="ℹ️ Правила", callback_data="rules"))
    return builder.as_markup()

# ==================== КЛИЕНТСКАЯ ЧАСТЬ ====================
@router.message(CommandStart())
async def cmd_start(message: Message):
    await db.add_user(message.from_user.id)
    text = (
        "☺️ <b>Добро пожаловать в IceBerg Magic Cheat Shop</b>\n\n"
        "Для покупки товаров используйте кнопки ниже ⬇️"
    )
    await message.answer(text, reply_markup=main_menu())

@router.callback_query(F.data == "profile")
async def show_profile(call: CallbackQuery):
    user = await db.get_user(call.from_user.id)
    text = (
        f"👤 <b>Ваш профиль:</b>\n\n"
        f"ID: <code>{call.from_user.id}</code>\n"
        f"💰 Баланс: <b>{user['balance']} ₽</b>"
    )
    
    # Кнопка пополнения (заглушка для клиента)
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💳 Пополнить баланс", callback_data="top_up"))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back_main"))
    
    await call.message.edit_text(text, reply_markup=builder.as_markup())

@router.callback_query(F.data == "back_main")
async def back_to_main(call: CallbackQuery):
    text = (
        "☺️ <b>Добро пожаловать в IceBerg Magic Cheat Shop</b>\n\n"
        "Для покупки товаров используйте кнопки ниже ⬇️"
    )
    await call.message.edit_text(text, reply_markup=main_menu())

# ==================== АДМИН ПАНЕЛЬ (FSM) ====================
class AdminAddProduct(StatesGroup):
    waiting_for_name_price = State()
    waiting_for_keys = State()

@router.message(Command("admin"))
async def admin_panel(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    await message.answer(
        "🛠 <b>Добавление товара</b>\n\n"
        "Отправь название и цену товара через тире.\n"
        "<i>Пример: Oxide Private Script - 500</i>"
    )
    await state.set_state(AdminAddProduct.waiting_for_name_price)

@router.message(AdminAddProduct.waiting_for_name_price)
async def process_name_price(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
        
    try:
        name, price = message.text.split("-")
        name = name.strip()
        price = int(price.strip())
        
        # Сохраняем товар и получаем его ID
        product_id = await db.add_product(name, price)
        
        await state.update_data(product_id=product_id)
        await message.answer(
            f"✅ Товар <b>{name}</b> (Цена: {price}₽) создан.\n\n"
            "Теперь отправь список ключей для этого товара.\n"
            "<b>Каждый ключ с новой строки!</b>"
        )
        await state.set_state(AdminAddProduct.waiting_for_keys)
    except ValueError:
        await message.answer("❌ Ошибка формата. Напиши в формате: Название - Цена")

@router.message(AdminAddProduct.waiting_for_keys)
async def process_keys(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
        
    data = await state.get_data()
    product_id = data.get("product_id")
    
    keys_list = [key.strip() for key in message.text.split("\n") if key.strip()]
    
    if keys_list:
        await db.add_keys(product_id, keys_list)
        await message.answer(f"✅ Успешно загружено ключей: <b>{len(keys_list)}</b> шт.")
    else:
        await message.answer("❌ Вы не отправили ни одного ключа.")
        
    await state.clear()

# ==================== ЗАПУСК ====================
async def main():
    await db.connect()
    dp.include_router(router)
    print("Бот запущен!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
