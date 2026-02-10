from __future__ import annotations

from typing import Any
from uuid import uuid4

import boto3
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    NoCredentialsError,
    PartialCredentialsError,
)

from app.constants_media import MEDIA_DETAIL_STORAGE_UNAVAILABLE, MEDIA_IMAGE_KEY_PREFIX
from app.core.config import settings
from app.core.service_errors import ServiceError
from app.modules.media.schemas import (
    PresignDownloadIn,
    PresignDownloadOut,
    PresignUploadIn,
    PresignUploadOut,
)
from app.modules.media.validators import extract_extension

STORAGE_ERRORS = (
    BotoCoreError,
    ClientError,
    NoCredentialsError,
    PartialCredentialsError,
)


class MediaServiceError(ServiceError):
    """Ошибка сервисного слоя media."""


def _media_error(*, status_code: int, detail: str) -> MediaServiceError:
    """Создаёт сервисную ошибку media с кодом и текстом ответа."""

    return MediaServiceError(status_code=status_code, detail=detail)


def _storage_unavailable_error() -> MediaServiceError:
    """Возвращает ошибку недоступности S3/MinIO backend."""

    return _media_error(status_code=502, detail=MEDIA_DETAIL_STORAGE_UNAVAILABLE)


def build_s3_client() -> Any:
    """Создаёт S3-клиент для работы с MinIO/S3."""

    endpoint_url = settings.s3_endpoint_url or None
    access_key = settings.s3_access_key_id or None
    secret_key = settings.s3_secret_access_key or None
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=settings.s3_region_name,
        use_ssl=settings.s3_secure,
    )


def generate_presigned_upload_url(*, image_key: str, content_type: str) -> str:
    """Генерирует presigned PUT URL для загрузки объекта в S3/MinIO."""

    client = build_s3_client()
    return client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.s3_bucket_name,
            "Key": image_key,
            "ContentType": content_type,
        },
        ExpiresIn=settings.s3_presigned_ttl_seconds,
        HttpMethod="PUT",
    )


def generate_presigned_download_url(*, image_key: str) -> str:
    """Генерирует presigned GET URL для чтения объекта из S3/MinIO."""

    client = build_s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket_name, "Key": image_key},
        ExpiresIn=settings.s3_presigned_ttl_seconds,
        HttpMethod="GET",
    )


def build_image_key(file_name: str) -> str:
    """Генерирует безопасный ключ объекта для хранения изображения статьи."""

    extension = extract_extension(file_name)
    assert extension is not None
    return f"{MEDIA_IMAGE_KEY_PREFIX}{uuid4().hex}.{extension}"


def create_presign_upload(payload: PresignUploadIn) -> PresignUploadOut:
    """Готовит данные для загрузки изображения через presigned PUT URL."""

    image_key = build_image_key(payload.file_name)
    try:
        upload_url = generate_presigned_upload_url(
            image_key=image_key,
            content_type=payload.content_type,
        )
    except STORAGE_ERRORS as err:
        raise _storage_unavailable_error() from err

    return PresignUploadOut(
        upload_url=upload_url,
        image_key=image_key,
        expires_in=settings.s3_presigned_ttl_seconds,
        required_content_type=payload.content_type,
    )


def create_presign_download(payload: PresignDownloadIn) -> PresignDownloadOut:
    """Готовит данные для чтения изображения через presigned GET URL."""

    try:
        download_url = generate_presigned_download_url(image_key=payload.image_key)
    except STORAGE_ERRORS as err:
        raise _storage_unavailable_error() from err

    return PresignDownloadOut(
        download_url=download_url,
        expires_in=settings.s3_presigned_ttl_seconds,
    )
