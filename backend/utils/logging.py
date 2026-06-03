"""
AIClipper Structured Logging Module

Provides rotating file handlers, JSON formatting for machine parsing,
colorized console output, and performance timing decorators.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import sys
import time
from functools import wraps
from pathlib import Path
from typing import Any, Callable

from backend.utils.config import get_settings


# ---------------------------------------------------------------------------
# Custom JSON Formatter
# ---------------------------------------------------------------------------

class JSONFormatter(logging.Formatter):
    """Output log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info and record.exc_info[1]:
            log_data["exception"] = self.formatException(record.exc_info)
        # Include any extra fields
        for key in ("video_id", "clip_id", "job_id", "step", "duration_ms"):
            if hasattr(record, key):
                log_data[key] = getattr(record, key)
        return json.dumps(log_data, default=str)


# ---------------------------------------------------------------------------
# Colorized Console Formatter
# ---------------------------------------------------------------------------

class ColorFormatter(logging.Formatter):
    """Colorized console output for development."""

    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[41m",  # Red background
    }
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        level = f"{color}{record.levelname:8s}{self.RESET}"
        name = f"{self.DIM}{record.name}{self.RESET}"
        message = record.getMessage()
        timestamp = self.formatTime(record, "%H:%M:%S")
        formatted = f"{self.DIM}{timestamp}{self.RESET} {level} {name} → {message}"
        if record.exc_info and record.exc_info[1]:
            formatted += f"\n{self.formatException(record.exc_info)}"
        return formatted


# ---------------------------------------------------------------------------
# Setup Functions
# ---------------------------------------------------------------------------

def _create_rotating_handler(
    log_path: Path,
    formatter: logging.Formatter,
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5,
    level: int = logging.DEBUG,
) -> logging.handlers.RotatingFileHandler:
    """Create a rotating file handler with the given formatter."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        str(log_path),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.setLevel(level)
    handler.setFormatter(formatter)
    return handler


def setup_logging(log_dir: Path | None = None) -> None:
    """
    Configure the application logging system.

    Creates separate log files for:
    - processing.log  — Pipeline processing events
    - errors.log      — ERROR and above only
    - uploads.log     — Upload-related events
    - performance.log — Performance metrics and timing
    - app.log         — All application logs
    """
    if log_dir is None:
        settings = get_settings()
        log_dir = settings.log_dir

    log_dir.mkdir(parents=True, exist_ok=True)
    json_fmt = JSONFormatter()

    # Root logger
    root = logging.getLogger("aiclipper")
    root.setLevel(logging.DEBUG)
    root.handlers.clear()

    # Console handler (colorized)
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(ColorFormatter())
    root.addHandler(console)

    # App log (all levels, JSON)
    root.addHandler(_create_rotating_handler(log_dir / "app.log", json_fmt))

    # Error log (ERROR+)
    root.addHandler(
        _create_rotating_handler(log_dir / "errors.log", json_fmt, level=logging.ERROR)
    )

    # Processing log
    proc_logger = logging.getLogger("aiclipper.processing")
    proc_logger.addHandler(_create_rotating_handler(log_dir / "processing.log", json_fmt))

    # Upload log
    upload_logger = logging.getLogger("aiclipper.upload")
    upload_logger.addHandler(_create_rotating_handler(log_dir / "uploads.log", json_fmt))

    # Performance log
    perf_logger = logging.getLogger("aiclipper.performance")
    perf_logger.addHandler(_create_rotating_handler(log_dir / "performance.log", json_fmt))


def get_logger(name: str) -> logging.Logger:
    """Get a namespaced logger under the aiclipper hierarchy."""
    return logging.getLogger(f"aiclipper.{name}")


# ---------------------------------------------------------------------------
# Performance Timing Decorator
# ---------------------------------------------------------------------------

def timed(func: Callable | None = None, *, logger_name: str = "performance") -> Callable:
    """
    Decorator that logs execution time of a function.

    Usage:
        @timed
        def my_func(): ...

        @timed(logger_name="processing")
        def my_func(): ...
    """

    def decorator(fn: Callable) -> Callable:
        log = get_logger(logger_name)

        @wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            try:
                result = fn(*args, **kwargs)
                elapsed_ms = (time.perf_counter() - start) * 1000
                log.info(
                    f"{fn.__qualname__} completed in {elapsed_ms:.1f}ms",
                    extra={"duration_ms": round(elapsed_ms, 1), "step": fn.__name__},
                )
                return result
            except Exception:
                elapsed_ms = (time.perf_counter() - start) * 1000
                log.error(
                    f"{fn.__qualname__} failed after {elapsed_ms:.1f}ms",
                    extra={"duration_ms": round(elapsed_ms, 1), "step": fn.__name__},
                    exc_info=True,
                )
                raise

        @wraps(fn)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            try:
                result = await fn(*args, **kwargs)
                elapsed_ms = (time.perf_counter() - start) * 1000
                log.info(
                    f"{fn.__qualname__} completed in {elapsed_ms:.1f}ms",
                    extra={"duration_ms": round(elapsed_ms, 1), "step": fn.__name__},
                )
                return result
            except Exception:
                elapsed_ms = (time.perf_counter() - start) * 1000
                log.error(
                    f"{fn.__qualname__} failed after {elapsed_ms:.1f}ms",
                    extra={"duration_ms": round(elapsed_ms, 1), "step": fn.__name__},
                    exc_info=True,
                )
                raise

        import asyncio
        if asyncio.iscoroutinefunction(fn):
            return async_wrapper
        return sync_wrapper

    if func is not None:
        return decorator(func)
    return decorator
