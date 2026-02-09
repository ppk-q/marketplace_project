from __future__ import annotations

from datetime import UTC, datetime
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
    AUTH_DETAIL_EMAIL_ALREADY_CONFIRMED,
    AUTH_DETAIL_EMAIL_CONFIRMED,
    AUTH_DETAIL_INVALID_CREDENTIALS,
    AUTH_DETAIL_INVALID_OR_EXPIRED_CONFIRM_TOKEN,
    AUTH_DETAIL_LOGIN_SUCCESS,
    AUTH_DETAIL_USER_EMAIL_EXISTS,
    AUTH_DETAIL_USER_EMAIL_OR_PHONE_EXISTS,
    AUTH_PREFIX,
    AUTH_TAG,
)
from app.core.config import settings
from app.core.db import get_session
from app.modules.auth.models import User
from app.modules.auth.schemas import (
    ConfirmEmailOut,
    LoginIn,
    LoginOut,
    RegisterIn,
    UserOut,
)
from app.modules.auth.security import (
    create_access_token,
    create_email_confirm_token,
    decode_email_confirm_token,
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

    token = create_access_token(user_id=user.id, email=user.email)
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        max_age=settings.jwt_access_ttl_seconds,
        httponly=AUTH_COOKIE_HTTPONLY,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
    )
    return LoginOut(detail=AUTH_DETAIL_LOGIN_SUCCESS)


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
        return ConfirmEmailOut(detail=AUTH_DETAIL_EMAIL_ALREADY_CONFIRMED)

    try:
        await _mark_email_confirmed(session, user)
    except IntegrityError as err:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=AUTH_DETAIL_INVALID_OR_EXPIRED_CONFIRM_TOKEN,
        ) from err

    return ConfirmEmailOut(detail=AUTH_DETAIL_EMAIL_CONFIRMED)
