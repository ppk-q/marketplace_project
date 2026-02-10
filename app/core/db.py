from collections.abc import AsyncGenerator
from typing import Final

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

POOL_PRE_PING: Final[bool] = True


def _build_engine() -> AsyncEngine:
    """Создаёт AsyncEngine на основе обязательного DATABASE_URL."""

    return create_async_engine(
        str(settings.database_url_required),
        pool_pre_ping=POOL_PRE_PING,
    )


def _build_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """Создаёт фабрику `AsyncSession` с едиными параметрами."""

    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


engine = _build_engine()
SessionLocal = _build_session_factory(engine)


async def get_session() -> AsyncGenerator[AsyncSession]:
    """Dependency для выдачи SQLAlchemy async-сессии на время запроса."""

    async with SessionLocal() as session:
        yield session
