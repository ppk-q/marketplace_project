from __future__ import annotations

from app.constants_api import API_V1_PREFIX

IMAGE_KEY_MAX_LENGTH = 1024

# Media / S3
S3_DEFAULT_BUCKET_NAME = "blog-images"
S3_DEFAULT_REGION = "us-east-1"
S3_DEFAULT_PRESIGNED_TTL_SECONDS = 900
S3_MAX_PRESIGNED_TTL_SECONDS = 24 * 60 * 60
MEDIA_MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024
MEDIA_ALLOWED_IMAGE_EXTENSIONS = ("jpg", "jpeg", "png", "webp")
MEDIA_ALLOWED_IMAGE_CONTENT_TYPES = ("image/jpeg", "image/png", "image/webp")
MEDIA_IMAGE_CONTENT_TYPE_BY_EXTENSION = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
}
MEDIA_IMAGE_KEY_PREFIX = "articles/"
MEDIA_IMAGE_KEY_REGEX = r"^articles/[A-Za-z0-9][A-Za-z0-9/_\.-]*$"
MEDIA_TAG = "media"
MEDIA_PREFIX = "/media"
MEDIA_PRESIGN_UPLOAD_PATH = f"{API_V1_PREFIX}{MEDIA_PREFIX}/presign-upload"
MEDIA_PRESIGN_DOWNLOAD_PATH = f"{API_V1_PREFIX}{MEDIA_PREFIX}/presign-download"

# Media messages
MEDIA_DETAIL_INVALID_FILE_EXTENSION = "Unsupported image file extension"
MEDIA_DETAIL_INVALID_CONTENT_TYPE = "Unsupported image content type"
MEDIA_DETAIL_CONTENT_TYPE_EXTENSION_MISMATCH = (
    "Content type does not match file extension"
)
MEDIA_DETAIL_INVALID_FILE_SIZE = "Invalid image size"
MEDIA_DETAIL_INVALID_IMAGE_KEY = "Invalid image key"
MEDIA_DETAIL_STORAGE_UNAVAILABLE = "Storage service unavailable"
