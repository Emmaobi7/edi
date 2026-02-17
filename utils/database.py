from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from utils.config import settings
from utils.entities import Base

DATABASE_URL = settings.SQLALCHEMY_DATABASE_URI

enable_echo = False
engine = create_async_engine(
    DATABASE_URL,
    echo=enable_echo,
    future=True,
    pool_pre_ping=True,  # Test connections before using
    pool_recycle=3600,   # Recycle connections after 1 hour
    pool_size=10,        # Connection pool size
    max_overflow=20      # Max overflow connections
)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

def get_session():
    session = AsyncSessionLocal()
    try:
        yield session
    finally:
        session.close()

async def get_async_session():
    """Async session generator for use with async functions"""
    session = AsyncSessionLocal()
    try:
        yield session
    finally:
        await session.close() 