import os
import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update

from flask import Flask, request
from threading import Thread

from config import BOT_TOKEN, ADMIN_IDS, RAILWAY_URL
from database import connect_db, close_db
from handlers import user, admin, payments
from handlers.payments import setup_payment_webhooks

# ===================== Настройка логирования =====================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# ===================== Инициализация =====================
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан. Проверь переменные окружения.")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
flask_app = Flask(__name__)

# ===================== Регистрация роутеров =====================
dp.include_router(user.router)
dp.include_router(admin.router)
dp.include_router(payments.router)


# ===================== Flask Web Server =====================
def run_flask():
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Запуск Flask на порту {port}")
    flask_app.run(host="0.0.0.0", port=port, threaded=True, use_reloader=False)


# ===================== Telegram Webhook =====================
def setup_telegram_webhook(flask_app: Flask, dp: Dispatcher, bot: Bot):
    @flask_app.route("/webhook/telegram", methods=["POST"])
    def telegram_webhook():
        data = request.get_json()
        if not data:
            return "Bad Request", 400

        loop = main_loop
        if not loop:
            return "Service Unavailable", 503

        try:
            update = Update.model_validate(data, context={"bot": bot})
            future = asyncio.run_coroutine_threadsafe(
                dp.feed_webhook_update(bot, update), loop
            )
            future.result(timeout=30)
            return "OK", 200
        except Exception as e:
            logger.exception("Ошибка обработки Telegram webhook")
            return "Internal Server Error", 500


# ===================== Жизненный цикл =====================
async def on_startup():
    logger.info("Подключение к базе данных...")
    await connect_db()
    if ADMIN_IDS:
        logger.info(f"Админы: {ADMIN_IDS}")


async def on_shutdown():
    logger.info("Завершение работы...")
    await dp.storage.close()
    await bot.session.close()
    await close_db()


# ===================== Точка входа =====================
async def main():
    loop = asyncio.get_running_loop()
    payments.main_loop = loop

    await on_startup()

    # Настройка webhook-эндпоинтов
    setup_payment_webhooks(flask_app, bot)

    # Запуск Flask в отдельном потоке
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()

    if RAILWAY_URL:
        webhook_path = "/webhook/telegram"
        webhook_url = f"{RAILWAY_URL}{webhook_path}"
        logger.info(f"Установка webhook: {webhook_url}")
        await bot.set_webhook(webhook_url, drop_pending_updates=True)
        setup_telegram_webhook(flask_app, dp, bot)
        logger.info("Бот запущен в режиме webhook")
        while True:
            await asyncio.sleep(3600)
    else:
        logger.info("Запуск в режиме polling")
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен")
    finally:
        asyncio.run(on_shutdown())
