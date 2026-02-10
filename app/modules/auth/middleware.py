from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Request, status
from fastapi.responses import JSONResponse, Response

from app.constants import (
    API_V1_PREFIX,
    AUTH_CONFIRM_EMAIL_PATH,
    AUTH_DETAIL_INVALID_OR_EXPIRED_TOKEN,
    AUTH_DETAIL_NOT_AUTHENTICATED,
    AUTH_LOGIN_PATH,
    AUTH_LOGOUT_PATH,
    AUTH_REFRESH_PATH,
    AUTH_REGISTER_PATH,
    BLOG_ARTICLE_DETAIL_PATH_PREFIX,
    BLOG_ARTICLES_PATH,
    BLOG_CATEGORIES_PATH,
    DOCS_PATH_PREFIX,
    HTTP_GET_METHOD,
    HTTP_OPTIONS_METHOD,
    OPENAPI_PATH,
    REDOC_PATH_PREFIX,
)
from app.core.config import settings
from app.modules.auth.security import decode_access_token

PROTECTED_PREFIXES = (API_V1_PREFIX,)

PUBLIC_EXACT_PATHS = {
    AUTH_REGISTER_PATH,
    AUTH_LOGIN_PATH,
    AUTH_CONFIRM_EMAIL_PATH,
    AUTH_REFRESH_PATH,
    AUTH_LOGOUT_PATH,
    OPENAPI_PATH,
}

PUBLIC_PREFIXES = (
    DOCS_PATH_PREFIX,
    REDOC_PATH_PREFIX,
)

PUBLIC_API_PREFIXES: tuple[str, ...] = ()

PUBLIC_METHOD_PATHS: set[tuple[str, str]] = {
    (HTTP_GET_METHOD, BLOG_ARTICLES_PATH),
    (HTTP_GET_METHOD, BLOG_CATEGORIES_PATH),
}

PUBLIC_METHOD_PATH_PREFIXES: set[tuple[str, str]] = {
    (HTTP_GET_METHOD, BLOG_ARTICLE_DETAIL_PATH_PREFIX),
}


def _is_public_path(method: str, path: str) -> bool:
    """Проверяет, доступен ли путь без обязательной авторизации."""

    if path in PUBLIC_EXACT_PATHS:
        return True

    if (method, path) in PUBLIC_METHOD_PATHS:
        return True

    if any(
        method == public_method and path.startswith(public_prefix)
        for public_method, public_prefix in PUBLIC_METHOD_PATH_PREFIXES
    ):
        return True

    if any(path.startswith(prefix) for prefix in PUBLIC_PREFIXES):
        return True

    return any(path.startswith(prefix) for prefix in PUBLIC_API_PREFIXES)


def _is_protected_path(path: str) -> bool:
    """Проверяет, относится ли путь к защищённой зоне API."""

    return any(path.startswith(prefix) for prefix in PROTECTED_PREFIXES)


def _is_protected_request(request: Request) -> bool:
    """Определяет, нужно ли применять проверку JWT для текущего запроса."""

    if request.method == HTTP_OPTIONS_METHOD:
        return False

    path = request.url.path
    if _is_public_path(request.method, path):
        return False

    return _is_protected_path(path)


async def auth_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Проверяет JWT-cookie для защищённых роутов и пишет identity в `request.state`."""

    if not _is_protected_request(request):
        return await call_next(request)

    token = request.cookies.get(settings.auth_cookie_name)
    if not token:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": AUTH_DETAIL_NOT_AUTHENTICATED},
        )

    identity = decode_access_token(token)
    if identity is None:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": AUTH_DETAIL_INVALID_OR_EXPIRED_TOKEN},
        )

    request.state.user_id = identity.user_id
    request.state.user_email = identity.email
    return await call_next(request)
