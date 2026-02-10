from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.constants import AUTH_DETAIL_NOT_AUTHENTICATED
from app.core.db import get_session
from app.main import app


class FakeResult:
    """Минимальный объект ответа для имитации SQLAlchemy execute."""

    def __init__(
        self,
        *,
        scalar: object | None = None,
        scalars_list: list[object] | None = None,
    ) -> None:
        self._scalar = scalar
        self._scalars_list = scalars_list or []

    def scalar_one(self):
        return self._scalar

    def scalar_one_or_none(self):
        return self._scalar

    def scalars(self):
        return self

    def all(self) -> list[object]:
        return self._scalars_list


class FakeSession:
    """Упрощённая in-memory реализация AsyncSession для API-тестов."""

    def __init__(self, execute_results: list[FakeResult]) -> None:
        self._execute_results = list(execute_results)

    async def execute(self, stmt):
        del stmt
        if not self._execute_results:
            raise AssertionError("No fake execute result configured")
        return self._execute_results.pop(0)


@pytest.mark.asyncio
async def test_get_articles_is_public(client) -> None:
    fake_session = FakeSession(
        execute_results=[
            FakeResult(scalar=0),
            FakeResult(scalars_list=[]),
        ]
    )

    async def _fake_get_session():
        yield fake_session

    app.dependency_overrides[get_session] = _fake_get_session
    response = await client.get("/api/v1/articles")

    assert response.status_code == 200
    assert response.json()["items"] == []


@pytest.mark.asyncio
async def test_get_article_detail_is_public(client) -> None:
    fake_category = SimpleNamespace(
        id=10,
        title="Public",
        created_at=datetime.now(UTC),
    )
    fake_article = SimpleNamespace(
        id=15,
        title="Public article",
        text="Body",
        image_key=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        category=fake_category,
    )
    fake_session = FakeSession(execute_results=[FakeResult(scalar=fake_article)])

    async def _fake_get_session():
        yield fake_session

    app.dependency_overrides[get_session] = _fake_get_session
    response = await client.get("/api/v1/articles/15")

    assert response.status_code == 200
    assert response.json()["id"] == 15


@pytest.mark.asyncio
async def test_get_categories_is_public(client) -> None:
    fake_category = SimpleNamespace(
        id=1,
        title="News",
        created_at=datetime.now(UTC),
    )
    fake_session = FakeSession(
        execute_results=[FakeResult(scalars_list=[fake_category])]
    )

    async def _fake_get_session():
        yield fake_session

    app.dependency_overrides[get_session] = _fake_get_session
    response = await client.get("/api/v1/categories")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["title"] == "News"


@pytest.mark.asyncio
async def test_post_articles_requires_auth(client) -> None:
    response = await client.post(
        "/api/v1/articles",
        json={
            "title": "Protected create",
            "text": "Body",
            "category_id": 1,
            "image_key": "articles/protected.png",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == AUTH_DETAIL_NOT_AUTHENTICATED
