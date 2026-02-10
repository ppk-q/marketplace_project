from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.constants_auth import JWT_REFRESH_TOKEN_ID_LENGTH
from app.core.models import Base, IntIdPkMixin


class User(Base, IntIdPkMixin):
    """Модель пользователя для аутентификации и регистрации."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )
    phone: Mapped[str | None] = mapped_column(
        String(32),
        unique=True,
        nullable=True,
        index=True,
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_email_confirmed: Mapped[bool] = mapped_column(
        Boolean,
        server_default="false",
        nullable=False,
    )
    email_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class RefreshToken(Base):
    """Модель хранилища refresh-токенов с поддержкой revoke-list."""

    __tablename__ = "refresh_tokens"

    token_id: Mapped[str] = mapped_column(
        String(JWT_REFRESH_TOKEN_ID_LENGTH),
        primary_key=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    replaced_by_token_id: Mapped[str | None] = mapped_column(
        String(JWT_REFRESH_TOKEN_ID_LENGTH),
        nullable=True,
        unique=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
