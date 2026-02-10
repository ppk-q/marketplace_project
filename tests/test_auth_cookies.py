from __future__ import annotations

from fastapi import Response

from app.constants_auth import (
    AUTH_COOKIE_HTTPONLY,
    AUTH_COOKIE_PATH_ACCESS,
    AUTH_COOKIE_PATH_REFRESH,
)
from app.core.config import settings
from app.modules.auth.cookies import (
    build_auth_cookies_config,
    clear_auth_cookies,
    set_auth_cookies,
)


def _cookie_headers(response: Response) -> list[str]:
    """Возвращает все set-cookie заголовки ответа в нижнем регистре."""

    return [
        value.decode().lower()
        for key, value in response.raw_headers
        if key.decode().lower() == "set-cookie"
    ]


def test_build_auth_cookies_config_uses_settings(monkeypatch) -> None:
    monkeypatch.setattr(settings, "auth_cookie_domain", "   ")
    monkeypatch.setattr(settings, "auth_cookie_secure", True)
    monkeypatch.setattr(settings, "auth_cookie_samesite", "strict")
    monkeypatch.setattr(settings, "auth_cookie_name", "test_access_cookie")
    monkeypatch.setattr(settings, "auth_refresh_cookie_name", "test_refresh_cookie")
    monkeypatch.setattr(settings, "jwt_access_ttl_minutes", 5)
    monkeypatch.setattr(settings, "jwt_refresh_ttl_minutes", 30)

    cfg = build_auth_cookies_config()

    assert cfg.common.domain is None
    assert cfg.common.httponly is AUTH_COOKIE_HTTPONLY
    assert cfg.common.secure is True
    assert cfg.common.samesite == "strict"

    assert cfg.access.key == "test_access_cookie"
    assert cfg.access.path == AUTH_COOKIE_PATH_ACCESS
    assert cfg.access.max_age == 5 * 60

    assert cfg.refresh.key == "test_refresh_cookie"
    assert cfg.refresh.path == AUTH_COOKIE_PATH_REFRESH
    assert cfg.refresh.max_age == 30 * 60


def test_set_auth_cookies_sets_expected_flags(monkeypatch) -> None:
    monkeypatch.setattr(settings, "auth_cookie_domain", "example.com")
    monkeypatch.setattr(settings, "auth_cookie_secure", True)
    monkeypatch.setattr(settings, "auth_cookie_samesite", "strict")
    monkeypatch.setattr(settings, "auth_cookie_name", "test_access_cookie")
    monkeypatch.setattr(settings, "auth_refresh_cookie_name", "test_refresh_cookie")
    monkeypatch.setattr(settings, "jwt_access_ttl_minutes", 10)
    monkeypatch.setattr(settings, "jwt_refresh_ttl_minutes", 20)

    response = Response()
    set_auth_cookies(response, "access-token", "refresh-token")

    headers = _cookie_headers(response)
    assert len(headers) == 2

    access_header = next(h for h in headers if h.startswith("test_access_cookie="))
    refresh_header = next(h for h in headers if h.startswith("test_refresh_cookie="))

    assert "access-token" in access_header
    assert "httponly" in access_header
    assert "secure" in access_header
    assert "samesite=strict" in access_header
    assert f"path={AUTH_COOKIE_PATH_ACCESS}".lower() in access_header
    assert "max-age=600" in access_header
    assert "domain=example.com" in access_header

    assert "refresh-token" in refresh_header
    assert "httponly" in refresh_header
    assert "secure" in refresh_header
    assert "samesite=strict" in refresh_header
    assert f"path={AUTH_COOKIE_PATH_REFRESH}".lower() in refresh_header
    assert "max-age=1200" in refresh_header
    assert "domain=example.com" in refresh_header


def test_clear_auth_cookies_sets_deletion_headers(monkeypatch) -> None:
    monkeypatch.setattr(settings, "auth_cookie_domain", "example.com")
    monkeypatch.setattr(settings, "auth_cookie_name", "test_access_cookie")
    monkeypatch.setattr(settings, "auth_refresh_cookie_name", "test_refresh_cookie")

    response = Response()
    clear_auth_cookies(response)

    headers = _cookie_headers(response)
    assert len(headers) == 2

    access_header = next(h for h in headers if h.startswith("test_access_cookie="))
    refresh_header = next(h for h in headers if h.startswith("test_refresh_cookie="))

    assert "max-age=0" in access_header
    assert f"path={AUTH_COOKIE_PATH_ACCESS}".lower() in access_header
    assert "domain=example.com" in access_header

    assert "max-age=0" in refresh_header
    assert f"path={AUTH_COOKIE_PATH_REFRESH}".lower() in refresh_header
    assert "domain=example.com" in refresh_header
