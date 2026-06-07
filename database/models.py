import os
from sqlalchemy import BigInteger, String, Boolean, ForeignKey, Integer, MetaData
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from sqlalchemy import inspect

# Используем DATABASE_URL, если он есть, иначе создаем файл локально
DB_URL = os.getenv('DATABASE_URL') or 'sqlite+aiosqlite:///db.sqlite3'
engine = create_async_engine(DB_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)

class Base(AsyncAttrs, DeclarativeBase):
    metadata = MetaData()

class User(Base):
    __tablename__ = 'users'
    tg_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    balance: Mapped[int] = mapped_column(Integer, default=0)

class Product(Base):
    __tablename__ = 'products'
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    price: Mapped[int] = mapped_column(Integer)

class Key(Base):
    __tablename__ = 'keys'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[str] = mapped_column(String(50))
    key_code: Mapped[str] = mapped_column(String(255))
    is_sold: Mapped[bool] = mapped_column(Boolean, default=False)

async def async_main():
    async with engine.begin() as conn:
        # Проверяем наличие таблиц перед созданием
        def check_tables(connection):
            inspector = inspect(connection)
            return inspector.get_table_names()
        
        tables = await conn.run_sync(check_tables)
        
        # Если таблиц нет — создаем. Если есть — ничего не делаем, ошибки не будет.
        if not tables:
            await conn.run_sync(Base.metadata.create_all)
            
