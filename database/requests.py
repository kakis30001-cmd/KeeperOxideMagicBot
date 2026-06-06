from sqlalchemy import select, func
from database.models import User, Item, Key, async_session

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

async def add_item(name: str, price: float):
    async with async_session() as session:
        session.add(Item(name=name, price=price))
        await session.commit()

async def add_keys(item_id: int, keys_list: list):
    async with async_session() as session:
        for key_data in keys_list:
            session.add(Key(item_id=item_id, key_data=key_data))
        await session.commit()

async def get_admin_stats():
    async with async_session() as session:
        total_users = await session.scalar(select(func.count()).select_from(User))
        sold_keys = await session.scalar(select(func.count()).select_from(Key).where(Key.is_sold == True))
        return total_users or 0, sold_keys or 0
        
