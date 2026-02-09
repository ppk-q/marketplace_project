from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.constants import (
    MEDIA_IMAGE_KEY_PREFIX,
    MEDIA_PRESIGN_UPLOAD_PATH,
)
from app.core.config import settings
from app.core.db import get_session
from app.main import app
from app.modules.auth.security import create_access_token
from app.modules.blog import router as blog_router_module
from app.modules.media import router as media_router_module


def _set_auth_cookie(client) -> None:
    token = create_access_token(user_id=1, email="media-user@example.com")
    client.cookies.set(settings.auth_cookie_name, token)


@pytest.mark.asyncio
async def test_presign_upload_success(client, monkeypatch) -> None:
    _set_auth_cookie(client)

    def fake_generate_upload_url(*, image_key: str, content_type: str) -> str:
        return f"https://storage.local/upload/{image_key}?content_type={content_type}"

    monkeypatch.setattr(
        media_router_module,
        "_generate_presigned_upload_url",
        fake_generate_upload_url,
    )

    response = await client.post(
        MEDIA_PRESIGN_UPLOAD_PATH,
        json={
            "file_name": "cover.png",
            "content_type": "image/png",
            "file_size": 1024,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["image_key"].startswith(MEDIA_IMAGE_KEY_PREFIX)
    assert data["image_key"].endswith(".png")
    assert "upload/" in data["upload_url"]
    assert data["required_content_type"] == "image/png"


@pytest.mark.asyncio
async def test_invalid_mime_or_extension_rejected(client) -> None:
    _set_auth_cookie(client)

    response = await client.post(
        MEDIA_PRESIGN_UPLOAD_PATH,
        json={
            "file_name": "cover.png",
            "content_type": "image/jpeg",
            "file_size": 1024,
        },
    )

    assert response.status_code == 422


class FakeSession:
    def __init__(self) -> None:
        self.last_added = None

    def add(self, obj) -> None:
        self.last_added = obj

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


@pytest.mark.asyncio
async def test_create_article_with_valid_image_key_success(client, monkeypatch) -> None:
    _set_auth_cookie(client)

    fake_category = SimpleNamespace(
        id=1,
        title="News",
        created_at=datetime.now(UTC),
    )
    fake_article = SimpleNamespace(
        id=100,
        title="Article",
        text="Text",
        image_key="articles/cover-ok.png",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        category=fake_category,
    )

    async def fake_ensure_category_exists(session, category_id: int):
        return None

    async def fake_get_article_with_category(session, article_id: int):
        return fake_article

    fake_session = FakeSession()

    async def _fake_get_session():
        yield fake_session

    app.dependency_overrides[get_session] = _fake_get_session
    monkeypatch.setattr(
        blog_router_module,
        "_ensure_category_exists",
        fake_ensure_category_exists,
    )
    monkeypatch.setattr(
        blog_router_module,
        "_get_article_with_category",
        fake_get_article_with_category,
    )

    response = await client.post(
        "/api/v1/articles",
        json={
            "title": "Article",
            "text": "Text",
            "category_id": 1,
            "image_key": "articles/cover-ok.png",
        },
    )

    assert response.status_code == 201
    assert response.json()["image_key"] == "articles/cover-ok.png"


@pytest.mark.asyncio
async def test_update_article_with_valid_image_key_success(client, monkeypatch) -> None:
    _set_auth_cookie(client)

    fake_category = SimpleNamespace(
        id=1,
        title="News",
        created_at=datetime.now(UTC),
    )
    existing_article = SimpleNamespace(
        id=200,
        title="Old",
        text="Old text",
        category_id=1,
        image_key="articles/old-cover.png",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        category=fake_category,
    )

    async def fake_get_article_with_category(session, article_id: int):
        return existing_article

    fake_session = FakeSession()

    async def _fake_get_session():
        yield fake_session

    app.dependency_overrides[get_session] = _fake_get_session
    monkeypatch.setattr(
        blog_router_module,
        "_get_article_with_category",
        fake_get_article_with_category,
    )

    response = await client.patch(
        "/api/v1/articles/200",
        json={"image_key": "articles/new-cover.webp"},
    )

    assert response.status_code == 200
    assert response.json()["image_key"] == "articles/new-cover.webp"


@pytest.mark.asyncio
async def test_invalid_image_key_rejected(client) -> None:
    _set_auth_cookie(client)

    response = await client.post(
        "/api/v1/articles",
        json={
            "title": "Article",
            "text": "Text",
            "category_id": 1,
            "image_key": "bad-key.png",
        },
    )

    assert response.status_code == 422
