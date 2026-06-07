import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

DB_URL = os.getenv("DB_URL")
DB_URL = DB_URL.replace("postgresql+asyncpg://", "postgresql://")
