from sqlalchemy import select
from database.models import User, Item, async_session

async def add_user(telegram_id: int):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
        if not user:
            session.add(User(telegram_id=telegram_id))
            await session.commit()

async def get_user(telegram_id: int):
    async with async_session() as session:
        return await session.scalar(select(User).where(User.telegram_id == telegram_id))

async def get_all_items():
    async with async_session() as session:
        result = await session.scalars(select(Item))
        return result.all()
