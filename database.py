import aiosqlite
from config import DB_URL

sqlite_conn: aiosqlite.Connection | None = None


async def connect_db():
    global sqlite_conn
    db_path = "bot.db"
    sqlite_conn = await aiosqlite.connect(db_path)
    sqlite_conn.row_factory = aiosqlite.Row
    await sqlite_conn.execute("PRAGMA foreign_keys = ON")
    await _create_tables()
    print(f"[DB] Подключено к SQLite: {db_path}")


async def _execute(query: str, *args):
    await sqlite_conn.execute(query, args)
    await sqlite_conn.commit()


async def _fetch(query: str, *args):
    async with sqlite_conn.execute(query, args) as cursor:
        return await cursor.fetchall()


async def _fetchrow(query: str, *args):
    async with sqlite_conn.execute(query, args) as cursor:
        return await cursor.fetchone()


async def _fetchval(query: str, *args):
    async with sqlite_conn.execute(query, args) as cursor:
        row = await cursor.fetchone()
        return row[0] if row else None


async def _create_tables():
    await _execute("""
    CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY,
        balance INTEGER DEFAULT 0,
        referrer_id INTEGER DEFAULT NULL,
        has_purchased INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    await _execute("""
    CREATE TABLE IF NOT EXISTS categories(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        emoji TEXT DEFAULT '🔹'
    )
    """)

    await _execute("""
    CREATE TABLE IF NOT EXISTS products(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
        name TEXT NOT NULL,
        description TEXT DEFAULT '',
        price INTEGER NOT NULL,
        photo_id TEXT DEFAULT NULL
    )
    """)

    await _execute("""
    CREATE TABLE IF NOT EXISTS keys_store(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
        key_value TEXT NOT NULL,
        used INTEGER DEFAULT 0
    )
    """)

    await _execute("""
    CREATE TABLE IF NOT EXISTS purchases(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
        product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
        price INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    await _execute("""
    CREATE TABLE IF NOT EXISTS promocodes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        discount_type TEXT NOT NULL,
        discount_value INTEGER NOT NULL,
        max_uses INTEGER NOT NULL,
        used_count INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1
    )
    """)

    await _execute("""
    CREATE TABLE IF NOT EXISTS promocode_uses(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
        promocode_id INTEGER REFERENCES promocodes(id) ON DELETE CASCADE,
        used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    await _execute("""
    CREATE TABLE IF NOT EXISTS referral_config(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bonus_type TEXT NOT NULL,
        bonus_value INTEGER NOT NULL
    )
    """)

    await _execute("""
    CREATE TABLE IF NOT EXISTS bot_settings(
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """)

    await _execute("""
    CREATE TABLE IF NOT EXISTS manual_orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
        product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
        amount INTEGER NOT NULL,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    await _execute("""
    CREATE TABLE IF NOT EXISTS pending_orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        order_id TEXT UNIQUE NOT NULL,
        amount INTEGER NOT NULL,
        provider TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    await _execute("""
    CREATE TABLE IF NOT EXISTS ai_chat_history(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    await _execute("""
    CREATE TABLE IF NOT EXISTS ai_settings(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key TEXT UNIQUE NOT NULL,
        value TEXT NOT NULL
    )
    """)

    await _execute("CREATE INDEX IF NOT EXISTS idx_keys_product_used ON keys_store(product_id, used)")
    await _execute("CREATE INDEX IF NOT EXISTS idx_purchases_user ON purchases(user_id)")
    await _execute("CREATE INDEX IF NOT EXISTS idx_pending_order ON pending_orders(order_id, status)")
    await _execute("CREATE INDEX IF NOT EXISTS idx_ai_history_user ON ai_chat_history(user_id, created_at)")

    await _execute("INSERT OR IGNORE INTO referral_config (bonus_type, bonus_value) VALUES ('rubles', 0)")
    await _execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('shop_mode', 'auto')")
    await _execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('custom_text', 'Переведите на карту / по СБП. После оплаты отправьте скриншот.')")
    await _execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('crypto_fee', '0')")
    await _execute(
        "INSERT OR IGNORE INTO ai_settings (key, value) VALUES (?, ?)",
        "system_prompt",
        "Ты — ИИ-ассистент магазина SWEG SHOP. Ты помогаешь пользователям с выбором товаров, "
        "отвечаешь на вопросы об оплате, доставке ключей, реферальной программе и промокодах. "
        "Стиль общения: уверенный, дружелюбный, по-человечески. Можешь использовать эмодзи. "
        "Если не знаешь точный ответ — не выдумывай, скажи обратиться к поддержке: @ZOJlOTOY или @SBveg."
    )
    await _execute("INSERT OR IGNORE INTO ai_settings (key, value) VALUES ('ai_enabled', 'true')")
    await _execute("INSERT OR IGNORE INTO ai_settings (key, value) VALUES ('ai_model', 'mistralai/mistral-7b-instruct:free')")
    await _execute("INSERT OR IGNORE INTO categories (name, emoji) VALUES ('Без категории', '🔹')")


async def close_db():
    global sqlite_conn
    if sqlite_conn:
        await sqlite_conn.close()
        sqlite_conn = None


# ===================== НАСТРОЙКИ =====================

async def get_setting(key: str, default: str = "") -> str:
    row = await _fetchval("SELECT value FROM bot_settings WHERE key = ?", key)
    return row if row is not None else default


async def get_crypto_fee() -> int:
    row = await _fetchval("SELECT value FROM bot_settings WHERE key = 'crypto_fee'")
    return int(row) if row else 0


async def set_crypto_fee(fee: int):
    await _execute("""
        INSERT INTO bot_settings (key, value) VALUES ('crypto_fee', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
    """, str(fee))


async def update_setting(key: str, value: str):
    await _execute("""
        INSERT INTO bot_settings (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
    """, key, value)


# ===================== ИИ =====================

async def get_ai_setting(key: str) -> str | None:
    return await _fetchval("SELECT value FROM ai_settings WHERE key = ?", key)


async def update_ai_setting(key: str, value: str):
    await _execute("""
        INSERT INTO ai_settings (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
    """, key, value)


async def save_ai_chat_history(user_id: int, role: str, content: str):
    await _execute(
        "INSERT INTO ai_chat_history (user_id, role, content) VALUES (?, ?, ?)",
        user_id, role, content
    )


async def get_ai_chat_history(user_id: int, limit: int = 10):
    return await _fetch(
        "SELECT role, content FROM ai_chat_history WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
        user_id, limit
    )


async def clear_ai_chat_history(user_id: int):
    await _execute("DELETE FROM ai_chat_history WHERE user_id = ?", user_id)


# ===================== ПОЛЬЗОВАТЕЛИ =====================

async def add_user(user_id: int, referrer_id: int = None):
    await _execute(
        "INSERT OR IGNORE INTO users(user_id, balance, referrer_id) VALUES(?, 0, ?)",
        user_id, referrer_id
    )


async def ensure_user(user_id: int, referrer_id: int = None):
    await _execute(
        "INSERT OR IGNORE INTO users(user_id, balance, referrer_id) VALUES(?, 0, ?)",
        user_id, referrer_id
    )


async def get_referrer(user_id: int):
    return await _fetchval("SELECT referrer_id FROM users WHERE user_id = ?", user_id)


async def get_referrals_count(user_id: int) -> int:
    return await _fetchval("SELECT COUNT(*) FROM users WHERE referrer_id = ?", user_id) or 0


async def get_paid_referrals_count(user_id: int) -> int:
    return await _fetchval(
        "SELECT COUNT(*) FROM users WHERE referrer_id = ? AND has_purchased = 1", user_id
    ) or 0


async def mark_purchased(user_id: int):
    await _execute("UPDATE users SET has_purchased = 1 WHERE user_id = ?", user_id)


async def has_user_purchased(user_id: int) -> bool:
    return await _fetchval("SELECT has_purchased FROM users WHERE user_id = ?", user_id) or False


async def get_referral_config():
    return await _fetchrow("SELECT bonus_type, bonus_value FROM referral_config LIMIT 1")


async def update_referral_config(bonus_type: str, bonus_value: int):
    await _execute(
        "UPDATE referral_config SET bonus_type = ?, bonus_value = ?",
        bonus_type, bonus_value
    )


async def get_balance(user_id: int) -> int:
    row = await _fetchrow("SELECT balance FROM users WHERE user_id = ?", user_id)
    return row["balance"] if row else 0


async def add_balance(user_id: int, amount: int):
    await _execute(
        "UPDATE users SET balance = balance + ? WHERE user_id = ?",
        amount, user_id
    )


async def get_all_users() -> list[int]:
    rows = await _fetch("SELECT user_id FROM users")
    return [r["user_id"] for r in rows]


# ===================== КАТЕГОРИИ =====================

async def get_all_categories():
    return await _fetch("""
        SELECT c.id, c.name, c.emoji,
               (SELECT COUNT(*) FROM products WHERE category_id = c.id) as product_count
        FROM categories c
        ORDER BY c.id
    """)


async def get_category_by_id(category_id: int):
    return await _fetchrow("SELECT * FROM categories WHERE id = ?", category_id)


async def create_category(name: str, emoji: str = '🔹') -> int:
    row = await _fetchrow(
        "INSERT INTO categories (name, emoji) VALUES (?, ?) RETURNING id",
        name, emoji
    )
    return row["id"]


async def update_category(category_id: int, name: str, emoji: str):
    await _execute(
        "UPDATE categories SET name = ?, emoji = ? WHERE id = ?",
        name, emoji, category_id
    )


async def delete_category(category_id: int):
    await _execute("DELETE FROM categories WHERE id = ?", category_id)


# ===================== ТОВАРЫ =====================

async def get_all_products():
    return await _fetch("""
        SELECT p.id, p.name, p.description, p.price, p.photo_id,
               c.id as category_id, c.name as category_name, c.emoji as category_emoji
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        ORDER BY p.id
    """)


async def get_products_by_category(category_id: int):
    return await _fetch("""
        SELECT p.id, p.name, p.description, p.price, p.photo_id,
               c.id as category_id, c.name as category_name, c.emoji as category_emoji
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.category_id = ?
        ORDER BY p.id
    """, category_id)


async def get_product_by_id(product_id: int):
    return await _fetchrow("""
        SELECT p.id, p.name, p.description, p.price, p.photo_id,
               c.id as category_id, c.name as category_name, c.emoji as category_emoji
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.id = ?
    """, product_id)


async def add_product(name: str, price: int, category_id: int = None, description: str = '', photo_id: str = None) -> int:
    row = await _fetchrow(
        """
        INSERT INTO products (name, price, category_id, description, photo_id)
        VALUES (?, ?, ?, ?, ?) RETURNING id
        """,
        name, price, category_id, description, photo_id
    )
    return row["id"]


async def update_product(product_id: int, **fields):
    allowed = {"name", "price", "category_id", "description", "photo_id"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return
    query = "UPDATE products SET " + ", ".join(
        f"{k} = ?" for k in updates.keys()
    ) + " WHERE id = ?"
    await _execute(query, *updates.values(), product_id)


async def delete_product(product_id: int):
    await _execute("DELETE FROM products WHERE id = ?", product_id)


# ===================== КЛЮЧИ =====================

async def add_keys_to_product(product_id: int, keys_list: list):
    for key in keys_list:
        key = key.strip()
        if key:
            await _execute(
                "INSERT INTO keys_store (product_id, key_value) VALUES (?, ?)",
                product_id, key
            )


async def get_keys_by_product(product_id: int):
    return await _fetch(
        "SELECT id, key_value, used FROM keys_store WHERE product_id = ? ORDER BY id",
        product_id
    )


async def delete_key(key_id: int):
    await _execute("DELETE FROM keys_store WHERE id = ?", key_id)


async def get_unused_key(product_id: int):
    return await _fetchrow(
        "SELECT id, key_value FROM keys_store WHERE product_id = ? AND used = 0 LIMIT 1",
        product_id
    )


async def mark_key_as_used(key_id: int):
    await _execute("UPDATE keys_store SET used = 1 WHERE id = ?", key_id)


async def count_keys(product_id: int):
    total = await _fetchval(
        "SELECT COUNT(*) FROM keys_store WHERE product_id = ?", product_id
    )
    left = await _fetchval(
        "SELECT COUNT(*) FROM keys_store WHERE product_id = ? AND used = 0", product_id
    )
    return {"total": total, "left": left}


# ===================== ПОКУПКИ =====================

async def add_purchase(user_id: int, product_id: int, price: int):
    await _execute(
        "INSERT INTO purchases (user_id, product_id, price) VALUES (?, ?, ?)",
        user_id, product_id, price
    )


async def get_user_purchases(user_id: int):
    return await _fetch("""
        SELECT p.id, pr.name, p.price, p.created_at
        FROM purchases p
        JOIN products pr ON p.product_id = pr.id
        WHERE p.user_id = ?
        ORDER BY p.created_at DESC
    """, user_id)


async def get_stats():
    users = await _fetchval("SELECT COUNT(*) FROM users")
    total_sales = await _fetchval("SELECT COALESCE(SUM(price), 0) FROM purchases")
    keys_sold = await _fetchval("SELECT COUNT(*) FROM keys_store WHERE used = 1")
    products_count = await _fetchval("SELECT COUNT(*) FROM products")
    keys_left = await _fetchval("SELECT COUNT(*) FROM keys_store WHERE used = 0")
    categories_count = await _fetchval("SELECT COUNT(*) FROM categories")
    return {
        "users": users,
        "total_sales": total_sales,
        "keys_sold": keys_sold,
        "products_count": products_count,
        "keys_left": keys_left,
        "categories_count": categories_count
    }


# ===================== ПРОМОКОДЫ =====================

async def create_promocode(code: str, discount_type: str, discount_value: int, max_uses: int):
    await _execute(
        """
        INSERT INTO promocodes (code, discount_type, discount_value, max_uses)
        VALUES (?, ?, ?, ?)
        """,
        code, discount_type, discount_value, max_uses
    )


async def get_promocode(code: str):
    return await _fetchrow(
        """
        SELECT * FROM promocodes
        WHERE code = ? AND is_active = 1 AND used_count < max_uses
        """,
        code
    )


async def use_promocode(user_id: int, promocode_id: int):
    await _execute(
        "INSERT INTO promocode_uses (user_id, promocode_id) VALUES (?, ?)",
        user_id, promocode_id
    )
    await _execute(
        "UPDATE promocodes SET used_count = used_count + 1 WHERE id = ?",
        promocode_id
    )


async def check_promocode_used(user_id: int, promocode_id: int):
    row = await _fetchrow(
        "SELECT id FROM promocode_uses WHERE user_id = ? AND promocode_id = ?",
        user_id, promocode_id
    )
    return row is not None


async def get_all_promocodes():
    return await _fetch("SELECT * FROM promocodes ORDER BY id DESC")


async def delete_promocode(promocode_id: int):
    await _execute("DELETE FROM promocodes WHERE id = ?", promocode_id)


# ===================== РУЧНЫЕ ЗАКАЗЫ =====================

async def create_manual_order(user_id: int, product_id: int, amount: int) -> int:
    row = await _fetchrow(
        "INSERT INTO manual_orders (user_id, product_id, amount) VALUES (?, ?, ?) RETURNING id",
        user_id, product_id, amount
    )
    return row["id"]


async def get_manual_order(order_id: int):
    return await _fetchrow("SELECT * FROM manual_orders WHERE id = ?", order_id)


async def update_manual_order_status(order_id: int, status: str):
    await _execute("UPDATE manual_orders SET status = ? WHERE id = ?", status, order_id)


async def get_pending_manual_orders():
    return await _fetch(
        "SELECT mo.*, p.name as product_name FROM manual_orders mo "
        "JOIN products p ON mo.product_id = p.id "
        "WHERE mo.status = 'pending' ORDER BY mo.created_at DESC"
    )


# ===================== ОНЛАЙН-ЗАКАЗЫ =====================

async def save_pending_order(user_id: int, order_id: str, amount: int, provider: str):
    await _execute(
        """
        INSERT INTO pending_orders (user_id, order_id, amount, provider)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(order_id) DO UPDATE SET
            user_id = excluded.user_id,
            amount = excluded.amount,
            provider = excluded.provider,
            status = 'pending'
        """,
        user_id, order_id, amount, provider
    )


async def get_pending_order(order_id: str):
    return await _fetchrow(
        "SELECT * FROM pending_orders WHERE order_id = ?",
        order_id
    )


async def update_order_status(order_id: str, status: str):
    await _execute(
        "UPDATE pending_orders SET status = ? WHERE order_id = ?",
        status, order_id
    )
