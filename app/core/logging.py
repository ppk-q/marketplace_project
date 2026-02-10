from __future__ import annotations

import logging
from typing import Final

DEFAULT_LOG_LEVEL: Final[str] = "INFO"
DEFAULT_LOG_FORMAT: Final[str] = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def setup_logging(*, level: str = DEFAULT_LOG_LEVEL) -> None:
    """Инициализирует базовую конфигурацию логирования один раз."""

    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    logging.basicConfig(level=level, format=DEFAULT_LOG_FORMAT)
