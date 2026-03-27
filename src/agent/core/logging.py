"""Structured JSON logging setup using structlog."""

from __future__ import annotations

import logging
import sys

import structlog

from agent.core.config import get_settings


def setup_logging() -> None:
    """Configure structlog for structured JSON logging.

    In development mode, uses colored console output.
    In production mode, uses JSON output.
    """
    settings = get_settings()

    # Shared processors for all environments
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if settings.is_development:
        # Pretty console output for local development
        renderer = structlog.dev.ConsoleRenderer(colors=True)
    else:
        # JSON output for production (Docker, log aggregators)
        renderer = structlog.processors.JSONRenderer()  # type: ignore[assignment]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging to use structlog formatting
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    # Quieten noisy third-party loggers
    for noisy in ("httpx", "httpcore", "asyncio", "celery.utils.dispatch"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a bound structlog logger."""
    return structlog.get_logger(name)
