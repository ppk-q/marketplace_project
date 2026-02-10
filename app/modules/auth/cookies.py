from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Response

from app.constants_auth import (
    AUTH_COOKIE_HTTPONLY,
    AUTH_COOKIE_PATH_ACCESS,
    AUTH_COOKIE_PATH_REFRESH,
)
from app.core.config import settings


@dataclass(frozen=True)
class CookieCommonConfig:
    """Общие параметры безопасности для auth-cookie."""

    domain: str | None
    httponly: bool
    secure: bool
    samesite: str


@dataclass(frozen=True)
class CookieEntryConfig:
    """Конфигурация отдельной cookie (access/refresh)."""

    key: str
    path: str
    max_age: int


@dataclass(frozen=True)
class AuthCookiesConfig:
    """Полная конфигурация auth-cookie для установки/удаления."""

    common: CookieCommonConfig
    access: CookieEntryConfig
    refresh: CookieEntryConfig


def _cookie_domain() -> str | None:
    """Возвращает домен cookie или `None`, если домен не задан."""

    domain = settings.auth_cookie_domain.strip()
    return domain or None


def build_auth_cookies_config() -> AuthCookiesConfig:
    """Собирает конфигурацию auth-cookie из текущих настроек приложения."""

    common = CookieCommonConfig(
        domain=_cookie_domain(),
        httponly=AUTH_COOKIE_HTTPONLY,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
    )
    access = CookieEntryConfig(
        key=settings.auth_cookie_name,
        path=AUTH_COOKIE_PATH_ACCESS,
        max_age=settings.jwt_access_ttl_seconds,
    )
    refresh = CookieEntryConfig(
        key=settings.auth_refresh_cookie_name,
        path=AUTH_COOKIE_PATH_REFRESH,
        max_age=settings.jwt_refresh_ttl_seconds,
    )
    return AuthCookiesConfig(common=common, access=access, refresh=refresh)


def _cookie_kwargs(
    common: CookieCommonConfig, entry: CookieEntryConfig
) -> dict[str, Any]:
    """Возвращает kwargs для `Response.set_cookie`."""

    return {
        "key": entry.key,
        "max_age": entry.max_age,
        "httponly": common.httponly,
        "secure": common.secure,
        "samesite": common.samesite,
        "path": entry.path,
        "domain": common.domain,
    }


def _delete_cookie_kwargs(
    common: CookieCommonConfig, entry: CookieEntryConfig
) -> dict[str, Any]:
    """Возвращает kwargs для `Response.delete_cookie`."""

    return {
        "key": entry.key,
        "path": entry.path,
        "domain": common.domain,
    }


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    """Устанавливает access и refresh cookie с едиными параметрами безопасности."""

    cfg = build_auth_cookies_config()
    response.set_cookie(
        value=access_token,
        **_cookie_kwargs(cfg.common, cfg.access),
    )
    response.set_cookie(
        value=refresh_token,
        **_cookie_kwargs(cfg.common, cfg.refresh),
    )


def clear_auth_cookies(response: Response) -> None:
    """Удаляет auth-cookie из ответа при выходе пользователя."""

    cfg = build_auth_cookies_config()
    response.delete_cookie(**_delete_cookie_kwargs(cfg.common, cfg.access))
    response.delete_cookie(**_delete_cookie_kwargs(cfg.common, cfg.refresh))
