"""
Logging and request context utilities.

Provides:
- Logging helpers: log_info(), log_error(), log_warning(), log_debug(), log_exception()
- Request ID generation and context management (for tracing requests across logs)
- Deployment ID (src hash) injection into logs
- Sentry SDK initialization

Usage:
    from backend.utils import log_info, log_error, log_warning

    log_info("User logged in")
    log_warning("Rate limit approaching")
    log_error("Failed to process", exc_info=True)
"""

import logging
import secrets
from contextvars import ContextVar
from typing import Literal, Optional

import sentry_sdk


# Request ID prefixes for different protocols
REQUEST_ID_PREFIX_HTTP = "h"
REQUEST_ID_PREFIX_WS = "w"

# Context variable for request ID - async-safe, ~50ns overhead per access
_request_id: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


def generate_request_id(prefix: str = "") -> str:
    """
    Generate a short, unique request ID.

    Args:
        prefix: Optional prefix (e.g., "h" for HTTP, "w" for WebSocket)

    Uses secrets.token_hex(4) which produces 8 hex chars.
    ~200ns on modern hardware, 4 billion combinations - plenty for request tracing.
    """
    return f"{prefix}{secrets.token_hex(4)}"


def set_request_id(request_id: Optional[str] = None, *, prefix: str = "") -> str:
    """
    Set the request ID for the current context.

    Args:
        request_id: Explicit request ID to use (if None, generates a new one)
        prefix: Prefix for generated IDs (ignored if request_id is provided)

    Returns the request ID.
    """
    if request_id is None:
        request_id = generate_request_id(prefix)
    _request_id.set(request_id)
    return request_id


def get_request_id() -> Optional[str]:
    """Get the current request ID, or None if not set."""
    return _request_id.get()


def clear_request_id() -> None:
    """Clear the request ID for the current context."""
    _request_id.set(None)


class RequestContextFilter(logging.Filter):
    """
    Logging filter that adds deployment ID (src) and request ID (req) to log messages.

    Output format: [src:<deployment_id>] [req:<request_id>] <message>

    If request_id is not set, only src is shown: [src:<deployment_id>] <message>
    """

    def __init__(self, srchash: Optional[str] = None):
        super().__init__()
        self.srchash = srchash or "_local"

    def filter(self, record: logging.LogRecord) -> bool:
        msg = getattr(record, "msg", None)
        if not msg:
            return False

        request_id = get_request_id()
        if request_id:
            record.msg = f"[src:{self.srchash}] [req:{request_id}] {msg}"
        else:
            record.msg = f"[src:{self.srchash}] {msg}"
        return True


# Keep old name as alias for backwards compatibility
SrcHashLoggingFilter = RequestContextFilter


# =============================================================================
# Logging Helpers
# =============================================================================
# Simple logging functions that automatically include request context.
# Use these instead of creating loggers manually.
#
# Usage:
#   from backend.utils import log_info, log_error
#   log_info("User logged in", user_id=123)
#   log_error("Failed to process", exc_info=True)
# =============================================================================

_root_logger = logging.getLogger()


def log_debug(msg: str, *args, **kwargs) -> None:
    """Log at DEBUG level with automatic request context."""
    _root_logger.debug(msg, *args, **kwargs)


def log_info(msg: str, *args, **kwargs) -> None:
    """Log at INFO level with automatic request context."""
    _root_logger.info(msg, *args, **kwargs)


def log_warning(msg: str, *args, **kwargs) -> None:
    """Log at WARNING level with automatic request context."""
    _root_logger.warning(msg, *args, **kwargs)


def log_error(msg: str, *args, exc_info: bool = False, **kwargs) -> None:
    """
    Log at ERROR level with automatic request context.

    Args:
        msg: Log message
        exc_info: If True, include exception traceback (default: False)
    """
    _root_logger.error(msg, *args, exc_info=exc_info, **kwargs)


def log_exception(msg: str, *args, **kwargs) -> None:
    """
    Log at ERROR level with exception traceback.

    Equivalent to log_error(msg, exc_info=True).
    Use this in except blocks to automatically capture the exception.
    """
    _root_logger.exception(msg, *args, **kwargs)


def get_logger(name: str) -> logging.Logger:
    """
    Get a named logger for more granular control.

    Use this when you need a specific logger name for filtering/configuration.
    The returned logger still benefits from the request context filter.

    Args:
        name: Logger name (typically __name__ for module-level logging)

    Returns:
        A configured Logger instance
    """
    return logging.getLogger(name)


def init_sentry_sdk(dsn: str, send_default_pii: Optional[bool] = True, **kwargs) -> None:
    """Initialize Sentry SDK if DSN is provided."""
    if not dsn:
        return
    sentry_sdk.init(dsn=dsn, send_default_pii=send_default_pii, **kwargs)


def init_logging(
    deployment_id: str,
    log_file: Optional[str] = None,
    log_level: str = "INFO",
) -> dict:
    """
    Initialize logging configuration.

    Args:
        deployment_id: Deployment/source hash for identifying which deployment logs came from
        log_file: Optional file path to write logs to
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Django LOGGING configuration dict
    """
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "request_context": {
                "()": "backend.utils.RequestContextFilter",
                "srchash": deployment_id,
            },
        },
        "formatters": {
            "verbose": {
                "format": "%(asctime)s [%(levelname)-8s] (%(module)s.%(funcName)s) %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "level": log_level,
                "class": "logging.StreamHandler",
                "formatter": "verbose",
                "filters": ["request_context"],
            },
        },
        "loggers": {
            "django": {
                "handlers": [],
                "level": log_level,
                "propagate": True,
            },
        },
        "root": {
            "handlers": ["console"],
            "level": log_level,
        },
    }

    if log_file is not None:
        config["handlers"]["file"] = {
            "level": log_level,
            "class": "logging.FileHandler",
            "filename": log_file,
            "formatter": "verbose",
            "filters": ["request_context"],
        }
        config["root"]["handlers"].append("file")

    return config
