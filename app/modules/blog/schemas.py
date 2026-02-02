from __future__ import annotations

from datetime import datetime
from math import ceil

from pydantic import BaseModel, ConfigDict, Field

from app.modules.blog.constants import (
    IMAGE_KEY_MAX_LENGTH,
    TEXT_MIN_LENGTH,
    TITLE_MAX_LENGTH,
    TITLE_MIN_LENGTH,
)


class CategoryCreate(BaseModel):
    """Данные для создания новой категории блога."""

    title: str = Field(
        min_length=TITLE_MIN_LENGTH,
        max_length=TITLE_MAX_LENGTH,
        description="Название категории, отображаемое пользователям.",
    )


class CategoryOut(BaseModel):
    """Схема ответа с данными категории блога."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Уникальный идентификатор категории.")
    title: str = Field(description="Название категории.")
    created_at: datetime = Field(description="Дата и время создания категории.")


class ArticleCreate(BaseModel):
    """Данные для создания новой статьи."""

    title: str = Field(
        min_length=TITLE_MIN_LENGTH,
        max_length=TITLE_MAX_LENGTH,
        description="Заголовок статьи.",
    )
    text: str = Field(
        min_length=TEXT_MIN_LENGTH,
        description="Основной текст статьи в формате Markdown или plain text.",
    )
    category_id: int = Field(description="ID категории, к которой относится статья.")
    image_key: str | None = Field(
        default=None,
        max_length=IMAGE_KEY_MAX_LENGTH,
        description="Ключ или путь до обложки статьи в файловом хранилище.",
    )


class ArticleUpdate(BaseModel):
    """Данные для частичного обновления существующей статьи."""

    title: str | None = Field(
        default=None,
        min_length=TITLE_MIN_LENGTH,
        max_length=TITLE_MAX_LENGTH,
        description="Новый заголовок статьи.",
    )
    text: str | None = Field(
        default=None,
        min_length=TEXT_MIN_LENGTH,
        description="Обновлённый текст статьи.",
    )
    category_id: int | None = Field(
        default=None,
        description="ID новой категории. Оставьте пустым, чтобы не менять.",
    )
    image_key: str | None = Field(
        default=None,
        max_length=IMAGE_KEY_MAX_LENGTH,
        description="Новый ключ обложки статьи. Передайте null, чтобы удалить.",
    )


class ArticleOut(BaseModel):
    """Схема ответа с данными статьи блога."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Уникальный идентификатор статьи.")
    title: str = Field(description="Заголовок статьи.")
    text: str = Field(description="Текст статьи.")
    image_key: str | None = Field(
        default=None,
        description="Ключ обложки статьи в файловом хранилище, может отсутствовать.",
    )
    created_at: datetime = Field(description="Дата создания записи.")
    updated_at: datetime = Field(description="Дата последнего обновления записи.")
    category: CategoryOut = Field(description="Категория, к которой привязана статья.")


class PageMeta(BaseModel):
    """Информация о пагинации списка статей."""

    page_number: int = Field(description="Номер текущей страницы (начинается с 1).")
    page_size: int = Field(description="Количество элементов на странице.")
    total: int = Field(description="Общее количество элементов.")
    total_pages: int = Field(description="Количество страниц с учётом page_size.")


class ArticleListOut(BaseModel):
    """Ответ со списком статей и метаданными пагинации."""

    items: list[ArticleOut] = Field(description="Список статей текущей страницы.")
    meta: PageMeta = Field(description="Метаданные пагинации.")

    @staticmethod
    def build(
        items: list[ArticleOut], *, page_number: int, page_size: int, total: int
    ) -> ArticleListOut:
        """Удобный конструктор, рассчитывающий количество страниц."""
        return ArticleListOut(
            items=items,
            meta=PageMeta(
                page_number=page_number,
                page_size=page_size,
                total=total,
                total_pages=max(1, ceil(total / page_size)) if page_size else 1,
            ),
        )
