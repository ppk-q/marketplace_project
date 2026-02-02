from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Конфигурация проекта."""

    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    database_url: str = Field(default="", validation_alias="DATABASE_URL")

    @property
    def database_url_required(self) -> str:
        if not self.database_url:
            raise RuntimeError("DATABASE_URL is not set")
        return self.database_url


settings = Settings()
