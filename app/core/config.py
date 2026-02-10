from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.constants import (
    AUTH_COOKIE_DOMAIN_DEFAULT,
    AUTH_COOKIE_NAME_DEFAULT,
    AUTH_COOKIE_SAMESITE_DEFAULT,
    AUTH_REDIS_URL_DEFAULT,
    AUTH_REFRESH_COOKIE_NAME_DEFAULT,
    AUTH_REFRESH_REDIS_KEY_PREFIX_DEFAULT,
    AUTH_REFRESH_STORE_BACKEND_DB,
    AUTH_REFRESH_STORE_BACKEND_DEFAULT,
    AUTH_REFRESH_STORE_BACKEND_MEMORY,
    AUTH_REFRESH_STORE_BACKEND_REDIS,
    DATABASE_URL_IS_NOT_SET_ERROR,
    JWT_DEFAULT_ACCESS_TTL_MINUTES,
    JWT_DEFAULT_ALGORITHM,
    JWT_DEFAULT_EMAIL_CONFIRM_TTL_MINUTES,
    JWT_DEFAULT_REFRESH_TTL_MINUTES,
    JWT_DEFAULT_SECRET,
    JWT_MAX_ACCESS_TTL_MINUTES,
    S3_DEFAULT_BUCKET_NAME,
    S3_DEFAULT_PRESIGNED_TTL_SECONDS,
    S3_DEFAULT_REGION,
    S3_MAX_PRESIGNED_TTL_SECONDS,
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
    jwt_refresh_ttl_minutes: int = Field(
        default=JWT_DEFAULT_REFRESH_TTL_MINUTES,
        ge=1,
        validation_alias="JWT_REFRESH_TTL_MINUTES",
    )
    auth_cookie_name: str = Field(
        default=AUTH_COOKIE_NAME_DEFAULT,
        validation_alias="AUTH_COOKIE_NAME",
    )
    auth_refresh_cookie_name: str = Field(
        default=AUTH_REFRESH_COOKIE_NAME_DEFAULT,
        validation_alias="AUTH_REFRESH_COOKIE_NAME",
    )
    auth_cookie_samesite: str = Field(
        default=AUTH_COOKIE_SAMESITE_DEFAULT,
        validation_alias="AUTH_COOKIE_SAMESITE",
    )
    auth_cookie_secure: bool = Field(
        default=False,
        validation_alias="AUTH_COOKIE_SECURE",
    )
    auth_require_email_confirmed: bool = Field(
        default=True,
        validation_alias="AUTH_REQUIRE_EMAIL_CONFIRMED",
    )
    auth_cookie_domain: str = Field(
        default=AUTH_COOKIE_DOMAIN_DEFAULT,
        validation_alias="AUTH_COOKIE_DOMAIN",
    )
    auth_refresh_store_backend: str = Field(
        default=AUTH_REFRESH_STORE_BACKEND_DEFAULT,
        validation_alias="AUTH_REFRESH_STORE_BACKEND",
    )
    auth_redis_url: str = Field(
        default=AUTH_REDIS_URL_DEFAULT,
        validation_alias="AUTH_REDIS_URL",
    )
    auth_refresh_redis_key_prefix: str = Field(
        default=AUTH_REFRESH_REDIS_KEY_PREFIX_DEFAULT,
        validation_alias="AUTH_REFRESH_REDIS_KEY_PREFIX",
    )
    s3_endpoint_url: str = Field(
        default="",
        validation_alias="MINIO_ENDPOINT",
    )
    s3_access_key_id: str = Field(
        default="",
        validation_alias="MINIO_ACCESS_KEY",
    )
    s3_secret_access_key: str = Field(
        default="",
        validation_alias="MINIO_SECRET_KEY",
    )
    s3_bucket_name: str = Field(
        default=S3_DEFAULT_BUCKET_NAME,
        validation_alias="MINIO_BUCKET",
    )
    s3_secure: bool = Field(
        default=False,
        validation_alias="MINIO_SECURE",
    )
    s3_region_name: str = Field(
        default=S3_DEFAULT_REGION,
        validation_alias="S3_REGION",
    )
    s3_presigned_ttl_seconds: int = Field(
        default=S3_DEFAULT_PRESIGNED_TTL_SECONDS,
        ge=1,
        le=S3_MAX_PRESIGNED_TTL_SECONDS,
        validation_alias="S3_PRESIGNED_TTL_SECONDS",
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

    @property
    def jwt_refresh_ttl_seconds(self) -> int:
        """Возвращает TTL refresh-токена в секундах."""

        return self.jwt_refresh_ttl_minutes * 60

    @property
    def auth_refresh_store_backend_normalized(self) -> str:
        """Возвращает нормализованное значение backend для refresh token store."""

        backend = self.auth_refresh_store_backend.strip().lower()
        if backend in {
            AUTH_REFRESH_STORE_BACKEND_DB,
            AUTH_REFRESH_STORE_BACKEND_MEMORY,
            AUTH_REFRESH_STORE_BACKEND_REDIS,
        }:
            return backend
        return AUTH_REFRESH_STORE_BACKEND_DB


settings = Settings()
