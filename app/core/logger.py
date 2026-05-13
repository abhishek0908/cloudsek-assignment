import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict

from app.core.config import settings

def _add_service_info(_: Any, __: Any, event_dict: EventDict) -> EventDict:
    """Stamp every log line with the service name."""
    event_dict["service"] = "http-metadata-service"
    return event_dict


def configure_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    is_dev = settings.environment == "development"

    shared_processors = [
        structlog.contextvars.merge_contextvars,       # request-scoped fields (request_id, url)
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        _add_service_info,
        structlog.stdlib.add_logger_name,
    ]

    if is_dev:
        renderer = structlog.dev.ConsoleRenderer(colors=True)
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # Silence noisy third-party loggers
    for noisy in ("httpx", "motor", "pymongo"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str = __name__) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)