from __future__ import annotations


class ServiceError(RuntimeError):
    """Базовая ошибка сервисного слоя с HTTP-метаданными для API-ответа."""

    def __init__(self, *, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
