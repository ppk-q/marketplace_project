from __future__ import annotations

from typing import NoReturn

from fastapi import HTTPException

from app.core.service_errors import ServiceError


def raise_http_exception_from_service_error(err: ServiceError) -> NoReturn:
    """Преобразует `ServiceError` в `HTTPException` API-слоя."""

    raise HTTPException(status_code=err.status_code, detail=err.detail) from err
