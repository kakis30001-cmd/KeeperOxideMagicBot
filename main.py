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

# Настройки для Railway (сервер сам подставит нужный порт)
WEB_SERVER_HOST = "0.0.0.0"
WEB_SERVER_PORT = int(os.getenv("PORT", 8080))
# Ссылка на Railway (заказчик впишет её в Variables)
BASE_WEBHOOK_URL = os.getenv("RAILWAY_URL", "https://твой-домен.railway.app") 
WEBHOOK_PATH = "/telegram_webhook"

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# --- ОБРАБОТЧИК ПЛАТЕЖЕЙ PLATEGA (Аналог Flask из кода заказчика) ---
async def platega_webhook(request: web.Request):
    try:
        data = await request.json()
        print(f"📡 Вебхук Platega: {data}")
        
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
                    
                    # TODO: Здесь будет наша функция из БД для выдачи товара/баланса
                    
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
                        print(f"Ошибка отправки ключа юзеру: {e}")
                        
        return web.json_response({"status": "ok"}, status=200)
    except Exception as e:
        print(f"Ошибка обработки вебхука: {e}")
        return web.json_response({"status": "error"}, status=500)

# --- ФУНКЦИЯ ПРИ СТАРТЕ БОТА ---
async def on_startup(bot: Bot):
    await async_main() 
    await bot.set_webhook(f"{BASE_WEBHOOK_URL}{WEBHOOK_PATH}")
    print(f"✅ Webhook Telegram установлен на {BASE_WEBHOOK_URL}{WEBHOOK_PATH}")

def main():
    dp.include_router(user_router)
    
    dp.startup.register(on_startup)
    
    app = web.Application()
    
    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)
    
    app.router.add_post('/webhook', platega_webhook)
    
    print("🚀 БОТ ЗАПУЩЕН НА AIOHTTP")
    web.run_app(app, host=WEB_SERVER_HOST, port=WEB_SERVER_PORT)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
    
