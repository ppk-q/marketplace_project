from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.constants import (
    JWT_CLAIM_EMAIL,
    JWT_CLAIM_EXP,
    JWT_CLAIM_SUB,
    JWT_CLAIM_TOKEN_TYPE,
    JWT_TOKEN_TYPE_EMAIL_CONFIRM,
)
from app.core.config import settings

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


@dataclass(frozen=True)
class AuthIdentity:
    """Идентификатор пользователя, извлечённый из JWT."""

    user_id: int
    email: str


def hash_password(password: str) -> str:
    """Хэширует пароль пользователя безопасным алгоритмом."""

    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Проверяет, соответствует ли пароль сохранённому хэшу."""

    return pwd_context.verify(password, password_hash)


def create_access_token(*, user_id: int, email: str) -> str:
    """Создаёт JWT access-токен с TTL из настроек приложения."""

    expire_at = datetime.now(UTC) + timedelta(minutes=settings.jwt_access_ttl_minutes)
    payload = {
        JWT_CLAIM_SUB: str(user_id),
        JWT_CLAIM_EMAIL: email,
        JWT_CLAIM_EXP: expire_at,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_email_confirm_token(
    *, user_id: int, email: str, ttl_minutes: int | None = None
) -> str:
    """Создаёт JWT-токен подтверждения email с короткоживущим TTL."""

    minutes = ttl_minutes or settings.jwt_email_confirm_ttl_minutes
    expire_at = datetime.now(UTC) + timedelta(minutes=minutes)
    payload = {
        JWT_CLAIM_SUB: str(user_id),
        JWT_CLAIM_EMAIL: email,
        JWT_CLAIM_EXP: expire_at,
        JWT_CLAIM_TOKEN_TYPE: JWT_TOKEN_TYPE_EMAIL_CONFIRM,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> AuthIdentity | None:
    """Декодирует JWT access-токен и возвращает identity либо `None`."""

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError:
        return None

    raw_user_id = payload.get(JWT_CLAIM_SUB)
    email = payload.get(JWT_CLAIM_EMAIL)
    if raw_user_id is None or email is None:
        return None

    try:
        user_id = int(raw_user_id)
    except (TypeError, ValueError):
        return None

    if not email:
        return None

    return AuthIdentity(user_id=user_id, email=str(email))


def decode_email_confirm_token(token: str) -> AuthIdentity | None:
    """Декодирует JWT-токен подтверждения email и валидирует тип токена."""

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError:
        return None

    if payload.get(JWT_CLAIM_TOKEN_TYPE) != JWT_TOKEN_TYPE_EMAIL_CONFIRM:
        return None

    raw_user_id = payload.get(JWT_CLAIM_SUB)
    email = payload.get(JWT_CLAIM_EMAIL)
    if raw_user_id is None or email is None:
        return None

    try:
        user_id = int(raw_user_id)
    except (TypeError, ValueError):
        return None

    if not email:
        return None

    return AuthIdentity(user_id=user_id, email=str(email))
