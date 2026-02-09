from __future__ import annotations

import pytest

from app.constants import (
    AUTH_DETAIL_INVALID_OR_EXPIRED_TOKEN,
    AUTH_DETAIL_NOT_AUTHENTICATED,
)
from app.core.config import settings
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
