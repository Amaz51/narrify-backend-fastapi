# Logging Utility

# Configures structured logging for the entire application.
# Uses loguru for better formatting and rotation.

import sys
from pathlib import Path
from typing import Optional

from loguru import logger

from app.config import settings


def setup_logger(
    log_file: Optional[Path] = None,
    rotation: str = "100 MB",
    retention: str = "30 days",
    level: str = "INFO",
) -> None:
    
    # Setup application logger
    
    # Remove default logger
    logger.remove()

    # Console handler with colors
    logger.add(
        sys.stdout,
        format=settings.LOG_FORMAT,
        level=level,
        colorize=True,
        backtrace=True,
        diagnose=True,
    )

    # File handler (if specified)
    if log_file is None:
        log_file = settings.LOG_DIR / "app.log"

    logger.add(
        str(log_file),
        format=settings.LOG_FORMAT,
        level=level,
        rotation=rotation,
        retention=retention,
        compression="zip",
        backtrace=True,
        diagnose=True,
    )

    # Error log file (separate)
    error_log = settings.LOG_DIR / "error.log"
    logger.add(
        str(error_log),
        format=settings.LOG_FORMAT,
        level="ERROR",
        rotation=rotation,
        retention=retention,
        compression="zip",
        backtrace=True,
        diagnose=True,
    )

    logger.info(f"Logger initialized - Level: {level}")
    logger.info(f"Log file: {log_file}")


def get_logger(name: str):
    
    Get logger instance for a module

    return logger.bind(name=name)


# Initialize logger on import
setup_logger(level=settings.LOG_LEVEL)

__all__ = ["logger", "get_logger", "setup_logger"]
