from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from alembic import context

# Если у тебя DATABASE_URL лежит в settings — импортируй настройки
# from app.core.config import settings
from app.core.models import Base

# ВАЖНО: импортируем модели, чтобы они зарегистрировались в Base.metadata
from app.modules.auth.models import User  # noqa: F401
from app.modules.blog.models import Article, Category, DeletedArticle  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    # заглушка для тестов
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return url

    # Должно вернуть строку вида: postgresql+asyncpg://user:pass@host:5432/dbname
    # return str(settings.database_url)


def run_migrations_offline() -> None:
    """Offline: генерит SQL без подключения к БД."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    """Синхронная часть миграций (Alembic внутри синхронный)."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Online: подключение через AsyncEngine + run_sync."""
    connectable: AsyncEngine = create_async_engine(
        get_url(),
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
