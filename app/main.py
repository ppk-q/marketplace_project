"""Точка входа FastAPI-приложения маркетплейс-блога."""

from fastapi import FastAPI

from app.constants import API_V1_PREFIX
from app.modules.auth.middleware import auth_middleware
from app.modules.auth.router import router as auth_router
from app.modules.blog.router import router as blog_router
from app.modules.media.router import router as media_router

app = FastAPI(title="Marketplace Blog API")
app.middleware("http")(auth_middleware)
app.include_router(auth_router, prefix=API_V1_PREFIX)
app.include_router(blog_router, prefix=API_V1_PREFIX)
app.include_router(media_router, prefix=API_V1_PREFIX)


# @app.get("/health")
# async def health():
#     return {"status": "ok"}
