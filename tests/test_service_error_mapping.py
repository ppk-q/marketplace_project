from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.core.http_errors import raise_http_exception_from_service_error
from app.core.service_errors import ServiceError


def test_service_error_stores_status_and_detail() -> None:
    error = ServiceError(status_code=409, detail="Conflict")

    assert error.status_code == 409
    assert error.detail == "Conflict"
    assert str(error) == "Conflict"


def test_raise_http_exception_from_service_error_preserves_status_and_detail() -> None:
    service_error = ServiceError(status_code=422, detail="Validation failed")

    with pytest.raises(HTTPException) as exc_info:
        raise_http_exception_from_service_error(service_error)

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "Validation failed"
    assert exc_info.value.__cause__ is service_error


def test_raise_http_exception_from_service_error_accepts_subclasses() -> None:
    class CustomServiceError(ServiceError):
        pass

    service_error = CustomServiceError(status_code=503, detail="Service unavailable")

    with pytest.raises(HTTPException) as exc_info:
        raise_http_exception_from_service_error(service_error)

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Service unavailable"
    assert exc_info.value.__cause__ is service_error
