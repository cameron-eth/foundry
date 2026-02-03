"""Structured logging for Tool Foundry."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from src.infra.config import get_settings, is_production


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging in production."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add extra fields
        if hasattr(record, "tool_id"):
            log_data["tool_id"] = record.tool_id
        if hasattr(record, "org_id"):
            log_data["org_id"] = record.org_id
        if hasattr(record, "conversation_id"):
            log_data["conversation_id"] = record.conversation_id
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


class DevelopmentFormatter(logging.Formatter):
    """Human-readable formatter for development."""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Build extra context string
        extras = []
        if hasattr(record, "tool_id"):
            extras.append(f"tool={record.tool_id}")
        if hasattr(record, "org_id"):
            extras.append(f"org={record.org_id}")
        if hasattr(record, "duration_ms"):
            extras.append(f"duration={record.duration_ms}ms")

        extra_str = f" [{', '.join(extras)}]" if extras else ""

        return (
            f"{color}{timestamp} {record.levelname:8}{self.RESET} "
            f"{record.name}: {record.getMessage()}{extra_str}"
        )


def setup_logging(level: Optional[str] = None) -> None:
    """Configure logging for the application."""
    settings = get_settings()

    # Determine log level
    if level:
        log_level = getattr(logging, level.upper(), logging.INFO)
    elif is_production():
        log_level = logging.INFO
    else:
        log_level = logging.DEBUG

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Add appropriate handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)

    if is_production():
        handler.setFormatter(StructuredFormatter())
    else:
        handler.setFormatter(DevelopmentFormatter())

    root_logger.addHandler(handler)

    # Reduce noise from third-party loggers
    noisy_loggers = [
        "httpx",
        "httpcore",
        "modal",
        "hpack",
        "h2",
        "h11",
        "grpc",
        "urllib3",
        "asyncio",
    ]
    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a module."""
    return logging.getLogger(f"foundry.{name}")


class LogContext:
    """Context manager for adding extra fields to log records."""

    def __init__(
        self,
        logger: logging.Logger,
        tool_id: Optional[str] = None,
        org_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ):
        self.logger = logger
        self.extra = {}
        if tool_id:
            self.extra["tool_id"] = tool_id
        if org_id:
            self.extra["org_id"] = org_id
        if conversation_id:
            self.extra["conversation_id"] = conversation_id

    def debug(self, msg: str, **kwargs: Any) -> None:
        self.logger.debug(msg, extra={**self.extra, **kwargs})

    def info(self, msg: str, **kwargs: Any) -> None:
        self.logger.info(msg, extra={**self.extra, **kwargs})

    def warning(self, msg: str, **kwargs: Any) -> None:
        self.logger.warning(msg, extra={**self.extra, **kwargs})

    def error(self, msg: str, **kwargs: Any) -> None:
        self.logger.error(msg, extra={**self.extra, **kwargs})

    def exception(self, msg: str, **kwargs: Any) -> None:
        self.logger.exception(msg, extra={**self.extra, **kwargs})
