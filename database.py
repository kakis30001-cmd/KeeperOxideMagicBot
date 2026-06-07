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

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS users(
            user_id BIGINT PRIMARY KEY,
            balance INTEGER DEFAULT 0
        )
        """)

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS products(
            id SERIAL PRIMARY KEY,
            name TEXT,
            price INTEGER
        )
        """)

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS keys_store(
            id SERIAL PRIMARY KEY,
            product_id INTEGER,
            key_value TEXT,
            used BOOLEAN DEFAULT FALSE
        )
        """)

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS purchases(
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            product_id INTEGER,
            price INTEGER
        )
        """)

async def add_user(user_id: int):
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users(user_id)
            VALUES($1)
            ON CONFLICT DO NOTHING
            """,
            user_id
        )

async def get_balance(user_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT balance FROM users WHERE user_id=$1",
            user_id
        )

        return row["balance"] if row else 0

async def get_all_products():
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, name, price FROM products")
        return rows

async def add_product(name: str, price: int):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO products (name, price) VALUES ($1, $2)",
            name, price
        )

async def add_keys_to_product(product_id: int, keys_list: list):
    async with pool.acquire() as conn:
        for key in keys_list:
            await conn.execute(
                "INSERT INTO keys_store (product_id, key_value) VALUES ($1, $2)",
                product_id, key.strip()
            )

async def get_unused_key(product_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, key_value FROM keys_store WHERE product_id = $1 AND used = FALSE LIMIT 1",
            product_id
        )
        return row

async def mark_key_as_used(key_id: int):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE keys_store SET used = TRUE WHERE id = $1", key_id)

async def update_user_balance(user_id: int, new_balance: int):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET balance = $1 WHERE user_id = $2",
            new_balance, user_id
        )
