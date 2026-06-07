import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
DB_URL = os.getenv("DB_URL")
RAILWAY_URL = os.getenv("RAILWAY_URL")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", 0))
