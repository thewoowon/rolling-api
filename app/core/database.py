from collections.abc import AsyncGenerator, Generator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import _to_async_url, settings


class Base(DeclarativeBase):
    pass


sync_engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.APP_DEBUG,
    pool_pre_ping=True,
)
SyncSessionLocal = sessionmaker(bind=sync_engine, autocommit=False, autoflush=False)

_async_url = settings.DATABASE_URL_ASYNC or _to_async_url(settings.DATABASE_URL)
async_engine = create_async_engine(
    _async_url,
    echo=settings.APP_DEBUG,
    pool_pre_ping=True,
)
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_sync_session() -> Generator[Session, None, None]:
    db = SyncSessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
