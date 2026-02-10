from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from threading import RLock
from typing import Any

from sqlalchemy import delete, or_, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants_auth import (
    AUTH_REFRESH_REDIS_KEY_PREFIX_DEFAULT,
    AUTH_REFRESH_STORE_BACKEND_MEMORY,
    AUTH_REFRESH_STORE_BACKEND_REDIS,
)
from app.core.config import settings
from app.modules.auth.models import RefreshToken

_REDIS_ROTATE_LUA_SCRIPT = """
if redis.call('EXISTS', KEYS[1]) == 0 then
    return 0
end
if redis.call('EXISTS', KEYS[2]) ~= 0 then
    return 0
end
redis.call('DEL', KEYS[1])
redis.call('SET', KEYS[2], ARGV[1], 'EX', ARGV[2])
return 1
"""


class RefreshStoreError(RuntimeError):
    """Ошибка операций с persistent-хранилищем refresh-токенов."""


@dataclass
class RefreshTokenState:
    """Состояние refresh-токена в in-memory store."""

    is_active: bool
    expires_at: datetime
    replaced_by_token_id: str | None = None


_STORE: dict[str, RefreshTokenState] = {}
_LOCK = RLock()
_REDIS_LOCK = RLock()
_REDIS_CLIENT: Any | None = None


def _now_utc() -> datetime:
    """Возвращает текущее UTC-время для операций store."""

    return datetime.now(UTC)


async def register_refresh_token(
    session: AsyncSession,
    *,
    token_id: str,
    user_id: int,
    expires_at: datetime,
) -> None:
    """Регистрирует новый refresh-токен в выбранном backend."""

    if _use_memory_backend():
        _register_refresh_token_memory(token_id=token_id, expires_at=expires_at)
        return

    if _use_redis_backend():
        await _register_refresh_token_redis(
            token_id=token_id,
            user_id=user_id,
            expires_at=expires_at,
        )
        return

    await _cleanup_refresh_tokens(session, user_id=user_id)
    record = RefreshToken(
        token_id=token_id,
        user_id=user_id,
        expires_at=expires_at,
        revoked_at=None,
        replaced_by_token_id=None,
    )
    session.add(record)
    try:
        await session.commit()
    except SQLAlchemyError as err:
        await session.rollback()
        raise RefreshStoreError from err


async def is_refresh_token_active(session: AsyncSession, token_id: str) -> bool:
    """Проверяет, активен ли refresh-токен в выбранном backend."""

    if _use_memory_backend():
        return _is_refresh_token_active_memory(token_id)

    if _use_redis_backend():
        return await _is_refresh_token_active_redis(token_id)

    now = _now_utc()
    stmt = (
        select(RefreshToken.token_id)
        .where(RefreshToken.token_id == token_id)
        .where(RefreshToken.revoked_at.is_(None))
        .where(RefreshToken.expires_at > now)
        .limit(1)
    )
    try:
        result = await session.execute(stmt)
    except SQLAlchemyError as err:
        raise RefreshStoreError from err
    return result.scalar_one_or_none() is not None


async def rotate_refresh_token(
    session: AsyncSession,
    *,
    old_token_id: str,
    new_token_id: str,
    user_id: int,
    expires_at: datetime,
) -> bool:
    """Выполняет атомарную ротацию refresh-токена (single-use)."""

    if _use_memory_backend():
        return _rotate_refresh_token_memory(
            old_token_id=old_token_id,
            new_token_id=new_token_id,
            expires_at=expires_at,
        )

    if _use_redis_backend():
        return await _rotate_refresh_token_redis(
            old_token_id=old_token_id,
            new_token_id=new_token_id,
            user_id=user_id,
            expires_at=expires_at,
        )

    now = _now_utc()
    revoke_stmt = (
        update(RefreshToken)
        .where(RefreshToken.token_id == old_token_id)
        .where(RefreshToken.revoked_at.is_(None))
        .where(RefreshToken.expires_at > now)
        .values(revoked_at=now, replaced_by_token_id=new_token_id)
    )
    try:
        revoke_result = await session.execute(revoke_stmt)
    except SQLAlchemyError as err:
        await session.rollback()
        raise RefreshStoreError from err
    if revoke_result.rowcount != 1:
        await session.rollback()
        return False

    session.add(
        RefreshToken(
            token_id=new_token_id,
            user_id=user_id,
            expires_at=expires_at,
            revoked_at=None,
            replaced_by_token_id=None,
        )
    )
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        return False
    except SQLAlchemyError as err:
        await session.rollback()
        raise RefreshStoreError from err

    return True


async def invalidate_refresh_token(session: AsyncSession, token_id: str) -> None:
    """Инвалидирует refresh-токен в выбранном backend."""

    if _use_memory_backend():
        _invalidate_refresh_token_memory(token_id)
        return

    if _use_redis_backend():
        await _invalidate_refresh_token_redis(token_id)
        return

    now = datetime.now(UTC)
    stmt = (
        update(RefreshToken)
        .where(RefreshToken.token_id == token_id)
        .where(RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    try:
        await session.execute(stmt)
        await _cleanup_refresh_tokens(session)
        await session.commit()
    except SQLAlchemyError as err:
        await session.rollback()
        raise RefreshStoreError from err


def clear_refresh_store() -> None:
    """Очищает in-memory store refresh-токенов (используется в тестах)."""

    with _LOCK:
        _STORE.clear()


def _use_memory_backend() -> bool:
    """Возвращает `True`, если включён in-memory backend для store."""

    return (
        settings.auth_refresh_store_backend_normalized
        == AUTH_REFRESH_STORE_BACKEND_MEMORY
    )


def _use_redis_backend() -> bool:
    """Возвращает `True`, если включён Redis backend для store."""

    return (
        settings.auth_refresh_store_backend_normalized
        == AUTH_REFRESH_STORE_BACKEND_REDIS
    )


def _register_refresh_token_memory(*, token_id: str, expires_at: datetime) -> None:
    """Регистрирует refresh-токен в in-memory store."""

    with _LOCK:
        _cleanup_refresh_tokens_memory()
        _STORE[token_id] = RefreshTokenState(
            is_active=True,
            expires_at=expires_at,
            replaced_by_token_id=None,
        )


def _is_refresh_token_active_memory(token_id: str) -> bool:
    """Проверяет активность refresh-токена в in-memory store."""

    with _LOCK:
        state = _STORE.get(token_id)
        return bool(
            state
            and state.is_active
            and state.expires_at > _now_utc()
            and state.replaced_by_token_id is None
        )


def _rotate_refresh_token_memory(
    *, old_token_id: str, new_token_id: str, expires_at: datetime
) -> bool:
    """Ротирует refresh-токен в in-memory store."""

    with _LOCK:
        old_state = _STORE.get(old_token_id)
        if old_state is None:
            return False
        if not old_state.is_active:
            return False
        if old_state.expires_at <= _now_utc():
            return False

        old_state.is_active = False
        old_state.replaced_by_token_id = new_token_id
        _STORE[new_token_id] = RefreshTokenState(
            is_active=True,
            expires_at=expires_at,
            replaced_by_token_id=None,
        )
        return True


def _invalidate_refresh_token_memory(token_id: str) -> None:
    """Инвалидирует refresh-токен в in-memory store, если он существует."""

    with _LOCK:
        state = _STORE.get(token_id)
        if state is not None:
            state.is_active = False
        _cleanup_refresh_tokens_memory()


async def _cleanup_refresh_tokens(
    session: AsyncSession,
    *,
    user_id: int | None = None,
) -> None:
    """Удаляет истёкшие и отозванные refresh-токены из DB backend."""

    now = _now_utc()
    cleanup_stmt = delete(RefreshToken).where(
        or_(
            RefreshToken.expires_at <= now,
            RefreshToken.revoked_at.is_not(None),
        )
    )
    if user_id is not None:
        cleanup_stmt = cleanup_stmt.where(RefreshToken.user_id == user_id)
    await session.execute(cleanup_stmt)


def _cleanup_refresh_tokens_memory() -> None:
    """Удаляет неактуальные refresh-токены из in-memory store."""

    now = datetime.now(UTC)
    stale_token_ids = [
        token_id
        for token_id, state in _STORE.items()
        if state.expires_at <= now or not state.is_active
    ]
    for token_id in stale_token_ids:
        _STORE.pop(token_id, None)


async def _register_refresh_token_redis(
    *,
    token_id: str,
    user_id: int,
    expires_at: datetime,
) -> None:
    """Регистрирует refresh-токен в Redis backend."""

    ttl_seconds = _ttl_seconds(expires_at)
    if ttl_seconds <= 0:
        raise RefreshStoreError("Cannot register expired refresh token")

    redis_client = await _get_redis_client()
    key = _redis_token_key(token_id)
    try:
        created = await redis_client.set(
            key,
            str(user_id),
            ex=ttl_seconds,
            nx=True,
        )
    except Exception as err:  # noqa: BLE001
        raise RefreshStoreError from err

    if created is not True:
        raise RefreshStoreError("Refresh token already exists")


async def _is_refresh_token_active_redis(token_id: str) -> bool:
    """Проверяет активность refresh-токена в Redis backend."""

    redis_client = await _get_redis_client()
    key = _redis_token_key(token_id)
    try:
        exists = await redis_client.exists(key)
    except Exception as err:  # noqa: BLE001
        raise RefreshStoreError from err

    return bool(exists)


async def _rotate_refresh_token_redis(
    *,
    old_token_id: str,
    new_token_id: str,
    user_id: int,
    expires_at: datetime,
) -> bool:
    """Выполняет атомарную ротацию refresh-токена в Redis backend."""

    ttl_seconds = _ttl_seconds(expires_at)
    if ttl_seconds <= 0:
        return False

    redis_client = await _get_redis_client()
    old_key = _redis_token_key(old_token_id)
    new_key = _redis_token_key(new_token_id)

    try:
        result = await redis_client.eval(
            _REDIS_ROTATE_LUA_SCRIPT,
            2,
            old_key,
            new_key,
            str(user_id),
            ttl_seconds,
        )
    except Exception as err:  # noqa: BLE001
        raise RefreshStoreError from err

    try:
        return int(result) == 1
    except (TypeError, ValueError) as err:
        raise RefreshStoreError("Unexpected Redis rotate response") from err


async def _invalidate_refresh_token_redis(token_id: str) -> None:
    """Инвалидирует refresh-токен в Redis backend."""

    redis_client = await _get_redis_client()
    key = _redis_token_key(token_id)
    try:
        await redis_client.delete(key)
    except Exception as err:  # noqa: BLE001
        raise RefreshStoreError from err


async def _get_redis_client() -> Any:
    """Возвращает singleton Redis async client для refresh token store."""

    global _REDIS_CLIENT

    with _REDIS_LOCK:
        if _REDIS_CLIENT is None:
            _REDIS_CLIENT = _create_redis_client()
        return _REDIS_CLIENT


def _create_redis_client() -> Any:
    """Создаёт Redis async client из конфигурации приложения."""

    try:
        import redis.asyncio as redis_async
    except ModuleNotFoundError as err:
        raise RefreshStoreError("Redis backend requires `redis` dependency.") from err

    return redis_async.from_url(
        settings.auth_redis_url,
        decode_responses=True,
    )


def _redis_token_key(token_id: str) -> str:
    """Формирует ключ refresh-токена в Redis."""

    prefix = settings.auth_refresh_redis_key_prefix.strip().strip(":")
    if not prefix:
        prefix = AUTH_REFRESH_REDIS_KEY_PREFIX_DEFAULT
    return f"{prefix}:{token_id}"


def _ttl_seconds(expires_at: datetime) -> int:
    """Возвращает TTL в секундах до истечения refresh-токена."""

    ttl_seconds = int((expires_at - _now_utc()).total_seconds())
    return max(ttl_seconds, 0)
