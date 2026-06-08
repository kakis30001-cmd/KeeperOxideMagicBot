import asyncpg
from config import DB_URL

pool = None

async def connect_db():
    global pool
    pool = await asyncpg.create_pool(DB_URL, min_size=1, max_size=5)
    
    async with pool.acquire() as conn:
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS users(
            user_id BIGINT PRIMARY KEY,
            balance INTEGER DEFAULT 0,
            referrer_id BIGINT DEFAULT NULL,
            has_purchased BOOLEAN DEFAULT FALSE
        )
        """)
        
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS products(
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            price INTEGER NOT NULL
        )
        """)

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS keys_store(
            id SERIAL PRIMARY KEY,
            product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
            key_value TEXT NOT NULL,
            used BOOLEAN DEFAULT FALSE
        )
        """)

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS purchases(
            id SERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
            product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
            price INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        )
        """)

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS promocodes(
            id SERIAL PRIMARY KEY,
            code TEXT UNIQUE NOT NULL,
            discount_type TEXT NOT NULL,
            discount_value INTEGER NOT NULL,
            max_uses INTEGER NOT NULL,
            used_count INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE
        )
        """)

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS promocode_uses(
            id SERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
            promocode_id INTEGER REFERENCES promocodes(id) ON DELETE CASCADE,
            used_at TIMESTAMP DEFAULT NOW()
        )
        """)

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS referral_config(
            id SERIAL PRIMARY KEY,
            bonus_type TEXT NOT NULL,
            bonus_value INTEGER NOT NULL
        )
        """)
        
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS crypto_config(
            id SERIAL PRIMARY KEY,
            payment_mode TEXT DEFAULT 'auto',
            currency TEXT DEFAULT 'USDT',
            amount INTEGER DEFAULT 10,
            manual_text TEXT DEFAULT 'Для оплаты криптовалютой переведите средства на кошелек USDT TRC20: TXXXX... и отправьте скриншот и хэш перевода администратору.',
            manual_photo TEXT DEFAULT ''
        )
        """)
        
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS crypto_payments(
            id SERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
            product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
            amount INTEGER NOT NULL,
            currency TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            payment_id TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
        """)
        
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS bot_messages(
            id SERIAL PRIMARY KEY,
            message_key TEXT UNIQUE NOT NULL,
            text TEXT,
            photo_file_id TEXT,
            updated_at TIMESTAMP DEFAULT NOW()
        )
        """)
        
        await conn.execute("""
        INSERT INTO referral_config (bonus_type, bonus_value) VALUES ('rubles', 0) ON CONFLICT DO NOTHING
        """)
        
        await conn.execute("""
        INSERT INTO crypto_config (payment_mode, currency, amount, manual_text, manual_photo) 
        VALUES ('auto', 'USDT', 10, 'Для оплаты криптовалютой переведите средства на кошелек USDT TRC20: TXXXX... и отправьте скриншот и хэш перевода администратору.', '') 
        ON CONFLICT DO NOTHING
        """)
        
        await conn.execute("""
        INSERT INTO bot_messages (message_key, text, photo_file_id) VALUES 
        ('welcome', '✨ <b>Добро пожаловать в KeeperShop</b>\n\n✨ <b>Официальный магазин ключей Magic</b>\n\n👇 <b>Для покупки товаров используйте кнопки ниже</b>', NULL),
        ('info', 'ℹ️ <b>ИНФОРМАЦИЯ</b>\n\n✨ <b>Официальный бот по продаже ключей для чит клиента Magic</b>\n\n💳 <b>Оплата:</b> Platega (СБП, Криптовалюта)\n\n📌 <b>Как пользоваться:</b>\n• Приобретите ключ через меню\n• После оплаты вы получите ключ и доступ в VIP канал\n\n📞 <b>КОНТАКТЫ:</b>\n• Техподдержка: @nikita1055\n• Основной канал: @keepersell\n• Отзывы: https://t.me/KeeperOtzivi\n\n⚖️ <b>ДОКУМЕНТЫ:</b>\n• <a href="https://telegra.ph/Politika-konfidencialnosti-04-01-26">Политика конфиденциальности</a>\n• <a href="https://telegra.ph/Polzovatelskoe-soglashenie-04-01-19">Пользовательское соглашение</a>', NULL)
        ON CONFLICT (message_key) DO NOTHING
        """)
        
        try:
            await conn.execute("ALTER TABLE users ADD COLUMN has_purchased BOOLEAN DEFAULT FALSE")
        except:
            pass

async def add_user(user_id: int, referrer_id: int = None):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO users(user_id, referrer_id) VALUES($1, $2) ON CONFLICT (user_id) DO NOTHING",
            user_id, referrer_id
        )

async def get_referrer(user_id: int):
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT referrer_id FROM users WHERE user_id = $1", user_id)

async def get_referrals_count(user_id: int) -> int:
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM users WHERE referrer_id = $1", user_id) or 0

async def get_paid_referrals_count(user_id: int) -> int:
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM users WHERE referrer_id = $1 AND has_purchased = TRUE", user_id) or 0

async def mark_purchased(user_id: int):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET has_purchased = TRUE WHERE user_id = $1", user_id)

async def has_user_purchased(user_id: int) -> bool:
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT has_purchased FROM users WHERE user_id = $1", user_id) or False

async def get_referral_config():
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT bonus_type, bonus_value FROM referral_config LIMIT 1")

async def update_referral_config(bonus_type: str, bonus_value: int):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE referral_config SET bonus_type = $1, bonus_value = $2", bonus_type, bonus_value)

async def get_balance(user_id: int) -> int:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT balance FROM users WHERE user_id = $1", user_id)
        return row["balance"] if row else 0

async def update_user_balance(user_id: int, new_balance: int):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET balance = $1 WHERE user_id = $2", new_balance, user_id)

async def add_balance(user_id: int, amount: int):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET balance = balance + $1 WHERE user_id = $2", amount, user_id)

async def get_all_products():
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT id, name, price FROM products ORDER BY id")

async def get_product_by_id(product_id: int):
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT id, name, price FROM products WHERE id = $1", product_id)

async def add_product(name: str, price: int) -> int:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("INSERT INTO products (name, price) VALUES ($1, $2) RETURNING id", name, price)
        return row["id"]

async def delete_product(product_id: int):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM products WHERE id = $1", product_id)

async def add_keys_to_product(product_id: int, keys_list: list):
    async with pool.acquire() as conn:
        for key in keys_list:
            if key.strip():
                await conn.execute("INSERT INTO keys_store (product_id, key_value) VALUES ($1, $2)", product_id, key.strip())

async def get_keys_by_product(product_id: int):
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT id, key_value, used FROM keys_store WHERE product_id = $1 ORDER BY id", product_id)

async def delete_key(key_id: int):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM keys_store WHERE id = $1", key_id)

async def get_unused_key(product_id: int):
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT id, key_value FROM keys_store WHERE product_id = $1 AND used = FALSE LIMIT 1", product_id)

async def mark_key_as_used(key_id: int):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE keys_store SET used = TRUE WHERE id = $1", key_id)

async def add_purchase(user_id: int, product_id: int, price: int):
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO purchases (user_id, product_id, price) VALUES ($1, $2, $3)", user_id, product_id, price)

async def get_user_purchases(user_id: int):
    async with pool.acquire() as conn:
        return await conn.fetch("""
            SELECT p.id, pr.name, p.price, p.created_at 
            FROM purchases p
            JOIN products pr ON p.product_id = pr.id
            WHERE p.user_id = $1
            ORDER BY p.created_at DESC
        """, user_id)

async def get_stats():
    async with pool.acquire() as conn:
        users = await conn.fetchval("SELECT COUNT(*) FROM users")
        total_sales = await conn.fetchval("SELECT COALESCE(SUM(price), 0) FROM purchases")
        keys_sold = await conn.fetchval("SELECT COUNT(*) FROM keys_store WHERE used = TRUE")
        products_count = await conn.fetchval("SELECT COUNT(*) FROM products")
        keys_left = await conn.fetchval("SELECT COUNT(*) FROM keys_store WHERE used = FALSE")
        return {"users": users, "total_sales": total_sales, "keys_sold": keys_sold, "products_count": products_count, "keys_left": keys_left}

async def get_all_users():
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT user_id FROM users")

async def create_promocode(code: str, discount_type: str, discount_value: int, max_uses: int):
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO promocodes (code, discount_type, discount_value, max_uses) VALUES ($1, $2, $3, $4)", code, discount_type, discount_value, max_uses)

async def get_promocode(code: str):
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM promocodes WHERE code = $1 AND is_active = TRUE AND used_count < max_uses", code)

async def use_promocode(user_id: int, promocode_id: int):
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO promocode_uses (user_id, promocode_id) VALUES ($1, $2)", user_id, promocode_id)
        await conn.execute("UPDATE promocodes SET used_count = used_count + 1 WHERE id = $1", promocode_id)

async def check_promocode_used(user_id: int, promocode_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id FROM promocode_uses WHERE user_id = $1 AND promocode_id = $2", user_id, promocode_id)
        return row is not None

async def get_all_promocodes():
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM promocodes ORDER BY id DESC")

async def delete_promocode(promocode_id: int):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM promocodes WHERE id = $1", promocode_id)

async def get_crypto_config():
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT payment_mode, currency, amount, manual_text, manual_photo FROM crypto_config LIMIT 1")

async def update_crypto_config(payment_mode: str, currency: str, amount: int, manual_text: str, manual_photo: str = None):
    async with pool.acquire() as conn:
        if manual_photo is not None:
            await conn.execute("""
                UPDATE crypto_config 
                SET payment_mode = $1, currency = $2, amount = $3, manual_text = $4, manual_photo = $5
            """, payment_mode, currency, amount, manual_text, manual_photo)
        else:
            await conn.execute("""
                UPDATE crypto_config 
                SET payment_mode = $1, currency = $2, amount = $3, manual_text = $4
            """, payment_mode, currency, amount, manual_text)

async def add_crypto_payment(user_id: int, product_id: int, amount: int, currency: str, payment_id: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO crypto_payments (user_id, product_id, amount, currency, payment_id, status)
            VALUES ($1, $2, $3, $4, $5, 'pending')
        """, user_id, product_id, amount, currency, payment_id)

async def update_crypto_payment_status(payment_id: str, status: str):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE crypto_payments SET status = $1 WHERE payment_id = $2", status, payment_id)

async def get_crypto_payment(payment_id: str):
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM crypto_payments WHERE payment_id = $1", payment_id)

async def get_bot_message(message_key: str):
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT text, photo_file_id FROM bot_messages WHERE message_key = $1", message_key)

async def update_bot_message(message_key: str, text: str, photo_file_id: str = None):
    async with pool.acquire() as conn:
        if photo_file_id:
            await conn.execute("""
                UPDATE bot_messages SET text = $1, photo_file_id = $2, updated_at = NOW()
                WHERE message_key = $3
            """, text, photo_file_id, message_key)
        else:
            await conn.execute("""
                UPDATE bot_messages SET text = $1, updated_at = NOW()
                WHERE message_key = $2
            """, text, message_key)

async def get_all_message_keys():
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT message_key, text, photo_file_id FROM bot_messages ORDER BY id")
