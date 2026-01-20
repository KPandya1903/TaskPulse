"""Database session management."""

from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings


@lru_cache
def get_engine():
    """Get or create the async engine (lazy initialization)."""
    return create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
    )


@lru_cache
def get_session_maker():
    """Get or create the session maker (lazy initialization)."""
    return async_sessionmaker(
        bind=get_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides a database session."""
    async with get_session_maker()() as session:
        try:
            yield session
        finally:
            await session.close()
