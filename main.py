import os
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from config import BOT_TOKEN
from database.models import async_main
from handlers.user import user_router

WEB_SERVER_HOST = "0.0.0.0"
WEB_SERVER_PORT = int(os.getenv("PORT", 8080))
BASE_WEBHOOK_URL = os.getenv("RAILWAY_URL", "https://your-project.railway.app")
WEBHOOK_PATH = "/telegram_webhook"

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

async def platega_webhook(request: web.Request):
    try:
        data = await request.json()
        status = data.get('status')
        payload = data.get('payload')
        
        if status == "CONFIRMED" and payload:
            if payload.startswith('user'):
                parts = payload.split('_')
                if len(parts) >= 5:
                    user_id = int(parts[1])
                    sub_type = parts[2]
                    days = int(parts[3].replace('day', ''))
                    key = parts[4]
                    
                    try:
                        await bot.send_message(
                            chat_id=user_id,
                            text=(
                                f"<b>✅ Оплата подтверждена!</b>\n\n"
                                f"🔑 Ваш ключ: <code>{key}</code>\n"
                                f"📦 Подписка: {sub_type.upper()} {days} д."
                            )
                        )
                    except Exception as e:
                        print(f"Error sending message: {e}")
                        
        return web.json_response({"status": "ok"}, status=200)
    except Exception as e:
        return web.json_response({"status": "error"}, status=500)

async def on_startup(bot: Bot):
    await async_main()
    await bot.set_webhook(f"{BASE_WEBHOOK_URL}{WEBHOOK_PATH}")

def main():
    dp.include_router(user_router)
    dp.startup.register(on_startup)
    
    app = web.Application()
    
    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)
    
    app.router.add_post('/webhook', platega_webhook)
    
    web.run_app(app, host=WEB_SERVER_HOST, port=WEB_SERVER_PORT)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
    
