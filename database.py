# Добавь в конец database.py

async def add_product(name: str, price: int) -> int:
    """Добавляет товар и возвращает его ID"""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO products (name, price) VALUES ($1, $2) RETURNING id",
            name, price
        )
        return row["id"]

async def add_keys_to_product(product_id: int, keys_list: list):
    """Добавляет несколько ключей для товара"""
    async with pool.acquire() as conn:
        for key in keys_list:
            if key.strip():
                await conn.execute(
                    "INSERT INTO keys_store (product_id, key_value) VALUES ($1, $2)",
                    product_id, key.strip()
                )

async def get_stats():
    """Возвращает статистику"""
    async with pool.acquire() as conn:
        users = await conn.fetchval("SELECT COUNT(*) FROM users")
        total_sales = await conn.fetchval("SELECT COALESCE(SUM(price), 0) FROM purchases")
        keys_sold = await conn.fetchval("SELECT COUNT(*) FROM keys_store WHERE used = TRUE")
        products_count = await conn.fetchval("SELECT COUNT(*) FROM products")
        
        return {
            "users": users,
            "total_sales": total_sales,
            "keys_sold": keys_sold,
            "products_count": products_count
        }
