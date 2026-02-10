from __future__ import annotations

import os
import sys
from collections.abc import AsyncGenerator
from pathlib import Path

import httpx
import pytest
import pytest_asyncio

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://app:app@localhost:5432/app_test"
)
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("AUTH_REFRESH_STORE_BACKEND", "memory")


class DummySession:
    pass


async def _dummy_get_session() -> AsyncGenerator[DummySession]:
    yield DummySession()


@pytest.fixture(autouse=True)
def _reset_refresh_store() -> None:
    from app.modules.auth.refresh_store import clear_refresh_store

    clear_refresh_store()
    yield
    clear_refresh_store()


@pytest.fixture(autouse=True)
def _clear_dependency_overrides() -> None:
    from app.main import app

    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[httpx.AsyncClient]:
    from app.core.db import get_session
    from app.main import app

    app.dependency_overrides[get_session] = _dummy_get_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as test_client:
        yield test_client
    app.dependency_overrides.clear()
