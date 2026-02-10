from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from urllib.parse import urlencode

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants_auth import (
    AUTH_CONFIRM_EMAIL_PATH,
    AUTH_DETAIL_AUTH_SERVICE_UNAVAILABLE,
    AUTH_DETAIL_EMAIL_NOT_CONFIRMED,
    AUTH_DETAIL_INVALID_CREDENTIALS,
    AUTH_DETAIL_INVALID_OR_EXPIRED_CONFIRM_TOKEN,
    AUTH_DETAIL_INVALID_OR_EXPIRED_REFRESH_TOKEN,
    AUTH_DETAIL_USER_EMAIL_EXISTS,
    AUTH_DETAIL_USER_EMAIL_OR_PHONE_EXISTS,
)
from app.core.config import settings
from app.core.service_errors import ServiceError
from app.modules.auth.models import User
from app.modules.auth.refresh_store import (
    RefreshStoreError,
    invalidate_refresh_token,
    register_refresh_token,
    rotate_refresh_token,
)
from app.modules.auth.schemas import LoginIn, RegisterIn
from app.modules.auth.security import (
    RefreshIdentity,
    create_access_token,
    create_email_confirm_token,
    create_refresh_token,
    decode_email_confirm_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)


class AuthServiceError(ServiceError):
    """Ошибка сервисного слоя auth."""


@dataclass(frozen=True)
class RegistrationResult:
    """Результат регистрации пользователя."""

    user: User
    confirm_link: str


@dataclass(frozen=True)
class AuthTokens:
    """Пара access/refresh токенов после успешной авторизации."""

    access_token: str
    refresh_token: str


def _auth_error(*, status_code: int, detail: str) -> AuthServiceError:
    """Создаёт сервисную ошибку auth с кодом и текстом ответа."""

    return AuthServiceError(status_code=status_code, detail=detail)


def _invalid_credentials_error() -> AuthServiceError:
    """Возвращает ошибку невалидных учётных данных."""

    return _auth_error(
        status_code=HTTPStatus.UNAUTHORIZED,
        detail=AUTH_DETAIL_INVALID_CREDENTIALS,
    )


def _email_not_confirmed_error() -> AuthServiceError:
    """Возвращает ошибку доступа для неподтверждённого email."""

    return _auth_error(
        status_code=HTTPStatus.FORBIDDEN,
        detail=AUTH_DETAIL_EMAIL_NOT_CONFIRMED,
    )


def _invalid_refresh_token_error() -> AuthServiceError:
    """Возвращает ошибку невалидного или просроченного refresh-токена."""

    return _auth_error(
        status_code=HTTPStatus.UNAUTHORIZED,
        detail=AUTH_DETAIL_INVALID_OR_EXPIRED_REFRESH_TOKEN,
    )


def _invalid_confirm_token_error() -> AuthServiceError:
    """Возвращает ошибку невалидного или просроченного confirm-токена."""

    return _auth_error(
        status_code=HTTPStatus.BAD_REQUEST,
        detail=AUTH_DETAIL_INVALID_OR_EXPIRED_CONFIRM_TOKEN,
    )


def _confirm_token_conflict_error() -> AuthServiceError:
    """Возвращает конфликт записи при подтверждении email."""

    return _auth_error(
        status_code=HTTPStatus.CONFLICT,
        detail=AUTH_DETAIL_INVALID_OR_EXPIRED_CONFIRM_TOKEN,
    )


def _user_email_exists_error() -> AuthServiceError:
    """Возвращает конфликт при повторной регистрации email."""

    return _auth_error(
        status_code=HTTPStatus.CONFLICT,
        detail=AUTH_DETAIL_USER_EMAIL_EXISTS,
    )


def _user_email_or_phone_exists_error() -> AuthServiceError:
    """Возвращает конфликт уникальности email/phone в момент сохранения."""

    return _auth_error(
        status_code=HTTPStatus.CONFLICT,
        detail=AUTH_DETAIL_USER_EMAIL_OR_PHONE_EXISTS,
    )


def _auth_service_unavailable_error() -> AuthServiceError:
    """Возвращает ошибку недоступности backend-хранилища auth."""

    return _auth_error(
        status_code=HTTPStatus.SERVICE_UNAVAILABLE,
        detail=AUTH_DETAIL_AUTH_SERVICE_UNAVAILABLE,
    )


def _ensure_email_confirmed(user: User) -> None:
    """Проверяет, что email пользователя подтверждён, если это требуется."""

    if settings.auth_require_email_confirmed and not user.is_email_confirmed:
        raise _email_not_confirmed_error()


def _create_refresh_token_with_identity(user: User) -> tuple[str, RefreshIdentity]:
    """Создаёт refresh-токен и валидирует его payload."""

    refresh_token = create_refresh_token(user_id=user.id, email=user.email)
    refresh_identity = decode_refresh_token(refresh_token)
    if refresh_identity is None:
        raise _invalid_refresh_token_error()
    return refresh_token, refresh_identity


def _decode_refresh_cookie(raw_refresh_token: str | None) -> RefreshIdentity:
    """Валидирует refresh-cookie и возвращает декодированную identity."""

    if not raw_refresh_token:
        raise _invalid_refresh_token_error()

    refresh_identity = decode_refresh_token(raw_refresh_token)
    if refresh_identity is None:
        raise _invalid_refresh_token_error()

    return refresh_identity


def _is_token_issued_for_user(*, issued_at: datetime, created_at: datetime) -> bool:
    """Проверяет, что confirm-token выпущен для актуальной записи пользователя."""

    normalized_created_at = created_at
    if normalized_created_at.tzinfo is None:
        normalized_created_at = normalized_created_at.replace(tzinfo=UTC)
    return issued_at + timedelta(seconds=1) >= normalized_created_at


def build_confirm_link(base_url: str, token: str) -> str:
    """Формирует абсолютную ссылку подтверждения email."""

    query = urlencode({"token": token})
    normalized_base_url = base_url.rstrip("/")
    return f"{normalized_base_url}{AUTH_CONFIRM_EMAIL_PATH}?{query}"


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    """Возвращает пользователя по email либо `None`."""

    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def create_user(session: AsyncSession, payload: RegisterIn) -> User:
    """Создаёт пользователя в БД и возвращает сохранённую запись."""

    user = User(
        email=payload.email,
        phone=payload.phone,
        password_hash=hash_password(payload.password),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    """Возвращает пользователя по ID либо `None`."""

    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def mark_email_confirmed(session: AsyncSession, user: User) -> User:
    """Отмечает email пользователя как подтверждённый."""

    user.is_email_confirmed = True
    user.email_confirmed_at = datetime.now(UTC)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def register_user(
    session: AsyncSession,
    payload: RegisterIn,
    *,
    base_url: str,
) -> RegistrationResult:
    """Регистрирует пользователя и готовит ссылку подтверждения email."""

    existing_user = await get_user_by_email(session, payload.email)
    if existing_user is not None:
        raise _user_email_exists_error()

    try:
        user = await create_user(session, payload)
    except IntegrityError as err:
        await session.rollback()
        raise _user_email_or_phone_exists_error() from err

    token = create_email_confirm_token(user_id=user.id, email=user.email)
    confirm_link = build_confirm_link(base_url, token)
    return RegistrationResult(user=user, confirm_link=confirm_link)


async def login_user(session: AsyncSession, payload: LoginIn) -> AuthTokens:
    """Проверяет логин/пароль и создаёт пару access/refresh токенов."""

    user = await get_user_by_email(session, payload.email)
    if user is None or not verify_password(payload.password, user.password_hash):
        raise _invalid_credentials_error()
    _ensure_email_confirmed(user)

    access_token = create_access_token(user_id=user.id, email=user.email)
    refresh_token, refresh_identity = _create_refresh_token_with_identity(user)

    try:
        await register_refresh_token(
            session,
            token_id=refresh_identity.token_id,
            user_id=user.id,
            expires_at=refresh_identity.expires_at,
        )
    except RefreshStoreError as err:
        raise _auth_service_unavailable_error() from err

    return AuthTokens(access_token=access_token, refresh_token=refresh_token)


async def refresh_user_tokens(
    session: AsyncSession,
    *,
    raw_refresh_token: str | None,
) -> AuthTokens:
    """Ротирует refresh-токен и возвращает новую пару access/refresh."""

    refresh_identity = _decode_refresh_cookie(raw_refresh_token)

    user = await get_user_by_id(session, refresh_identity.user_id)
    if user is None or user.email != refresh_identity.email:
        raise _invalid_refresh_token_error()
    _ensure_email_confirmed(user)

    new_refresh_token, new_refresh_identity = _create_refresh_token_with_identity(user)

    try:
        rotated = await rotate_refresh_token(
            session,
            old_token_id=refresh_identity.token_id,
            new_token_id=new_refresh_identity.token_id,
            user_id=user.id,
            expires_at=new_refresh_identity.expires_at,
        )
    except RefreshStoreError as err:
        raise _auth_service_unavailable_error() from err

    if not rotated:
        raise _invalid_refresh_token_error()

    new_access_token = create_access_token(user_id=user.id, email=user.email)
    return AuthTokens(access_token=new_access_token, refresh_token=new_refresh_token)


async def logout_user(
    session: AsyncSession,
    *,
    raw_refresh_token: str | None,
) -> None:
    """Инвалидирует refresh-токен на сервере, если он присутствует."""

    if not raw_refresh_token:
        return

    refresh_identity = decode_refresh_token(raw_refresh_token)
    if refresh_identity is None:
        return

    try:
        await invalidate_refresh_token(session, refresh_identity.token_id)
    except RefreshStoreError as err:
        raise _auth_service_unavailable_error() from err


async def confirm_user_email(session: AsyncSession, token: str) -> None:
    """Подтверждает email пользователя по одноразовому JWT-токену."""

    identity = decode_email_confirm_token(token)
    if identity is None:
        raise _invalid_confirm_token_error()

    user = await get_user_by_id(session, identity.user_id)
    if user is None or user.email != identity.email:
        raise _invalid_confirm_token_error()

    if user.is_email_confirmed:
        raise _invalid_confirm_token_error()

    if not _is_token_issued_for_user(
        issued_at=identity.issued_at,
        created_at=user.created_at,
    ):
        raise _invalid_confirm_token_error()

    try:
        await mark_email_confirmed(session, user)
    except IntegrityError as err:
        await session.rollback()
        raise _confirm_token_conflict_error() from err
