"""
Factory functions for Langflow client creation.

This module provides factory functions that automatically select between
the real Langflow client and mock client based on configuration.

Usage:
    from app.services.langflow import get_langflow_client

    # Returns LangflowClient if LANGFLOW_URL is configured (not "mock"),
    # otherwise returns MockLangflowClient
    client = get_langflow_client()

Environment Variables:
    LANGFLOW_URL: Langflow server URL. Set to "mock" for testing.
    LANGFLOW_API_KEY: API key for authentication (loaded from K8s secret)
    LANGFLOW_ID: Langflow project ID (for Langflow Cloud)
    LANGFLOW_DEFAULT_FLOW: Default flow name to execute
"""

import logging

from app.core.config import settings
from app.services.protocols import LangflowClientProtocol

from .client import LangflowClient
from .mock_client import MockLangflowClient


logger = logging.getLogger(__name__)


# Special value to explicitly enable mock Langflow client
MOCK_LANGFLOW_URL = "mock"


def is_mock_langflow_enabled() -> bool:
    """
    Check if mock Langflow mode is explicitly enabled.

    Mock mode is enabled when LANGFLOW_URL is set to the special value "mock".

    Returns:
        True if mock Langflow is enabled, False otherwise
    """
    return settings.LANGFLOW_URL and settings.LANGFLOW_URL.lower() == MOCK_LANGFLOW_URL


def is_langflow_configured() -> bool:
    """
    Check if Langflow is configured (real or mock).

    Returns:
        True if Langflow is configured, False otherwise
    """
    if not settings.LANGFLOW_URL:
        return False

    # Mock mode is considered "configured"
    if is_mock_langflow_enabled():
        return True

    # Real mode just requires URL (flow selected via UI)
    return True


def get_langflow_client() -> LangflowClientProtocol:
    """
    Factory function to get a Langflow client instance.

    Automatically selects between real and mock client based on configuration:
    - If LANGFLOW_URL is "mock": Returns MockLangflowClient (explicit mock mode)
    - If LANGFLOW_URL is set: Returns real LangflowClient
    - Otherwise: Returns MockLangflowClient with warning

    The factory reads configuration from environment variables, which can be
    populated from Kubernetes secrets for production deployments:

        LANGFLOW_URL: Base URL or "mock" for testing
        LANGFLOW_API_KEY: Bearer token (from K8s secret)
        LANGFLOW_ID: Project ID for Langflow Cloud
        LANGFLOW_DEFAULT_FLOW: Optional default flow name

    Returns:
        A Langflow client implementing LangflowClientProtocol

    Example:
        # Mock mode (LANGFLOW_URL=mock):
        client = get_langflow_client()  # Returns MockLangflowClient

        # Production (real LANGFLOW_URL):
        client = get_langflow_client()  # Returns LangflowClient
    """
    if is_mock_langflow_enabled():
        logger.info("Using mock Langflow client (LANGFLOW_URL=mock)")
        return MockLangflowClient()

    if settings.LANGFLOW_URL:
        logger.info(f"Using real Langflow client (URL: {settings.LANGFLOW_URL})")
        return LangflowClient()

    # In production/staging, fail explicitly rather than silently using mock
    if settings.ENVIRONMENT in ("production", "staging"):
        raise RuntimeError(
            "Langflow not configured. LANGFLOW_URL must be set in production/staging. "
            "Set LANGFLOW_URL=mock to explicitly use mock client for testing."
        )

    # In local/development, fall back to mock with a warning
    logger.warning(
        "Langflow not configured. Set LANGFLOW_URL=mock for testing, "
        "or provide LANGFLOW_URL for production. "
        "Falling back to mock client in development."
    )
    return MockLangflowClient()
