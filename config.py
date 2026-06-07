import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
DB_URL = os.getenv("DB_URL")
RAILWAY_URL = os.getenv("RAILWAY_URL")
CHANNEL_ID = -1003705309530

PLATEGA_SHOP_ID = os.getenv("PLATEGA_SHOP_ID")
PLATEGA_SECRET_KEY = os.getenv("PLATEGA_SECRET_KEY")

if DB_URL:
    DB_URL = DB_URL.replace("postgresql+asyncpg://", "postgresql://")
