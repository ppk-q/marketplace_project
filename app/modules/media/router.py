from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.constants_media import MEDIA_PREFIX, MEDIA_TAG
from app.core.http_errors import raise_http_exception_from_service_error
from app.modules.media.schemas import (
    PresignDownloadIn,
    PresignDownloadOut,
    PresignUploadIn,
    PresignUploadOut,
)
from app.modules.media.service import (
    MediaServiceError,
    create_presign_download,
    create_presign_upload,
)

router = APIRouter(prefix=MEDIA_PREFIX, tags=[MEDIA_TAG])
PresignDownloadDep = Annotated[PresignDownloadIn, Depends()]


@router.post("/presign-upload", response_model=PresignUploadOut)
async def presign_upload(payload: PresignUploadIn) -> PresignUploadOut:
    """Выдаёт presigned PUT URL и `image_key` для загрузки изображения статьи."""

    try:
        return create_presign_upload(payload)
    except MediaServiceError as err:
        raise_http_exception_from_service_error(err)


@router.get("/presign-download", response_model=PresignDownloadOut)
async def presign_download(payload: PresignDownloadDep) -> PresignDownloadOut:
    """Выдаёт presigned GET URL для чтения ранее загруженного изображения."""

    try:
        return create_presign_download(payload)
    except MediaServiceError as err:
        raise_http_exception_from_service_error(err)
