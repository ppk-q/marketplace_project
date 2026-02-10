from __future__ import annotations

import re
from pathlib import PurePosixPath

from app.constants_media import (
    IMAGE_KEY_MAX_LENGTH,
    MEDIA_ALLOWED_IMAGE_CONTENT_TYPES,
    MEDIA_ALLOWED_IMAGE_EXTENSIONS,
    MEDIA_DETAIL_CONTENT_TYPE_EXTENSION_MISMATCH,
    MEDIA_DETAIL_INVALID_CONTENT_TYPE,
    MEDIA_DETAIL_INVALID_FILE_EXTENSION,
    MEDIA_DETAIL_INVALID_FILE_SIZE,
    MEDIA_DETAIL_INVALID_IMAGE_KEY,
    MEDIA_IMAGE_CONTENT_TYPE_BY_EXTENSION,
    MEDIA_IMAGE_KEY_PREFIX,
    MEDIA_IMAGE_KEY_REGEX,
    MEDIA_MAX_IMAGE_SIZE_BYTES,
)

IMAGE_KEY_PATTERN = re.compile(MEDIA_IMAGE_KEY_REGEX)


def extract_extension(value: str) -> str | None:
    """Возвращает расширение файла без точки в нижнем регистре."""

    suffix = PurePosixPath(value.strip()).suffix.lower()
    if not suffix:
        return None
    return suffix.lstrip(".")


def validate_upload_payload(file_name: str, content_type: str, file_size: int) -> str:
    """Проверяет параметры запроса на presign-upload и возвращает расширение."""

    extension = extract_extension(file_name)
    if extension is None or extension not in MEDIA_ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError(MEDIA_DETAIL_INVALID_FILE_EXTENSION)

    if content_type not in MEDIA_ALLOWED_IMAGE_CONTENT_TYPES:
        raise ValueError(MEDIA_DETAIL_INVALID_CONTENT_TYPE)

    expected_content_type = MEDIA_IMAGE_CONTENT_TYPE_BY_EXTENSION.get(extension)
    if expected_content_type != content_type:
        raise ValueError(MEDIA_DETAIL_CONTENT_TYPE_EXTENSION_MISMATCH)

    if file_size <= 0 or file_size > MEDIA_MAX_IMAGE_SIZE_BYTES:
        raise ValueError(MEDIA_DETAIL_INVALID_FILE_SIZE)

    return extension


def validate_image_key(value: str) -> str:
    """Проверяет формат `image_key` для статей и presign-download."""

    image_key = value.strip()
    if not image_key or len(image_key) > IMAGE_KEY_MAX_LENGTH:
        raise ValueError(MEDIA_DETAIL_INVALID_IMAGE_KEY)

    if not image_key.startswith(MEDIA_IMAGE_KEY_PREFIX):
        raise ValueError(MEDIA_DETAIL_INVALID_IMAGE_KEY)

    if not IMAGE_KEY_PATTERN.fullmatch(image_key):
        raise ValueError(MEDIA_DETAIL_INVALID_IMAGE_KEY)

    path_parts = PurePosixPath(image_key).parts
    if any(part in {"..", "."} for part in path_parts):
        raise ValueError(MEDIA_DETAIL_INVALID_IMAGE_KEY)

    extension = extract_extension(image_key)
    if extension is None or extension not in MEDIA_ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError(MEDIA_DETAIL_INVALID_IMAGE_KEY)

    return image_key
