# worker/tasks.py
from worker.celery_app import celery_app


@celery_app.task(name="send_registration_email")
def send_registration_email(email: str) -> None:
    """
    Пока заглушка: имитируем отправку письма.
    На следующих шагах заменим на реальный SMTP/провайдера.
    """
    print(f"[EMAIL] Registration email sent to: {email}")
