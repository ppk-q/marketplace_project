from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.constants_blog import (
    BLOG_DETAIL_ARTICLE_NOT_FOUND,
    BLOG_DETAIL_CATEGORY_EXISTS,
    BLOG_DETAIL_CATEGORY_NOT_FOUND,
    BLOG_DETAIL_CREATE_ARTICLE_FAILED,
    BLOG_DETAIL_DELETE_ARTICLE_FAILED,
    BLOG_DETAIL_UPDATE_ARTICLE_FAILED,
)
from app.core.service_errors import ServiceError
from app.modules.blog.models import Article, Category, DeletedArticle
from app.modules.blog.schemas import (
    ArticleCreate,
    ArticleListOut,
    ArticleUpdate,
    CategoryCreate,
)


class BlogServiceError(ServiceError):
    """Ошибка сервисного слоя блога."""


def _blog_error(*, status_code: int, detail: str) -> BlogServiceError:
    """Создаёт сервисную ошибку блога с кодом и текстом ответа."""

    return BlogServiceError(status_code=status_code, detail=detail)


def _not_found_error(detail: str) -> BlogServiceError:
    """Возвращает сервисную ошибку 404."""

    return _blog_error(status_code=404, detail=detail)


def _conflict_error(detail: str) -> BlogServiceError:
    """Возвращает сервисную ошибку 409."""

    return _blog_error(status_code=409, detail=detail)


async def _commit_or_raise_conflict(session: AsyncSession, detail: str) -> None:
    """Коммитит транзакцию или возвращает 409 при конфликте записи."""

    try:
        await session.commit()
    except IntegrityError as err:
        await session.rollback()
        raise _conflict_error(detail) from err


async def ensure_category_exists(session: AsyncSession, category_id: int) -> None:
    """Проверяет наличие категории и выбрасывает 404, если она не найдена."""

    exists = await session.execute(
        select(Category.id).where(Category.id == category_id)
    )
    if exists.scalar_one_or_none() is None:
        raise _not_found_error(BLOG_DETAIL_CATEGORY_NOT_FOUND)


async def get_article_with_category(
    session: AsyncSession,
    article_id: int,
) -> Article | None:
    """Возвращает статью вместе с категорией либо `None`, если статья отсутствует."""

    result = await session.execute(
        select(Article)
        .where(Article.id == article_id)
        .options(selectinload(Article.category))
    )
    return result.scalar_one_or_none()


def _build_article_filters(
    *, category_id: int | None, search: str | None
) -> list[object]:
    """Собирает фильтры для списка статей (категория и FTS-поиск)."""

    filters: list[object] = []
    if category_id is not None:
        filters.append(Article.category_id == category_id)

    if search:
        doc = func.coalesce(Article.title, "")
        doc = doc.op("||")(" ")
        doc = doc.op("||")(func.coalesce(Article.text, ""))
        ts_vec = func.to_tsvector("russian", doc)
        ts_q = func.plainto_tsquery("russian", search)
        filters.append(ts_vec.op("@@")(ts_q))

    return filters


def _build_deleted_article(article: Article) -> DeletedArticle:
    """Создаёт архивную копию статьи для soft-delete."""

    return DeletedArticle(
        title=article.title,
        text=article.text,
        category_id=article.category_id,
        image_key=article.image_key,
        created_at=article.created_at,
        updated_at=article.updated_at,
    )


async def create_category(
    session: AsyncSession,
    payload: CategoryCreate,
) -> Category:
    """Создаёт новую категорию блога."""

    category = Category(title=payload.title)
    session.add(category)
    await _commit_or_raise_conflict(session, BLOG_DETAIL_CATEGORY_EXISTS)
    await session.refresh(category)
    return category


async def list_categories(session: AsyncSession) -> list[Category]:
    """Возвращает список категорий, отсортированных по названию."""

    result = await session.execute(select(Category).order_by(Category.title.asc()))
    return list(result.scalars().all())


async def create_article(
    session: AsyncSession,
    payload: ArticleCreate,
) -> Article:
    """Создаёт статью в выбранной категории."""

    await ensure_category_exists(session, payload.category_id)

    article = Article(
        title=payload.title,
        text=payload.text,
        category_id=payload.category_id,
        image_key=payload.image_key,
    )
    session.add(article)
    await _commit_or_raise_conflict(session, BLOG_DETAIL_CREATE_ARTICLE_FAILED)

    created = await get_article_with_category(session, article.id)
    assert created is not None
    return created


async def list_articles(
    session: AsyncSession,
    *,
    page_number: int,
    page_size: int,
    category_id: int | None,
    search: str | None,
) -> ArticleListOut:
    """Возвращает список статей с пагинацией, фильтром по категории и FTS-поиском."""

    filters = _build_article_filters(category_id=category_id, search=search)

    total_result = await session.execute(select(func.count(Article.id)).where(*filters))
    total = int(total_result.scalar_one())

    offset = (page_number - 1) * page_size
    result = await session.execute(
        select(Article)
        .where(*filters)
        .options(selectinload(Article.category))
        .order_by(Article.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    items = list(result.scalars().all())

    return ArticleListOut.build(
        items=items,
        page_number=page_number,
        page_size=page_size,
        total=total,
    )


async def get_article(
    session: AsyncSession,
    article_id: int,
) -> Article:
    """Возвращает одну статью по ID."""

    article = await get_article_with_category(session, article_id)
    if article is None:
        raise _not_found_error(BLOG_DETAIL_ARTICLE_NOT_FOUND)
    return article


async def update_article(
    session: AsyncSession,
    *,
    article_id: int,
    payload: ArticleUpdate,
) -> Article:
    """Частично обновляет статью и возвращает актуальные данные."""

    article = await get_article_with_category(session, article_id)
    if article is None:
        raise _not_found_error(BLOG_DETAIL_ARTICLE_NOT_FOUND)

    if payload.category_id is not None:
        await ensure_category_exists(session, payload.category_id)
        article.category_id = payload.category_id

    if payload.title is not None:
        article.title = payload.title
    if payload.text is not None:
        article.text = payload.text
    if payload.image_key is not None or "image_key" in payload.model_fields_set:
        article.image_key = payload.image_key

    session.add(article)
    await _commit_or_raise_conflict(session, BLOG_DETAIL_UPDATE_ARTICLE_FAILED)

    updated = await get_article_with_category(session, article_id)
    assert updated is not None
    return updated


async def delete_article(
    session: AsyncSession,
    article_id: int,
) -> None:
    """Удаляет статью (soft-delete в archived таблицу)."""

    result = await session.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()
    if article is None:
        raise _not_found_error(BLOG_DETAIL_ARTICLE_NOT_FOUND)

    deleted = _build_deleted_article(article)
    session.add(deleted)
    await session.delete(article)
    await _commit_or_raise_conflict(session, BLOG_DETAIL_DELETE_ARTICLE_FAILED)
