from worker.celery_app import celery_app


@celery_app.task(name="send_registration_email")
def send_registration_email(email: str, confirmation_link: str) -> None:
    """
    Пока заглушка: имитируем отправку письма.
    """
    print(
        f"[EMAIL] Registration email sent to: {email}. "
        f"Confirm link: {confirmation_link}"
    )
