from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest

from app.constants import (
    AUTH_CONFIRM_EMAIL_PATH,
    AUTH_DETAIL_EMAIL_CONFIRMED,
    AUTH_DETAIL_EMAIL_NOT_CONFIRMED,
    AUTH_DETAIL_INVALID_CREDENTIALS,
    AUTH_DETAIL_INVALID_OR_EXPIRED_CONFIRM_TOKEN,
    AUTH_DETAIL_LOGIN_SUCCESS,
)
from app.core.config import settings
from app.modules.auth import router as auth_router_module
from app.modules.auth.security import (
    create_email_confirm_token,
    decode_email_confirm_token,
    hash_password,
)


@pytest.mark.asyncio
async def test_register_enqueues_confirm_email_task_with_link(
    client, monkeypatch
) -> None:
    created_users: list[object] = []
    enqueued_payloads: list[tuple[str, str]] = []

    async def fake_get_user_by_email(session, email: str):
        return None

    async def fake_create_user(session, payload):
        user = SimpleNamespace(
            id=1,
            email=payload.email,
            phone=payload.phone,
            is_email_confirmed=False,
            created_at=datetime.now(UTC),
        )
        created_users.append(user)
        return user

    def fake_delay(email: str, confirmation_link: str) -> None:
        enqueued_payloads.append((email, confirmation_link))

    monkeypatch.setattr(
        auth_router_module, "_get_user_by_email", fake_get_user_by_email
    )
    monkeypatch.setattr(auth_router_module, "_create_user", fake_create_user)
    monkeypatch.setattr(
        auth_router_module,
        "send_registration_email",
        SimpleNamespace(delay=fake_delay),
    )

    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "alice@example.com",
            "phone": "+15550001111",
            "password": "strong-pass-123",
        },
    )

    assert response.status_code == 201
    assert response.json()["email"] == "alice@example.com"
    assert len(created_users) == 1
    assert len(enqueued_payloads) == 1
    enqueued_email, confirmation_link = enqueued_payloads[0]
    assert enqueued_email == "alice@example.com"

    parsed = urlparse(confirmation_link)
    assert parsed.path == AUTH_CONFIRM_EMAIL_PATH
    query_token = parse_qs(parsed.query).get("token", [None])[0]
    assert query_token is not None

    identity = decode_email_confirm_token(query_token)
    assert identity is not None
    assert identity.user_id == 1
    assert identity.email == "alice@example.com"


@pytest.mark.asyncio
async def test_login_sets_http_only_jwt_cookie(client, monkeypatch) -> None:
    fake_user = SimpleNamespace(
        id=5,
        email="bob@example.com",
        password_hash=hash_password("strong-pass-123"),
        is_email_confirmed=True,
    )

    async def fake_get_user_by_email(session, email: str):
        if email == fake_user.email:
            return fake_user
        return None

    monkeypatch.setattr(
        auth_router_module, "_get_user_by_email", fake_get_user_by_email
    )

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "bob@example.com", "password": "strong-pass-123"},
    )

    assert response.status_code == 200
    assert response.json()["detail"] == AUTH_DETAIL_LOGIN_SUCCESS
    set_cookie = response.headers.get("set-cookie", "")
    assert f"{settings.auth_cookie_name}=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert f"Max-Age={settings.jwt_access_ttl_seconds}" in set_cookie
    assert f"samesite={settings.auth_cookie_samesite}" in set_cookie.lower()


@pytest.mark.asyncio
async def test_login_wrong_password_returns_auth_error(client, monkeypatch) -> None:
    fake_user = SimpleNamespace(
        id=7,
        email="charlie@example.com",
        password_hash=hash_password("correct-password"),
        is_email_confirmed=True,
    )

    async def fake_get_user_by_email(session, email: str):
        if email == fake_user.email:
            return fake_user
        return None

    monkeypatch.setattr(
        auth_router_module, "_get_user_by_email", fake_get_user_by_email
    )

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "charlie@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == AUTH_DETAIL_INVALID_CREDENTIALS


@pytest.mark.asyncio
async def test_confirm_email_success_sets_email_confirmed(client, monkeypatch) -> None:
    fake_user = SimpleNamespace(
        id=13,
        email="confirm@example.com",
        is_email_confirmed=False,
        email_confirmed_at=None,
        created_at=datetime.now(UTC),
    )
    marked_users: list[int] = []

    async def fake_get_user_by_id(session, user_id: int):
        if user_id == fake_user.id:
            return fake_user
        return None

    async def fake_mark_email_confirmed(session, user):
        user.is_email_confirmed = True
        user.email_confirmed_at = datetime.now(UTC)
        marked_users.append(user.id)
        return user

    monkeypatch.setattr(auth_router_module, "_get_user_by_id", fake_get_user_by_id)
    monkeypatch.setattr(
        auth_router_module, "_mark_email_confirmed", fake_mark_email_confirmed
    )

    token = create_email_confirm_token(user_id=fake_user.id, email=fake_user.email)
    response = await client.get(
        "/api/v1/auth/confirm-email",
        params={"token": token},
    )

    assert response.status_code == 200
    assert response.json()["detail"] == AUTH_DETAIL_EMAIL_CONFIRMED
    assert fake_user.is_email_confirmed is True
    assert fake_user.email_confirmed_at is not None
    assert marked_users == [fake_user.id]


@pytest.mark.asyncio
async def test_confirm_email_invalid_token_returns_error(client) -> None:
    response = await client.get(
        "/api/v1/auth/confirm-email",
        params={"token": "not-a-jwt"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == AUTH_DETAIL_INVALID_OR_EXPIRED_CONFIRM_TOKEN


@pytest.mark.asyncio
async def test_confirm_email_expired_token_returns_error(client) -> None:
    token = create_email_confirm_token(
        user_id=21,
        email="expired@example.com",
        ttl_minutes=-1,
    )
    response = await client.get(
        "/api/v1/auth/confirm-email",
        params={"token": token},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == AUTH_DETAIL_INVALID_OR_EXPIRED_CONFIRM_TOKEN


@pytest.mark.asyncio
async def test_confirm_email_reuse_returns_error(client, monkeypatch) -> None:
    fake_user = SimpleNamespace(
        id=31,
        email="already-confirmed@example.com",
        is_email_confirmed=True,
        email_confirmed_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
    )

    async def fake_get_user_by_id(session, user_id: int):
        if user_id == fake_user.id:
            return fake_user
        return None

    monkeypatch.setattr(auth_router_module, "_get_user_by_id", fake_get_user_by_id)

    token = create_email_confirm_token(user_id=fake_user.id, email=fake_user.email)
    response = await client.get(
        "/api/v1/auth/confirm-email",
        params={"token": token},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == AUTH_DETAIL_INVALID_OR_EXPIRED_CONFIRM_TOKEN


@pytest.mark.asyncio
async def test_login_unconfirmed_email_returns_forbidden(client, monkeypatch) -> None:
    fake_user = SimpleNamespace(
        id=41,
        email="unconfirmed@example.com",
        password_hash=hash_password("strong-pass-123"),
        is_email_confirmed=False,
    )

    async def fake_get_user_by_email(session, email: str):
        if email == fake_user.email:
            return fake_user
        return None

    monkeypatch.setattr(
        auth_router_module, "_get_user_by_email", fake_get_user_by_email
    )

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "unconfirmed@example.com", "password": "strong-pass-123"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == AUTH_DETAIL_EMAIL_NOT_CONFIRMED
