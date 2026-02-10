from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants_blog import (
    PAGE_DEFAULT,
    PAGE_SIZE_DEFAULT,
    PAGE_SIZE_MAX,
    PAGE_SIZE_MIN,
    SEARCH_MIN_LENGTH,
)
from app.core.db import get_session
from app.core.http_errors import raise_http_exception_from_service_error
from app.modules.blog.schemas import (
    ArticleCreate,
    ArticleListOut,
    ArticleOut,
    ArticleUpdate,
    CategoryCreate,
    CategoryOut,
)
from app.modules.blog.service import (
    BlogServiceError,
    create_article,
    create_category,
    delete_article,
    get_article,
    list_articles,
    list_categories,
    update_article,
)

router = APIRouter(tags=["blog"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post(
    "/categories",
    response_model=CategoryOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_category_endpoint(
    payload: CategoryCreate,
    session: SessionDep,
) -> CategoryOut:
    """Создаёт новую категорию блога."""

    try:
        category = await create_category(session, payload)
    except BlogServiceError as err:
        raise_http_exception_from_service_error(err)
    return category


@router.get("/categories", response_model=list[CategoryOut])
async def list_categories_endpoint(session: SessionDep) -> list[CategoryOut]:
    """Возвращает все категории, отсортированные по названию."""

    return await list_categories(session)


@router.post(
    "/articles",
    response_model=ArticleOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_article_endpoint(
    payload: ArticleCreate,
    session: SessionDep,
) -> ArticleOut:
    """Создаёт статью в выбранной категории."""

    try:
        article = await create_article(session, payload)
    except BlogServiceError as err:
        raise_http_exception_from_service_error(err)
    return article


@router.get("/articles", response_model=ArticleListOut)
async def list_articles_endpoint(
    session: SessionDep,
    page_number: int = Query(
        default=PAGE_DEFAULT,
        ge=PAGE_DEFAULT,
        description="Номер страницы, начиная с 1.",
    ),
    page_size: int = Query(
        default=PAGE_SIZE_DEFAULT,
        ge=PAGE_SIZE_MIN,
        le=PAGE_SIZE_MAX,
        description="Количество элементов на странице.",
    ),
    category_id: int | None = Query(
        default=None,
        ge=1,
        description="Фильтр по категории (ID).",
    ),
    search: str | None = Query(
        default=None,
        min_length=SEARCH_MIN_LENGTH,
        description="Полнотекстовый поиск по заголовку и тексту.",
    ),
) -> ArticleListOut:
    """Возвращает список статей с пагинацией, фильтрами и FTS-поиском."""

    return await list_articles(
        session,
        page_number=page_number,
        page_size=page_size,
        category_id=category_id,
        search=search,
    )


@router.get("/articles/{article_id}", response_model=ArticleOut)
async def get_article_endpoint(
    article_id: Annotated[int, Path(ge=1, description="ID статьи для просмотра.")],
    session: SessionDep,
) -> ArticleOut:
    """Возвращает одну статью по ID вместе с категорией."""

    try:
        article = await get_article(session, article_id)
    except BlogServiceError as err:
        raise_http_exception_from_service_error(err)
    return article


@router.patch("/articles/{article_id}", response_model=ArticleOut)
async def update_article_endpoint(
    article_id: Annotated[int, Path(ge=1, description="ID статьи для обновления.")],
    payload: ArticleUpdate,
    session: SessionDep,
) -> ArticleOut:
    """Частично обновляет статью и возвращает актуальные данные."""

    try:
        article = await update_article(session, article_id=article_id, payload=payload)
    except BlogServiceError as err:
        raise_http_exception_from_service_error(err)
    return article


@router.delete("/articles/{article_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_article_endpoint(
    article_id: Annotated[int, Path(ge=1, description="ID статьи для удаления.")],
    session: SessionDep,
) -> None:
    """Удаляет статью и переносит запись в archived таблицу."""

    try:
        await delete_article(session, article_id)
    except BlogServiceError as err:
        raise_http_exception_from_service_error(err)
