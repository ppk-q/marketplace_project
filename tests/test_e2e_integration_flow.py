from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select

from app.core.config import settings
from app.core.db import SessionLocal, get_session
from app.main import app
from app.modules.auth import router as auth_router_module
from app.modules.blog.models import Article, DeletedArticle

RUN_INTEGRATION_TESTS_ENV = "RUN_INTEGRATION_TESTS"

pytestmark = pytest.mark.integration


@dataclass
class SentEmail:
    """Данные отправленного регистрационного письма для проверки confirm-flow."""

    email: str
    confirmation_link: str


@pytest_asyncio.fixture
async def integration_client() -> httpx.AsyncClient:
    """HTTP-клиент для интеграционных тестов без подмены DB-сессии."""

    app.dependency_overrides.pop(get_session, None)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield client
    app.dependency_overrides.pop(get_session, None)


@pytest.fixture(autouse=True)
def require_integration_flag() -> None:
    """Пропускает integration-тесты, если они не включены через env-флаг."""

    if os.getenv(RUN_INTEGRATION_TESTS_ENV) != "1":
        pytest.skip(f"Set {RUN_INTEGRATION_TESTS_ENV}=1 to run integration tests.")


@pytest.mark.asyncio
async def test_auth_blog_soft_delete_e2e_flow(
    integration_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет полный e2e-флоу: auth, CRUD статьи и soft-delete архивирование."""

    sent_emails: list[SentEmail] = []

    class DummyEmailTask:
        """Заглушка Celery-задачи, сохраняющая ссылку подтверждения в память."""

        @staticmethod
        def delay(email: str, confirmation_link: str) -> None:
            sent_emails.append(
                SentEmail(email=email, confirmation_link=confirmation_link)
            )

    monkeypatch.setattr(auth_router_module, "send_registration_email", DummyEmailTask)

    suffix = uuid4().hex[:8]
    email = f"integration_{suffix}@example.com"
    password = "StrongPass123"
    category_title = f"integration-category-{suffix}"
    article_title = f"integration-article-{suffix}"
    image_key = f"articles/integration-{suffix}.png"

    register_response = await integration_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
        },
    )
    assert register_response.status_code == 201
    user = register_response.json()
    assert user["email"] == email

    assert sent_emails
    assert sent_emails[0].email == email
    parsed_link = urlparse(sent_emails[0].confirmation_link)
    confirm_path = parsed_link.path
    if parsed_link.query:
        confirm_path = f"{confirm_path}?{parsed_link.query}"

    confirm_response = await integration_client.get(confirm_path)
    assert confirm_response.status_code == 200

    login_response = await integration_client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )
    assert login_response.status_code == 200
    assert settings.auth_cookie_name in integration_client.cookies
    assert settings.auth_refresh_cookie_name in integration_client.cookies

    category_response = await integration_client.post(
        "/api/v1/categories",
        json={"title": category_title},
    )
    assert category_response.status_code == 201
    category_id = category_response.json()["id"]

    create_article_response = await integration_client.post(
        "/api/v1/articles",
        json={
            "title": article_title,
            "text": "Integration text body",
            "category_id": category_id,
            "image_key": image_key,
        },
    )
    assert create_article_response.status_code == 201
    article_id = create_article_response.json()["id"]

    public_transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=public_transport,
        base_url="http://testserver",
    ) as public_client:
        public_detail_response = await public_client.get(
            f"/api/v1/articles/{article_id}"
        )
    assert public_detail_response.status_code == 200
    assert public_detail_response.json()["id"] == article_id

    delete_response = await integration_client.delete(f"/api/v1/articles/{article_id}")
    assert delete_response.status_code == 204

    async with SessionLocal() as session:
        article_in_main = await session.get(Article, article_id)
        assert article_in_main is None

        deleted_result = await session.execute(
            select(DeletedArticle).where(DeletedArticle.title == article_title)
        )
        deleted_article = deleted_result.scalars().first()

    assert deleted_article is not None
    assert deleted_article.category_id == category_id
    assert deleted_article.image_key == image_key
