"""Sentry 初始化"""

import logging

import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def init_sentry() -> None:
    if not settings.SENTRY_DSN:
        logger.info("Sentry DSN not configured, skipping initialization")
        return
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        traces_sample_rate=settings.SENTRY_SAMPLE_RATE,
        send_default_pii=False,
        integrations=[
            LoggingIntegration(
                level=logging.INFO,
                event_level=logging.ERROR,
            ),
        ],
    )
    logger.info("Sentry initialized")
