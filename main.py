import asyncio
import os
import logging
from aiogram import Bot, Dispatcher
from database.models import async_main
from handlers.user import user_router
from handlers.admin import admin_router

async def main():
    logging.basicConfig(level=logging.INFO)
    await async_main()
    
    bot = Bot(token=os.getenv('BOT_TOKEN'))
    dp = Dispatcher()
    
    dp.include_router(user_router)
    dp.include_router(admin_router)
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
