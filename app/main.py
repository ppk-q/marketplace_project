"""Точка входа FastAPI-приложения маркетплейс-блога."""

from fastapi import FastAPI

from app.constants_api import (
    API_V1_PREFIX,
    HEALTH_PATH,
    HEALTH_STATUS_KEY,
    HEALTH_STATUS_OK,
)
from app.core.logging import setup_logging
from app.modules.auth.middleware import auth_middleware
from app.modules.auth.router import router as auth_router
from app.modules.blog.router import router as blog_router
from app.modules.media.router import router as media_router


def create_app() -> FastAPI:
    """Собирает и настраивает экземпляр FastAPI-приложения."""

    setup_logging()

    application = FastAPI(title="Marketplace Blog API")
    application.middleware("http")(auth_middleware)
    application.include_router(auth_router, prefix=API_V1_PREFIX)
    application.include_router(blog_router, prefix=API_V1_PREFIX)
    application.include_router(media_router, prefix=API_V1_PREFIX)

    @application.get(HEALTH_PATH)
    async def healthcheck() -> dict[str, str]:
        """Возвращает статус доступности API для smoke/readiness проверок."""

        return {HEALTH_STATUS_KEY: HEALTH_STATUS_OK}

    return application


app = create_app()
