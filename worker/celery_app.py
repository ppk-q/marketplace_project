from __future__ import annotations

import os
from typing import Final

from celery import Celery

DEFAULT_RABBITMQ_HOST: Final[str] = "localhost"
DEFAULT_RABBITMQ_PORT: Final[str] = "5672"
DEFAULT_RABBITMQ_USER: Final[str] = "guest"
DEFAULT_RABBITMQ_PASSWORD: Final[str] = "guest"


def _broker_url() -> str:
    """Собирает AMQP URL из переменных окружения."""

    host = os.getenv("RABBITMQ_HOST", DEFAULT_RABBITMQ_HOST).strip()
    port = os.getenv("RABBITMQ_PORT", DEFAULT_RABBITMQ_PORT).strip()
    user = os.getenv("RABBITMQ_USER", DEFAULT_RABBITMQ_USER).strip()
    password = os.getenv("RABBITMQ_PASSWORD", DEFAULT_RABBITMQ_PASSWORD).strip()

    if not host:
        host = DEFAULT_RABBITMQ_HOST
    if not port:
        port = DEFAULT_RABBITMQ_PORT
    if not user:
        user = DEFAULT_RABBITMQ_USER
    if not password:
        password = DEFAULT_RABBITMQ_PASSWORD

    return f"amqp://{user}:{password}@{host}:{port}//"


def _create_celery_app() -> Celery:
    """Создаёт и настраивает Celery-приложение воркера."""

    application = Celery("worker", broker=_broker_url())
    application.autodiscover_tasks(["worker"])
    return application


celery_app = _create_celery_app()
