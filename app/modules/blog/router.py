from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.constants import (
    PAGE_DEFAULT,
    PAGE_SIZE_DEFAULT,
    PAGE_SIZE_MAX,
    PAGE_SIZE_MIN,
    SEARCH_MIN_LENGTH,
)
from app.core.db import get_session
from app.modules.blog.models import Article, Category, DeletedArticle
from app.modules.blog.schemas import (
    ArticleCreate,
    ArticleListOut,
    ArticleOut,
    ArticleUpdate,
    CategoryCreate,
    CategoryOut,
)

router = APIRouter(tags=["blog"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def _ensure_category_exists(session: AsyncSession, category_id: int) -> None:
    """Проверяет наличие категории и выбрасывает 404, если она не найдена."""

    exists = await session.execute(
        select(Category.id).where(Category.id == category_id)
    )
    if exists.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Category not found"
        )


async def _get_article_with_category(
    session: AsyncSession, article_id: int
) -> Article | None:
    """Возвращает статью вместе с категорией либо None, если статья отсутствует."""

    res = await session.execute(
        select(Article)
        .where(Article.id == article_id)
        .options(selectinload(Article.category))
    )
    return res.scalar_one_or_none()


@router.post(
    "/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED
)
async def create_category(payload: CategoryCreate, session: SessionDep) -> CategoryOut:
    """Создать новую категорию блога."""

    category = Category(title=payload.title)
    session.add(category)
    try:
        await session.commit()
    except IntegrityError as err:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Category with this title already exists",
        ) from err

    await session.refresh(category)
    return category


@router.get("/categories", response_model=list[CategoryOut])
async def list_categories(session: SessionDep) -> list[CategoryOut]:
    """Вернуть все категории, отсортированные по названию."""

    res = await session.execute(select(Category).order_by(Category.title.asc()))
    return list(res.scalars().all())


@router.post(
    "/articles", response_model=ArticleOut, status_code=status.HTTP_201_CREATED
)
async def create_article(payload: ArticleCreate, session: SessionDep) -> ArticleOut:
    """Создать статью в выбранной категории."""

    await _ensure_category_exists(session, payload.category_id)

    article = Article(
        title=payload.title,
        text=payload.text,
        category_id=payload.category_id,
        image_key=payload.image_key,
    )
    session.add(article)

    try:
        await session.commit()
    except IntegrityError as err:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Failed to create article",
        ) from err

    created = await _get_article_with_category(session, article.id)
    assert created
    return created


@router.get("/articles", response_model=ArticleListOut)
async def list_articles(
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
    """Список статей с пагинацией, фильтром по категории и поиском."""

    filters = []

    if category_id is not None:
        filters.append(Article.category_id == category_id)

    if search:
        # FTS без индекса на старте (потом добавим GIN миграцией)
        doc = func.concat_ws(" ", Article.title, Article.text)
        ts_vec = func.to_tsvector("russian", doc)
        ts_q = func.plainto_tsquery("russian", search)
        filters.append(ts_vec.op("@@")(ts_q))

    total_res = await session.execute(select(func.count(Article.id)).where(*filters))
    total = int(total_res.scalar_one())

    offset = (page_number - 1) * page_size
    res = await session.execute(
        select(Article)
        .where(*filters)
        .options(selectinload(Article.category))
        .order_by(Article.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    items = list(res.scalars().all())

    return ArticleListOut.build(
        items=items, page_number=page_number, page_size=page_size, total=total
    )


@router.get("/articles/{article_id}", response_model=ArticleOut)
async def get_article(
    article_id: Annotated[int, Path(ge=1, description="ID статьи для просмотра.")],
    session: SessionDep,
) -> ArticleOut:
    """Вернуть одну статью по ID вместе с категорией."""

    article = await _get_article_with_category(session, article_id)
    if article is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Article not found",
        )
    return article


@router.patch("/articles/{article_id}", response_model=ArticleOut)
async def update_article(
    article_id: Annotated[int, Path(ge=1, description="ID статьи для обновления.")],
    payload: ArticleUpdate,
    session: SessionDep,
) -> ArticleOut:
    """Частично обновить статью и вернуть актуальные данные."""

    article = await _get_article_with_category(session, article_id)
    if article is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Article not found"
        )

    if payload.category_id is not None:
        await _ensure_category_exists(session, payload.category_id)
        article.category_id = payload.category_id

    if payload.title is not None:
        article.title = payload.title
    if payload.text is not None:
        article.text = payload.text
    if payload.image_key is not None or "image_key" in payload.model_fields_set:
        # Учитываем явное null, чтобы можно было сбросить обложку
        article.image_key = payload.image_key

    session.add(article)
    try:
        await session.commit()
    except IntegrityError as err:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Failed to update article",
        ) from err

    updated = await _get_article_with_category(session, article_id)
    assert updated
    return updated


@router.delete("/articles/{article_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_article(
    article_id: Annotated[int, Path(ge=1, description="ID статьи для удаления.")],
    session: SessionDep,
) -> None:
    """Удалить статью, сохранив копию в таблице deleted_articles."""

    res = await session.execute(select(Article).where(Article.id == article_id))
    article = res.scalar_one_or_none()
    if article is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Article not found"
        )

    deleted = DeletedArticle(
        title=article.title,
        text=article.text,
        category_id=article.category_id,
        image_key=article.image_key,
        created_at=article.created_at,
        updated_at=article.updated_at,
    )
    session.add(deleted)
    await session.delete(article)
    try:
        await session.commit()
    except IntegrityError as err:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Failed to delete article",
        ) from err
