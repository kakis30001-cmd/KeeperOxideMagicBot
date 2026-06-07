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
