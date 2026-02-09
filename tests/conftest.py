from __future__ import annotations

import os
import sys
from collections.abc import AsyncGenerator
from pathlib import Path

import httpx
import pytest_asyncio

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://app:app@localhost:5432/app_test"
)
os.environ.setdefault("JWT_SECRET", "test-secret")


class DummySession:
    pass


async def _dummy_get_session() -> AsyncGenerator[DummySession]:
    yield DummySession()


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
