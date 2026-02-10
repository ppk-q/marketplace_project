from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import (
    AUTH_CONFIRM_EMAIL_ENDPOINT,
    AUTH_CONFIRM_EMAIL_PATH,
    AUTH_COOKIE_HTTPONLY,
    AUTH_COOKIE_PATH_ACCESS,
    AUTH_COOKIE_PATH_REFRESH,
    AUTH_DETAIL_AUTH_SERVICE_UNAVAILABLE,
    AUTH_DETAIL_EMAIL_CONFIRMED,
    AUTH_DETAIL_EMAIL_NOT_CONFIRMED,
    AUTH_DETAIL_INVALID_CREDENTIALS,
    AUTH_DETAIL_INVALID_OR_EXPIRED_CONFIRM_TOKEN,
    AUTH_DETAIL_INVALID_OR_EXPIRED_REFRESH_TOKEN,
    AUTH_DETAIL_LOGIN_SUCCESS,
    AUTH_DETAIL_LOGOUT_SUCCESS,
    AUTH_DETAIL_REFRESH_SUCCESS,
    AUTH_DETAIL_USER_EMAIL_EXISTS,
    AUTH_DETAIL_USER_EMAIL_OR_PHONE_EXISTS,
    AUTH_LOGOUT_ENDPOINT,
    AUTH_PREFIX,
    AUTH_REFRESH_ENDPOINT,
    AUTH_TAG,
)
from app.core.config import settings
from app.core.db import get_session
from app.modules.auth.models import User
from app.modules.auth.refresh_store import (
    RefreshStoreError,
    invalidate_refresh_token,
    register_refresh_token,
    rotate_refresh_token,
)
from app.modules.auth.schemas import (
    ConfirmEmailOut,
    LoginIn,
    LoginOut,
    LogoutOut,
    RefreshOut,
    RegisterIn,
    UserOut,
)
from app.modules.auth.security import (
    create_access_token,
    create_email_confirm_token,
    create_refresh_token,
    decode_email_confirm_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from worker.tasks import send_registration_email

router = APIRouter(prefix=AUTH_PREFIX, tags=[AUTH_TAG])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def _get_user_by_email(session: AsyncSession, email: str) -> User | None:
    """Возвращает пользователя по email либо `None`, если запись отсутствует."""

    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def _create_user(session: AsyncSession, payload: RegisterIn) -> User:
    """Создаёт пользователя и фиксирует транзакцию в БД."""

    user = User(
        email=payload.email,
        phone=payload.phone,
        password_hash=hash_password(payload.password),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def _get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    """Возвращает пользователя по ID либо `None`, если запись отсутствует."""

    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def _mark_email_confirmed(session: AsyncSession, user: User) -> User:
    """Фиксирует подтверждение email пользователя в базе данных."""

    user.is_email_confirmed = True
    user.email_confirmed_at = datetime.now(UTC)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


def _build_confirm_link(request: Request, token: str) -> str:
    """Формирует абсолютную ссылку подтверждения email для отправки по почте."""

    base_url = str(request.base_url).rstrip("/")
    query = urlencode({"token": token})
    return f"{base_url}{AUTH_CONFIRM_EMAIL_PATH}?{query}"


def _cookie_domain() -> str | None:
    """Возвращает домен cookie или `None`, если домен не задан."""

    domain = settings.auth_cookie_domain.strip()
    return domain or None


def _set_auth_cookies(
    response: Response, access_token: str, refresh_token: str
) -> None:
    """Устанавливает access и refresh cookie с едиными параметрами безопасности."""

    domain = _cookie_domain()
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=access_token,
        max_age=settings.jwt_access_ttl_seconds,
        httponly=AUTH_COOKIE_HTTPONLY,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        path=AUTH_COOKIE_PATH_ACCESS,
        domain=domain,
    )
    response.set_cookie(
        key=settings.auth_refresh_cookie_name,
        value=refresh_token,
        max_age=settings.jwt_refresh_ttl_seconds,
        httponly=AUTH_COOKIE_HTTPONLY,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        path=AUTH_COOKIE_PATH_REFRESH,
        domain=domain,
    )


def _clear_auth_cookies(response: Response) -> None:
    """Удаляет auth-cookie из ответа при выходе пользователя."""

    domain = _cookie_domain()
    response.delete_cookie(
        key=settings.auth_cookie_name,
        path=AUTH_COOKIE_PATH_ACCESS,
        domain=domain,
    )
    response.delete_cookie(
        key=settings.auth_refresh_cookie_name,
        path=AUTH_COOKIE_PATH_REFRESH,
        domain=domain,
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterIn, request: Request, session: SessionDep
) -> UserOut:
    """Регистрирует пользователя и ставит задачу отправки приветственного письма."""

    existing_user = await _get_user_by_email(session, payload.email)
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=AUTH_DETAIL_USER_EMAIL_EXISTS,
        )

    try:
        user = await _create_user(session, payload)
    except IntegrityError as err:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=AUTH_DETAIL_USER_EMAIL_OR_PHONE_EXISTS,
        ) from err

    token = create_email_confirm_token(user_id=user.id, email=user.email)
    confirm_link = _build_confirm_link(request, token)
    send_registration_email.delay(user.email, confirm_link)
    return user


@router.post("/login", response_model=LoginOut)
async def login(payload: LoginIn, response: Response, session: SessionDep) -> LoginOut:
    """Авторизует пользователя и устанавливает JWT access-токен в cookie."""

    user = await _get_user_by_email(session, payload.email)
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=AUTH_DETAIL_INVALID_CREDENTIALS,
        )
    if settings.auth_require_email_confirmed and not user.is_email_confirmed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=AUTH_DETAIL_EMAIL_NOT_CONFIRMED,
        )

    access_token = create_access_token(user_id=user.id, email=user.email)
    refresh_token = create_refresh_token(user_id=user.id, email=user.email)

    refresh_identity = decode_refresh_token(refresh_token)
    if refresh_identity is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=AUTH_DETAIL_INVALID_OR_EXPIRED_REFRESH_TOKEN,
        )

    try:
        await register_refresh_token(
            session,
            token_id=refresh_identity.token_id,
            user_id=user.id,
            expires_at=refresh_identity.expires_at,
        )
    except RefreshStoreError as err:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=AUTH_DETAIL_AUTH_SERVICE_UNAVAILABLE,
        ) from err

    _set_auth_cookies(response, access_token, refresh_token)
    return LoginOut(detail=AUTH_DETAIL_LOGIN_SUCCESS)


@router.post(AUTH_REFRESH_ENDPOINT, response_model=RefreshOut)
async def refresh_tokens(
    request: Request, response: Response, session: SessionDep
) -> RefreshOut:
    """Обновляет access-cookie по валидному refresh-cookie с ротацией refresh-токена."""

    raw_refresh_token = request.cookies.get(settings.auth_refresh_cookie_name)
    if not raw_refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=AUTH_DETAIL_INVALID_OR_EXPIRED_REFRESH_TOKEN,
        )

    refresh_identity = decode_refresh_token(raw_refresh_token)
    if refresh_identity is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=AUTH_DETAIL_INVALID_OR_EXPIRED_REFRESH_TOKEN,
        )

    user = await _get_user_by_id(session, refresh_identity.user_id)
    if user is None or user.email != refresh_identity.email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=AUTH_DETAIL_INVALID_OR_EXPIRED_REFRESH_TOKEN,
        )
    if settings.auth_require_email_confirmed and not user.is_email_confirmed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=AUTH_DETAIL_EMAIL_NOT_CONFIRMED,
        )

    new_refresh_token = create_refresh_token(user_id=user.id, email=user.email)
    new_refresh_identity = decode_refresh_token(new_refresh_token)
    if new_refresh_identity is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=AUTH_DETAIL_INVALID_OR_EXPIRED_REFRESH_TOKEN,
        )

    try:
        rotated = await rotate_refresh_token(
            session,
            old_token_id=refresh_identity.token_id,
            new_token_id=new_refresh_identity.token_id,
            user_id=user.id,
            expires_at=new_refresh_identity.expires_at,
        )
    except RefreshStoreError as err:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=AUTH_DETAIL_AUTH_SERVICE_UNAVAILABLE,
        ) from err

    if not rotated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=AUTH_DETAIL_INVALID_OR_EXPIRED_REFRESH_TOKEN,
        )

    new_access_token = create_access_token(user_id=user.id, email=user.email)
    _set_auth_cookies(response, new_access_token, new_refresh_token)
    return RefreshOut(detail=AUTH_DETAIL_REFRESH_SUCCESS)


@router.post(AUTH_LOGOUT_ENDPOINT, response_model=LogoutOut)
async def logout(
    request: Request, response: Response, session: SessionDep
) -> LogoutOut:
    """Инвалидирует refresh-токен на сервере и очищает auth-cookie."""

    raw_refresh_token = request.cookies.get(settings.auth_refresh_cookie_name)
    if raw_refresh_token:
        refresh_identity = decode_refresh_token(raw_refresh_token)
        if refresh_identity is not None:
            try:
                await invalidate_refresh_token(session, refresh_identity.token_id)
            except RefreshStoreError as err:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=AUTH_DETAIL_AUTH_SERVICE_UNAVAILABLE,
                ) from err

    _clear_auth_cookies(response)
    return LogoutOut(detail=AUTH_DETAIL_LOGOUT_SUCCESS)


@router.get(AUTH_CONFIRM_EMAIL_ENDPOINT, response_model=ConfirmEmailOut)
async def confirm_email(
    token: Annotated[str, Query(min_length=1)],
    session: SessionDep,
) -> ConfirmEmailOut:
    """Подтверждает email по одноразовому токену из ссылки."""

    identity = decode_email_confirm_token(token)
    if identity is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=AUTH_DETAIL_INVALID_OR_EXPIRED_CONFIRM_TOKEN,
        )

    user = await _get_user_by_id(session, identity.user_id)
    if user is None or user.email != identity.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=AUTH_DETAIL_INVALID_OR_EXPIRED_CONFIRM_TOKEN,
        )

    if user.is_email_confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=AUTH_DETAIL_INVALID_OR_EXPIRED_CONFIRM_TOKEN,
        )

    created_at = user.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    # Токен должен быть выпущен не раньше создания пользователя.
    if identity.issued_at + timedelta(seconds=1) < created_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=AUTH_DETAIL_INVALID_OR_EXPIRED_CONFIRM_TOKEN,
        )

    try:
        await _mark_email_confirmed(session, user)
    except IntegrityError as err:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=AUTH_DETAIL_INVALID_OR_EXPIRED_CONFIRM_TOKEN,
        ) from err

    return ConfirmEmailOut(detail=AUTH_DETAIL_EMAIL_CONFIRMED)
