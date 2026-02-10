from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants_auth import (
    AUTH_CONFIRM_EMAIL_ENDPOINT,
    AUTH_DETAIL_EMAIL_CONFIRMED,
    AUTH_DETAIL_LOGIN_SUCCESS,
    AUTH_DETAIL_LOGOUT_SUCCESS,
    AUTH_DETAIL_REFRESH_SUCCESS,
    AUTH_LOGOUT_ENDPOINT,
    AUTH_PREFIX,
    AUTH_REFRESH_ENDPOINT,
    AUTH_TAG,
)
from app.core.config import settings
from app.core.db import get_session
from app.core.http_errors import raise_http_exception_from_service_error
from app.modules.auth.cookies import clear_auth_cookies, set_auth_cookies
from app.modules.auth.schemas import (
    ConfirmEmailOut,
    LoginIn,
    LoginOut,
    LogoutOut,
    RefreshOut,
    RegisterIn,
    UserOut,
)
from app.modules.auth.service import (
    AuthServiceError,
    confirm_user_email,
    login_user,
    logout_user,
    refresh_user_tokens,
    register_user,
)
from worker.tasks import send_registration_email

router = APIRouter(prefix=AUTH_PREFIX, tags=[AUTH_TAG])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterIn, request: Request, session: SessionDep
) -> UserOut:
    """Регистрирует пользователя и отправляет ссылку подтверждения email."""

    try:
        result = await register_user(
            session,
            payload,
            base_url=str(request.base_url),
        )
    except AuthServiceError as err:
        raise_http_exception_from_service_error(err)

    send_registration_email.delay(result.user.email, result.confirm_link)
    return result.user


@router.post("/login", response_model=LoginOut)
async def login(payload: LoginIn, response: Response, session: SessionDep) -> LoginOut:
    """Авторизует пользователя и устанавливает JWT access/refresh cookie."""

    try:
        tokens = await login_user(session, payload)
    except AuthServiceError as err:
        raise_http_exception_from_service_error(err)

    set_auth_cookies(response, tokens.access_token, tokens.refresh_token)
    return LoginOut(detail=AUTH_DETAIL_LOGIN_SUCCESS)


@router.post(AUTH_REFRESH_ENDPOINT, response_model=RefreshOut)
async def refresh_tokens(
    request: Request, response: Response, session: SessionDep
) -> RefreshOut:
    """Обновляет access-cookie по валидному refresh-cookie с ротацией."""

    try:
        tokens = await refresh_user_tokens(
            session,
            raw_refresh_token=request.cookies.get(settings.auth_refresh_cookie_name),
        )
    except AuthServiceError as err:
        raise_http_exception_from_service_error(err)

    set_auth_cookies(response, tokens.access_token, tokens.refresh_token)
    return RefreshOut(detail=AUTH_DETAIL_REFRESH_SUCCESS)


@router.post(AUTH_LOGOUT_ENDPOINT, response_model=LogoutOut)
async def logout(
    request: Request, response: Response, session: SessionDep
) -> LogoutOut:
    """Инвалидирует refresh-токен и очищает auth-cookie."""

    try:
        await logout_user(
            session,
            raw_refresh_token=request.cookies.get(settings.auth_refresh_cookie_name),
        )
    except AuthServiceError as err:
        raise_http_exception_from_service_error(err)

    clear_auth_cookies(response)
    return LogoutOut(detail=AUTH_DETAIL_LOGOUT_SUCCESS)


@router.get(AUTH_CONFIRM_EMAIL_ENDPOINT, response_model=ConfirmEmailOut)
async def confirm_email(
    token: Annotated[str, Query(min_length=1)],
    session: SessionDep,
) -> ConfirmEmailOut:
    """Подтверждает email по одноразовому токену из ссылки."""

    try:
        await confirm_user_email(session, token)
    except AuthServiceError as err:
        raise_http_exception_from_service_error(err)

    return ConfirmEmailOut(detail=AUTH_DETAIL_EMAIL_CONFIRMED)
