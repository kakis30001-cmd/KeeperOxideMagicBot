import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from database.models import async_main
from handlers.user import user_router

async def main():
    await async_main()
    bot = Bot(token=os.getenv('BOT_TOKEN'))
    dp = Dispatcher()
    dp.include_router(user_router)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
    
