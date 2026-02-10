from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.constants import (
    EMAIL_MAX_LENGTH,
    EMAIL_MIN_LENGTH,
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    PHONE_MAX_LENGTH,
)


class RegisterIn(BaseModel):
    """Схема запроса на регистрацию пользователя."""

    email: str = Field(min_length=EMAIL_MIN_LENGTH, max_length=EMAIL_MAX_LENGTH)
    phone: str | None = Field(default=None, max_length=PHONE_MAX_LENGTH)
    password: str = Field(
        min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH
    )


class LoginIn(BaseModel):
    """Схема запроса на авторизацию пользователя."""

    email: str = Field(min_length=EMAIL_MIN_LENGTH, max_length=EMAIL_MAX_LENGTH)
    password: str = Field(
        min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH
    )


class UserOut(BaseModel):
    """Публичные данные пользователя в ответе API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    phone: str | None
    is_email_confirmed: bool
    created_at: datetime


class LoginOut(BaseModel):
    """Схема ответа при успешной авторизации."""

    detail: str


class ConfirmEmailOut(BaseModel):
    """Схема ответа для подтверждения адреса электронной почты."""

    detail: str


class RefreshOut(BaseModel):
    """Схема ответа при успешном обновлении токенов авторизации."""

    detail: str


class LogoutOut(BaseModel):
    """Схема ответа при успешном выходе пользователя из системы."""

    detail: str
