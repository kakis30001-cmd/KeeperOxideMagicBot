import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
DB_URL = os.getenv("DB_URL")
RAILWAY_URL = os.getenv("RAILWAY_URL")

if DB_URL:
    DB_URL = DB_URL.replace("postgresql+asyncpg://", "postgresql://")
