import os
from sqlalchemy import BigInteger, String, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine

# Вставь сюда свой ID из @userinfobot
ADMIN_IDS = [8493522297] 

engine = create_async_engine(os.getenv('DB_URL', 'sqlite+aiosqlite:///db.sqlite3'), echo=False)
async_session = async_sessionmaker(engine)

class Base(AsyncAttrs, DeclarativeBase):
    pass

class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id = mapped_column(BigInteger, unique=True)
    balance: Mapped[int] = mapped_column(default=0)

class Key(Base):
    __tablename__ = 'keys'
    id: Mapped[int] = mapped_column(primary_key=True)
    game: Mapped[str] = mapped_column(String(50))
    device: Mapped[str] = mapped_column(String(50))
    product: Mapped[str] = mapped_column(String(50))
    key_code: Mapped[str] = mapped_column(String(100))
    is_sold: Mapped[bool] = mapped_column(default=False)

async def async_main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
