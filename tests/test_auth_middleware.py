from __future__ import annotations

import pytest
from starlette.requests import Request

from app.constants_api import HEALTH_PATH
from app.constants_auth import (
    AUTH_DETAIL_INVALID_OR_EXPIRED_TOKEN,
    AUTH_DETAIL_NOT_AUTHENTICATED,
)
from app.core.config import settings
from app.modules.auth.middleware import _is_protected_request
from app.modules.auth.security import create_access_token, create_email_confirm_token


@pytest.mark.asyncio
async def test_protected_endpoint_requires_cookie(client) -> None:
    response = await client.get("/api/v1/protected-nonexistent")

    assert response.status_code == 401
    assert response.json()["detail"] == AUTH_DETAIL_NOT_AUTHENTICATED


@pytest.mark.asyncio
async def test_protected_endpoint_allows_valid_cookie(client) -> None:
    token = create_access_token(user_id=42, email="valid@example.com")
    client.cookies.set(settings.auth_cookie_name, token)

    response = await client.get("/api/v1/protected-nonexistent")

    # Endpoint doesn't exist, but middleware passed token validation.
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_protected_endpoint_rejects_confirm_email_token(client) -> None:
    token = create_email_confirm_token(user_id=7, email="confirm@example.com")
    client.cookies.set(settings.auth_cookie_name, token)

    response = await client.get("/api/v1/protected-nonexistent")

    assert response.status_code == 401
    assert response.json()["detail"] == AUTH_DETAIL_INVALID_OR_EXPIRED_TOKEN


def _build_request(*, method: str, path: str) -> Request:
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [],
        "client": ("testclient", 12345),
        "server": ("testserver", 80),
        "scheme": "http",
        "root_path": "",
    }
    return Request(scope)


def test_public_get_articles_is_not_protected() -> None:
    request = _build_request(method="GET", path="/api/v1/articles")

    assert _is_protected_request(request) is False


def test_public_get_categories_is_not_protected() -> None:
    request = _build_request(method="GET", path="/api/v1/categories")

    assert _is_protected_request(request) is False


def test_post_articles_remains_protected() -> None:
    request = _build_request(method="POST", path="/api/v1/articles")

    assert _is_protected_request(request) is True


def test_public_get_article_detail_is_not_protected() -> None:
    request = _build_request(method="GET", path="/api/v1/articles/123")

    assert _is_protected_request(request) is False


def test_patch_article_detail_remains_protected() -> None:
    request = _build_request(method="PATCH", path="/api/v1/articles/123")

    assert _is_protected_request(request) is True


def test_health_endpoint_is_not_protected() -> None:
    request = _build_request(method="GET", path=HEALTH_PATH)

    assert _is_protected_request(request) is False
