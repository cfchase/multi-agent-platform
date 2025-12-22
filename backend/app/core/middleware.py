"""
Middleware components for the backend.

This module provides middleware for request/response logging,
error tracking, and other cross-cutting concerns.
"""

import logging
import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log HTTP requests and responses.

    Logs:
    - Request method, path, and query parameters
    - Response status code
    - Request processing duration
    - Client IP address (if available)

    Usage:
        app.add_middleware(RequestLoggingMiddleware)
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process the request and log details.

        Args:
            request: The incoming HTTP request
            call_next: The next middleware or route handler

        Returns:
            HTTP response
        """
        # Start timing
        start_time = time.time()

        # Get client info
        client_host = request.client.host if request.client else "unknown"

        # Log incoming request
        logger.info(
            f"Request started: {request.method} {request.url.path} "
            f"from {client_host}"
        )

        # Log query parameters if present (at debug level for verbosity)
        if request.url.query:
            logger.debug(f"Query params: {request.url.query}")

        try:
            # Process request
            response = await call_next(request)

            # Calculate duration
            duration = time.time() - start_time

            # Log response
            logger.info(
                f"Request completed: {request.method} {request.url.path} "
                f"status={response.status_code} duration={duration:.3f}s"
            )

            # Log slow requests as warnings
            if duration > 5.0:  # Requests taking more than 5 seconds
                logger.warning(
                    f"Slow request detected: {request.method} {request.url.path} "
                    f"took {duration:.3f}s"
                )

            return response

        except Exception as e:
            # Calculate duration even for errors
            duration = time.time() - start_time

            # Log error
            logger.error(
                f"Request failed: {request.method} {request.url.path} "
                f"error={type(e).__name__} duration={duration:.3f}s",
                exc_info=True,
            )

            # Re-raise to let FastAPI's error handlers deal with it
            raise
