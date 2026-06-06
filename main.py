import asyncio
import os
from aiogram import Bot, Dispatcher
from database.models import async_main
from handlers.user import user_router
from handlers.admin import admin_router

async def main():
    await async_main()
    # Получаем токен из переменных окружения Railway
    bot = Bot(token=os.getenv('BOT_TOKEN'))
    dp = Dispatcher()
    
    # Подключаем оба роутера
    dp.include_router(user_router)
    dp.include_router(admin_router)
    
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
    
