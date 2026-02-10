from __future__ import annotations

import logging

from worker.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="send_registration_email")
def send_registration_email(email: str, confirmation_link: str) -> None:
    """Заглушка отправки регистрационного письма."""

    logger.info(
        "Registration email sent to: %s. Confirm link: %s",
        email,
        confirmation_link,
    )
