from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.constants import (
    AUTH_COOKIE_NAME_DEFAULT,
    AUTH_COOKIE_SAMESITE_DEFAULT,
    DATABASE_URL_IS_NOT_SET_ERROR,
    JWT_DEFAULT_ACCESS_TTL_MINUTES,
    JWT_DEFAULT_ALGORITHM,
    JWT_DEFAULT_EMAIL_CONFIRM_TTL_MINUTES,
    JWT_DEFAULT_SECRET,
    JWT_MAX_ACCESS_TTL_MINUTES,
)


class Settings(BaseSettings):
    """Конфигурация проекта."""

    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    database_url: str = Field(default="", validation_alias="DATABASE_URL")
    jwt_secret: str = Field(
        default=JWT_DEFAULT_SECRET,
        validation_alias="JWT_SECRET",
    )
    jwt_algorithm: str = Field(
        default=JWT_DEFAULT_ALGORITHM,
        validation_alias="JWT_ALGORITHM",
    )
    jwt_access_ttl_minutes: int = Field(
        default=JWT_DEFAULT_ACCESS_TTL_MINUTES,
        ge=1,
        le=JWT_MAX_ACCESS_TTL_MINUTES,
        validation_alias="JWT_ACCESS_TTL_MINUTES",
    )
    jwt_email_confirm_ttl_minutes: int = Field(
        default=JWT_DEFAULT_EMAIL_CONFIRM_TTL_MINUTES,
        ge=1,
        le=JWT_MAX_ACCESS_TTL_MINUTES,
        validation_alias="JWT_EMAIL_CONFIRM_TTL_MINUTES",
    )
    auth_cookie_name: str = Field(
        default=AUTH_COOKIE_NAME_DEFAULT,
        validation_alias="AUTH_COOKIE_NAME",
    )
    auth_cookie_samesite: str = Field(
        default=AUTH_COOKIE_SAMESITE_DEFAULT,
        validation_alias="AUTH_COOKIE_SAMESITE",
    )
    auth_cookie_secure: bool = Field(
        default=False,
        validation_alias="AUTH_COOKIE_SECURE",
    )

    @property
    def database_url_required(self) -> str:
        """Возвращает обязательный DATABASE_URL или выбрасывает ошибку."""

        if not self.database_url:
            raise RuntimeError(DATABASE_URL_IS_NOT_SET_ERROR)
        return self.database_url

    @property
    def jwt_access_ttl_seconds(self) -> int:
        """Возвращает TTL access-токена в секундах."""

        return self.jwt_access_ttl_minutes * 60


settings = Settings()
