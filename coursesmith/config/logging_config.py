import logging
import sys
from typing import Literal

import structlog
from structlog.contextvars import merge_contextvars
from structlog.dev import ConsoleRenderer
from structlog.processors import JSONRenderer, TimeStamper, format_exc_info
from structlog.stdlib import BoundLogger, LoggerFactory, ProcessorFormatter, add_log_level
from structlog.typing import Processor

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def configure_logging(json_logs: bool = True, log_level: LogLevel = "INFO") -> None:
    shared_processors: list[Processor] = [
        merge_contextvars,
        add_log_level,
        TimeStamper(fmt="iso"),
        format_exc_info,
    ]

    renderer = JSONRenderer() if json_logs else ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[*shared_processors, ProcessorFormatter.wrap_for_formatter],
        logger_factory=LoggerFactory(),
        wrapper_class=BoundLogger,
        cache_logger_on_first_use=True,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        ProcessorFormatter(processor=renderer, foreign_pre_chain=shared_processors)
    )

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(log_level)

    for name in ("LiteLLM", "LiteLLM Router", "LiteLLM Proxy"):
        noisy = logging.getLogger(name)
        noisy.handlers.clear()
        noisy.propagate = True
