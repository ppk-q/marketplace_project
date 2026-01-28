# worker/celery_app.py
import os

from celery import Celery


def _broker_url() -> str:
    """
    Собираем AMQP URL из env.
    В docker-compose мы задаём RABBITMQ_HOST=rabbitmq и RABBITMQ_PORT=5672.
    """
    host = os.getenv("RABBITMQ_HOST", "localhost")
    port = os.getenv("RABBITMQ_PORT", "5672")
    user = os.getenv("RABBITMQ_USER", "guest")
    password = os.getenv("RABBITMQ_PASSWORD", "guest")

    # Стандартный формат для RabbitMQ (AMQP)
    return f"amqp://{user}:{password}@{host}:{port}//"


# ВАЖНО: объект должен называться celery_app
celery_app = Celery(
    "worker",
    broker=_broker_url(),
)

# Автопоиск задач в модуле worker.tasks
celery_app.autodiscover_tasks(["worker"])
