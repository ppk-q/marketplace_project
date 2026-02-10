from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.constants import AUTH_REFRESH_STORE_BACKEND_REDIS
from app.core.config import settings
from app.modules.auth import refresh_store


class FakeRedisClient:
    """Простой in-memory double для проверки Redis backend логики."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[str, int]] = {}

    async def set(
        self,
        key: str,
        value: str,
        *,
        ex: int,
        nx: bool,
    ) -> bool | None:
        if nx and key in self._store:
            return None
        self._store[key] = (value, ex)
        return True

    async def exists(self, key: str) -> int:
        return int(key in self._store)

    async def eval(self, script: str, numkeys: int, *args) -> int:
        del script
        if numkeys != 2:
            raise ValueError("Expected exactly two keys")

        old_key, new_key, user_id, ttl_seconds = args
        if old_key not in self._store:
            return 0
        if new_key in self._store:
            return 0

        self._store.pop(old_key, None)
        self._store[new_key] = (str(user_id), int(ttl_seconds))
        return 1

    async def delete(self, key: str) -> int:
        deleted = key in self._store
        self._store.pop(key, None)
        return int(deleted)


@pytest.fixture
def redis_backend(monkeypatch: pytest.MonkeyPatch) -> FakeRedisClient:
    """Переключает refresh-store на Redis backend и подменяет клиент."""

    fake_client = FakeRedisClient()

    async def fake_get_redis_client() -> FakeRedisClient:
        return fake_client

    monkeypatch.setattr(
        settings,
        "auth_refresh_store_backend",
        AUTH_REFRESH_STORE_BACKEND_REDIS,
    )
    monkeypatch.setattr(refresh_store, "_get_redis_client", fake_get_redis_client)
    return fake_client


@pytest.mark.asyncio
async def test_redis_backend_register_rotate(redis_backend: FakeRedisClient) -> None:
    session = SimpleNamespace()
    expires_at = datetime.now(UTC) + timedelta(minutes=30)

    await refresh_store.register_refresh_token(
        session,
        token_id="old-token",
        user_id=1,
        expires_at=expires_at,
    )
    assert await refresh_store.is_refresh_token_active(session, "old-token") is True

    rotated = await refresh_store.rotate_refresh_token(
        session,
        old_token_id="old-token",
        new_token_id="new-token",
        user_id=1,
        expires_at=expires_at,
    )

    assert rotated is True
    assert await refresh_store.is_refresh_token_active(session, "old-token") is False
    assert await refresh_store.is_refresh_token_active(session, "new-token") is True


@pytest.mark.asyncio
async def test_redis_backend_invalidate(redis_backend: FakeRedisClient) -> None:
    session = SimpleNamespace()
    expires_at = datetime.now(UTC) + timedelta(minutes=30)

    await refresh_store.register_refresh_token(
        session,
        token_id="token-to-revoke",
        user_id=2,
        expires_at=expires_at,
    )
    assert await refresh_store.is_refresh_token_active(session, "token-to-revoke")

    await refresh_store.invalidate_refresh_token(session, "token-to-revoke")

    assert not await refresh_store.is_refresh_token_active(session, "token-to-revoke")
