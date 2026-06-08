import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()]
DB_URL = os.getenv("DB_URL")
RAILWAY_URL = os.getenv("RAILWAY_URL")
CHANNEL_ID = -1003709565134

MERCHANT_ID = os.getenv("MERCHANT_ID")
API_SECRET = os.getenv("API_SECRET")

if DB_URL:
    DB_URL = DB_URL.replace("postgresql+asyncpg://", "postgresql://")
