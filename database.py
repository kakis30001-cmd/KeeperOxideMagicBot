import asyncpg
from config import DB_URL

pool = None

async def connect_db():
    global pool

    pool = await asyncpg.create_pool(
        DB_URL,
        min_size=1,
        max_size=5
    )

    async with pool.acquire() as conn:
        # Таблица users — user_id как PRIMARY KEY
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS users(
            user_id BIGINT PRIMARY KEY,
            balance INTEGER DEFAULT 0
        )
        """)

        # Таблица products — id SERIAL (автоинкремент)
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS products(
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            price INTEGER NOT NULL
        )
        """)

        # Таблица keys_store
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS keys_store(
            id SERIAL PRIMARY KEY,
            product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
            key_value TEXT NOT NULL,
            used BOOLEAN DEFAULT FALSE
        )
        """)

        # Таблица purchases
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS purchases(
            id SERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
            product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
            price INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        )
        """)

async def add_user(user_id: int):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO users(user_id) VALUES($1) ON CONFLICT (user_id) DO NOTHING",
            user_id
        )

async def get_balance(user_id: int) -> int:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT balance FROM users WHERE user_id = $1",
            user_id
        )
        return row["balance"] if row else 0

async def update_user_balance(user_id: int, new_balance: int):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET balance = $1 WHERE user_id = $2",
            new_balance, user_id
        )

async def get_all_products():
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT id, name, price FROM products ORDER BY id")

async def add_product(name: str, price: int):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO products (name, price) VALUES ($1, $2)",
            name, price
        )

async def add_keys_to_product(product_id: int, keys_list: list):
    async with pool.acquire() as conn:
        for key in keys_list:
            if key.strip():
                await conn.execute(
                    "INSERT INTO keys_store (product_id, key_value) VALUES ($1, $2)",
                    product_id, key.strip()
                )

async def get_unused_key(product_id: int):
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT id, key_value FROM keys_store WHERE product_id = $1 AND used = FALSE LIMIT 1",
            product_id
        )

async def mark_key_as_used(key_id: int):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE keys_store SET used = TRUE WHERE id = $1",
            key_id
        )
