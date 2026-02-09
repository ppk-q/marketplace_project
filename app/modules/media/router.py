from __future__ import annotations

from typing import Annotated
from uuid import uuid4

import boto3
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    NoCredentialsError,
    PartialCredentialsError,
)
from fastapi import APIRouter, Depends, HTTPException, status

from app.constants import (
    MEDIA_DETAIL_STORAGE_UNAVAILABLE,
    MEDIA_IMAGE_KEY_PREFIX,
    MEDIA_PREFIX,
    MEDIA_TAG,
)
from app.core.config import settings
from app.modules.media.schemas import (
    PresignDownloadIn,
    PresignDownloadOut,
    PresignUploadIn,
    PresignUploadOut,
)
from app.modules.media.validators import extract_extension

router = APIRouter(prefix=MEDIA_PREFIX, tags=[MEDIA_TAG])
PresignDownloadDep = Annotated[PresignDownloadIn, Depends()]


def _build_s3_client():
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


def _generate_presigned_upload_url(*, image_key: str, content_type: str) -> str:
    """Генерирует presigned PUT URL для загрузки объекта в S3/MinIO."""

    client = _build_s3_client()
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


def _generate_presigned_download_url(*, image_key: str) -> str:
    """Генерирует presigned GET URL для чтения объекта из S3/MinIO."""

    client = _build_s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket_name, "Key": image_key},
        ExpiresIn=settings.s3_presigned_ttl_seconds,
        HttpMethod="GET",
    )


def _map_storage_error(err: Exception) -> HTTPException:
    """Преобразует ошибки S3/MinIO в безопасный HTTP-ответ без утечки деталей."""

    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=MEDIA_DETAIL_STORAGE_UNAVAILABLE,
    )


def _build_image_key(file_name: str) -> str:
    """Генерирует безопасный ключ объекта для хранения изображения статьи."""

    extension = extract_extension(file_name)
    assert extension
    return f"{MEDIA_IMAGE_KEY_PREFIX}{uuid4().hex}.{extension}"


@router.post("/presign-upload", response_model=PresignUploadOut)
async def presign_upload(payload: PresignUploadIn) -> PresignUploadOut:
    """Выдаёт presigned PUT URL и `image_key` для загрузки изображения статьи."""

    image_key = _build_image_key(payload.file_name)
    try:
        upload_url = _generate_presigned_upload_url(
            image_key=image_key,
            content_type=payload.content_type,
        )
    except (
        BotoCoreError,
        ClientError,
        NoCredentialsError,
        PartialCredentialsError,
    ) as err:
        raise _map_storage_error(err) from err

    return PresignUploadOut(
        upload_url=upload_url,
        image_key=image_key,
        expires_in=settings.s3_presigned_ttl_seconds,
        required_content_type=payload.content_type,
    )


@router.get("/presign-download", response_model=PresignDownloadOut)
async def presign_download(payload: PresignDownloadDep) -> PresignDownloadOut:
    """Выдаёт presigned GET URL для чтения ранее загруженного изображения."""

    try:
        download_url = _generate_presigned_download_url(image_key=payload.image_key)
    except (
        BotoCoreError,
        ClientError,
        NoCredentialsError,
        PartialCredentialsError,
    ) as err:
        raise _map_storage_error(err) from err

    return PresignDownloadOut(
        download_url=download_url,
        expires_in=settings.s3_presigned_ttl_seconds,
    )
