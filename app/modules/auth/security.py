from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.constants_auth import (
    JWT_CLAIM_EMAIL,
    JWT_CLAIM_EXP,
    JWT_CLAIM_IAT,
    JWT_CLAIM_JTI,
    JWT_CLAIM_SUB,
    JWT_CLAIM_TOKEN_TYPE,
    JWT_TOKEN_TYPE_ACCESS,
    JWT_TOKEN_TYPE_EMAIL_CONFIRM,
    JWT_TOKEN_TYPE_REFRESH,
)
from app.core.config import settings

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


@dataclass(frozen=True)
class AuthIdentity:
    """Идентификатор пользователя, извлечённый из JWT."""

    user_id: int
    email: str


@dataclass(frozen=True)
class EmailConfirmIdentity:
    """Данные токена подтверждения email после успешной валидации JWT."""

    user_id: int
    email: str
    issued_at: datetime


@dataclass(frozen=True)
class RefreshIdentity:
    """Данные refresh-токена после успешной валидации JWT."""

    user_id: int
    email: str
    token_id: str
    expires_at: datetime


def hash_password(password: str) -> str:
    """Хэширует пароль пользователя безопасным алгоритмом."""

    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Проверяет, соответствует ли пароль сохранённому хэшу."""

    return pwd_context.verify(password, password_hash)


def create_access_token(*, user_id: int, email: str) -> str:
    """Создаёт JWT access-токен с TTL из настроек приложения."""

    issued_at = datetime.now(UTC)
    expire_at = issued_at + timedelta(minutes=settings.jwt_access_ttl_minutes)
    payload = {
        JWT_CLAIM_SUB: str(user_id),
        JWT_CLAIM_EMAIL: email,
        JWT_CLAIM_EXP: expire_at,
        JWT_CLAIM_IAT: issued_at,
        JWT_CLAIM_TOKEN_TYPE: JWT_TOKEN_TYPE_ACCESS,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_email_confirm_token(
    *, user_id: int, email: str, ttl_minutes: int | None = None
) -> str:
    """Создаёт JWT-токен подтверждения email с короткоживущим TTL."""

    minutes = ttl_minutes or settings.jwt_email_confirm_ttl_minutes
    issued_at = datetime.now(UTC)
    expire_at = issued_at + timedelta(minutes=minutes)
    payload = {
        JWT_CLAIM_SUB: str(user_id),
        JWT_CLAIM_EMAIL: email,
        JWT_CLAIM_EXP: expire_at,
        JWT_CLAIM_IAT: issued_at,
        JWT_CLAIM_TOKEN_TYPE: JWT_TOKEN_TYPE_EMAIL_CONFIRM,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(
    *, user_id: int, email: str, ttl_minutes: int | None = None
) -> str:
    """Создаёт JWT refresh-токен с уникальным `jti`."""

    issued_at = datetime.now(UTC)
    minutes = (
        ttl_minutes if ttl_minutes is not None else settings.jwt_refresh_ttl_minutes
    )
    expire_at = issued_at + timedelta(minutes=minutes)
    payload = {
        JWT_CLAIM_SUB: str(user_id),
        JWT_CLAIM_EMAIL: email,
        JWT_CLAIM_EXP: expire_at,
        JWT_CLAIM_IAT: issued_at,
        JWT_CLAIM_JTI: uuid4().hex,
        JWT_CLAIM_TOKEN_TYPE: JWT_TOKEN_TYPE_REFRESH,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> AuthIdentity | None:
    """Декодирует JWT access-токен и возвращает identity либо `None`."""

    payload = _decode_payload(token)
    if payload is None:
        return None

    if payload.get(JWT_CLAIM_TOKEN_TYPE) != JWT_TOKEN_TYPE_ACCESS:
        return None

    identity_data = _extract_identity_data(payload)
    if identity_data is None:
        return None
    return AuthIdentity(user_id=identity_data[0], email=identity_data[1])


def decode_email_confirm_token(token: str) -> EmailConfirmIdentity | None:
    """Декодирует JWT-токен подтверждения email и валидирует тип токена."""

    payload = _decode_payload(token)
    if payload is None:
        return None

    if payload.get(JWT_CLAIM_TOKEN_TYPE) != JWT_TOKEN_TYPE_EMAIL_CONFIRM:
        return None

    identity_data = _extract_identity_data(payload)
    if identity_data is None:
        return None
    user_id, email = identity_data

    issued_at = _extract_issued_at(payload)
    if issued_at is None:
        return None

    return EmailConfirmIdentity(user_id=user_id, email=email, issued_at=issued_at)


def decode_refresh_token(token: str) -> RefreshIdentity | None:
    """Декодирует refresh-токен и валидирует обязательные claims."""

    payload = _decode_payload(token)
    if payload is None:
        return None

    if payload.get(JWT_CLAIM_TOKEN_TYPE) != JWT_TOKEN_TYPE_REFRESH:
        return None

    identity_data = _extract_identity_data(payload)
    if identity_data is None:
        return None
    user_id, email = identity_data

    raw_token_id = payload.get(JWT_CLAIM_JTI)
    if raw_token_id is None:
        return None

    token_id = str(raw_token_id).strip()
    if not token_id:
        return None

    expires_at = _extract_expiration(payload)
    if expires_at is None:
        return None

    return RefreshIdentity(
        user_id=user_id,
        email=email,
        token_id=token_id,
        expires_at=expires_at,
    )


def _extract_identity_data(payload: dict[str, object]) -> tuple[int, str] | None:
    """Извлекает и валидирует обязательные поля `sub` и `email`."""

    raw_user_id = payload.get(JWT_CLAIM_SUB)
    email = payload.get(JWT_CLAIM_EMAIL)
    if raw_user_id is None or email is None:
        return None

    try:
        user_id = int(raw_user_id)
    except (TypeError, ValueError):
        return None

    email_value = str(email).strip()
    if not email_value:
        return None

    return user_id, email_value


def _decode_payload(token: str) -> dict[str, object] | None:
    """Декодирует JWT и возвращает payload-словарь либо `None` при ошибке."""

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError:
        return None

    if not isinstance(payload, dict):
        return None

    return payload


def _extract_issued_at(payload: dict[str, object]) -> datetime | None:
    """Извлекает и валидирует обязательный claim `iat`."""

    raw_issued_at = payload.get(JWT_CLAIM_IAT)
    if raw_issued_at is None:
        return None

    try:
        timestamp = float(raw_issued_at)
    except (TypeError, ValueError):
        return None

    return datetime.fromtimestamp(timestamp, UTC)


def _extract_expiration(payload: dict[str, object]) -> datetime | None:
    """Извлекает и валидирует обязательный claim `exp`."""

    raw_expiration = payload.get(JWT_CLAIM_EXP)
    if raw_expiration is None:
        return None

    try:
        timestamp = float(raw_expiration)
    except (TypeError, ValueError):
        return None

    return datetime.fromtimestamp(timestamp, UTC)
