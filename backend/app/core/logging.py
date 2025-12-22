"""
Centralized logging configuration for the backend.

This module provides standardized logging setup that integrates with
FastAPI and Uvicorn, with environment-based log levels and consistent
formatting across all application modules.
"""

import logging
import sys

from app.core.config import settings


def setup_logging() -> None:
    """
    Configure application-wide logging.

    Uses Python's standard logging with appropriate levels based on environment.
    Integrates with Uvicorn's logging configuration.

    Log Levels by Environment:
    - local/development: DEBUG
    - staging/production: INFO

    Format: timestamp - module - level - message
    """
    # Define log level based on environment
    log_level_map = {
        "local": logging.DEBUG,
        "development": logging.DEBUG,
        "staging": logging.INFO,
        "production": logging.INFO,
    }

    log_level = log_level_map.get(settings.ENVIRONMENT, logging.INFO)

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,  # Override any existing configuration
    )

    # Set specific log levels for noisy third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # Uvicorn access logs - keep at INFO in production
    if settings.ENVIRONMENT in ("staging", "production"):
        logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    else:
        logging.getLogger("uvicorn.access").setLevel(logging.DEBUG)

    # Application logger
    app_logger = logging.getLogger("app")
    app_logger.setLevel(log_level)

    # Log the logging configuration
    app_logger.info(
        f"Logging configured for environment: {settings.ENVIRONMENT} "
        f"(level: {logging.getLevelName(log_level)})"
    )


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance

    Usage:
        logger = get_logger(__name__)
        logger.info("Something happened")
    """
    return logging.getLogger(name)
