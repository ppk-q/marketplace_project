from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator

from app.constants_media import (
    IMAGE_KEY_MAX_LENGTH,
    MEDIA_MAX_IMAGE_SIZE_BYTES,
)
from app.modules.media.validators import validate_image_key, validate_upload_payload


class PresignUploadIn(BaseModel):
    """Схема запроса на выдачу presigned PUT URL для загрузки изображения."""

    file_name: str = Field(min_length=3, max_length=255)
    content_type: str = Field(min_length=3, max_length=64)
    file_size: int = Field(gt=0, le=MEDIA_MAX_IMAGE_SIZE_BYTES)

    @model_validator(mode="after")
    def check_constraints(self) -> PresignUploadIn:
        validate_upload_payload(self.file_name, self.content_type, self.file_size)
        return self


class PresignUploadOut(BaseModel):
    """Ответ с presigned PUT URL и сгенерированным `image_key`."""

    upload_url: str
    image_key: str
    expires_in: int
    required_content_type: str


class PresignDownloadIn(BaseModel):
    """Схема запроса на выдачу presigned GET URL для чтения изображения."""

    image_key: str = Field(min_length=1, max_length=IMAGE_KEY_MAX_LENGTH)

    @field_validator("image_key")
    @classmethod
    def check_image_key(cls, value: str) -> str:
        return validate_image_key(value)


class PresignDownloadOut(BaseModel):
    """Ответ с presigned GET URL для чтения изображения."""

    download_url: str
    expires_in: int
