from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import postgresql

from app.core.config import settings
from app.core.db import get_session
from app.main import app
from app.modules.auth.security import create_access_token
from app.modules.blog.models import DeletedArticle


class FakeResult:
    """Минимальный mock результата SQLAlchemy execute для тестов роутера."""

    def __init__(
        self, *, scalar=None, scalars_list: list[object] | None = None
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
    """Минимальная in-memory реализация AsyncSession для unit-тестов роутера."""

    def __init__(self, execute_results: list[FakeResult]) -> None:
        self._execute_results = list(execute_results)
        self.executed_statements: list[object] = []
        self.added_objects: list[object] = []
        self.deleted_objects: list[object] = []
        self.commit_called = False
        self.rollback_called = False

    async def execute(self, stmt):
        self.executed_statements.append(stmt)
        if not self._execute_results:
            raise AssertionError("No more fake execute results configured")
        return self._execute_results.pop(0)

    def add(self, obj) -> None:
        self.added_objects.append(obj)

    async def delete(self, obj) -> None:
        self.deleted_objects.append(obj)

    async def commit(self) -> None:
        self.commit_called = True

    async def rollback(self) -> None:
        self.rollback_called = True


def _build_session_override(fake_session: FakeSession):
    async def _fake_get_session():
        yield fake_session

    return _fake_get_session


def _set_auth_cookie(client) -> None:
    token = create_access_token(user_id=101, email="blog-user@example.com")
    client.cookies.set(settings.auth_cookie_name, token)


def _compile_postgres_sql(statement: object) -> str:
    compiled = statement.compile(dialect=postgresql.dialect())
    return str(compiled)


@pytest.mark.asyncio
async def test_list_articles_returns_pagination_meta_and_items(client) -> None:
    _set_auth_cookie(client)

    fake_category = SimpleNamespace(
        id=1,
        title="News",
        created_at=datetime.now(UTC),
    )
    fake_article = SimpleNamespace(
        id=5,
        title="Hello",
        text="World",
        image_key="articles/hello.png",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        category=fake_category,
    )
    fake_session = FakeSession(
        execute_results=[
            FakeResult(scalar=1),
            FakeResult(scalars_list=[fake_article]),
        ]
    )

    app.dependency_overrides[get_session] = _build_session_override(fake_session)
    response = await client.get("/api/v1/articles?page_number=1&page_size=20")

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["page_number"] == 1
    assert body["meta"]["page_size"] == 20
    assert body["meta"]["total"] == 1
    assert body["meta"]["total_pages"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["title"] == "Hello"


@pytest.mark.asyncio
async def test_list_articles_with_search_uses_postgresql_fts(client) -> None:
    _set_auth_cookie(client)

    fake_session = FakeSession(
        execute_results=[
            FakeResult(scalar=0),
            FakeResult(scalars_list=[]),
        ]
    )

    app.dependency_overrides[get_session] = _build_session_override(fake_session)
    response = await client.get("/api/v1/articles?search=смартфон")

    assert response.status_code == 200
    assert len(fake_session.executed_statements) == 2

    count_query_sql = _compile_postgres_sql(fake_session.executed_statements[0]).lower()
    assert "to_tsvector" in count_query_sql
    assert "plainto_tsquery" in count_query_sql
    assert "@@" in count_query_sql


@pytest.mark.asyncio
async def test_delete_article_moves_row_to_deleted_articles(client) -> None:
    _set_auth_cookie(client)

    fake_article = SimpleNamespace(
        id=9,
        title="To remove",
        text="Body",
        category_id=3,
        image_key="articles/old.png",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_session = FakeSession(execute_results=[FakeResult(scalar=fake_article)])

    app.dependency_overrides[get_session] = _build_session_override(fake_session)
    response = await client.delete("/api/v1/articles/9")

    assert response.status_code == 204
    assert fake_session.commit_called is True
    assert fake_session.rollback_called is False
    assert fake_session.deleted_objects == [fake_article]
    assert len(fake_session.added_objects) == 1

    archived = fake_session.added_objects[0]
    assert isinstance(archived, DeletedArticle)
    assert archived.title == fake_article.title
    assert archived.text == fake_article.text
    assert archived.category_id == fake_article.category_id
    assert archived.image_key == fake_article.image_key


@pytest.mark.asyncio
async def test_get_article_detail_public_success(client) -> None:
    fake_category = SimpleNamespace(
        id=2,
        title="Tech",
        created_at=datetime.now(UTC),
    )
    fake_article = SimpleNamespace(
        id=77,
        title="Public detail",
        text="Visible without auth cookie",
        image_key=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        category=fake_category,
    )
    fake_session = FakeSession(execute_results=[FakeResult(scalar=fake_article)])

    app.dependency_overrides[get_session] = _build_session_override(fake_session)
    response = await client.get("/api/v1/articles/77")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == 77
    assert body["title"] == "Public detail"
    assert body["category"]["id"] == 2


@pytest.mark.asyncio
async def test_get_article_detail_public_not_found(client) -> None:
    fake_session = FakeSession(execute_results=[FakeResult(scalar=None)])

    app.dependency_overrides[get_session] = _build_session_override(fake_session)
    response = await client.get("/api/v1/articles/999999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Article not found"


@pytest.mark.asyncio
async def test_create_article_requires_image_key(client) -> None:
    _set_auth_cookie(client)

    response = await client.post(
        "/api/v1/articles",
        json={
            "title": "No image",
            "text": "Body",
            "category_id": 1,
        },
    )

    assert response.status_code == 422
    assert any(
        error.get("loc") == ["body", "image_key"]
        for error in response.json().get("detail", [])
    )
