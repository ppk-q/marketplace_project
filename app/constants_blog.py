from __future__ import annotations

from app.constants_api import API_V1_PREFIX

# Blog field constraints
TITLE_MIN_LENGTH = 1
TITLE_MAX_LENGTH = 255
TEXT_MIN_LENGTH = 1
PAGE_DEFAULT = 1
PAGE_SIZE_DEFAULT = 20
PAGE_SIZE_MIN = 1
PAGE_SIZE_MAX = 50
SEARCH_MIN_LENGTH = 1

# Blog API routes
BLOG_ARTICLES_PATH = f"{API_V1_PREFIX}/articles"
BLOG_ARTICLE_DETAIL_PATH_PREFIX = f"{BLOG_ARTICLES_PATH}/"
BLOG_CATEGORIES_PATH = f"{API_V1_PREFIX}/categories"

# Blog messages
BLOG_DETAIL_CATEGORY_NOT_FOUND = "Category not found"
BLOG_DETAIL_ARTICLE_NOT_FOUND = "Article not found"
BLOG_DETAIL_CATEGORY_EXISTS = "Category with this title already exists"
BLOG_DETAIL_CREATE_ARTICLE_FAILED = "Failed to create article"
BLOG_DETAIL_UPDATE_ARTICLE_FAILED = "Failed to update article"
BLOG_DETAIL_DELETE_ARTICLE_FAILED = "Failed to delete article"
