import os
from sqlalchemy import BigInteger, String, Boolean, ForeignKey, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine

# Здесь мы берем имя переменной точно такое же, как у тебя в Railway
url = os.getenv('DB_URL') or 'sqlite+aiosqlite:///db.sqlite3'
engine = create_async_engine(url, echo=False)
async_session = async_sessionmaker(engine)

class Base(AsyncAttrs, DeclarativeBase):
    pass

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
    product_id: Mapped[str] = mapped_column(String(50), ForeignKey('products.id'))
    key_code: Mapped[str] = mapped_column(String(255))
    is_sold: Mapped[bool] = mapped_column(Boolean, default=False)

async def async_main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
