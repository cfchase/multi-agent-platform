"""
Langflow service client package.

This package provides a Langflow client with automatic mock/real selection:

    from app.services.langflow import get_langflow_client, LangflowError

    client = get_langflow_client()  # Auto-selects based on config
    response = await client.chat("Hello!")

Configuration (environment variables):
    LANGFLOW_URL: Server URL or "mock" for testing
    LANGFLOW_API_KEY: API key (from K8s secret in production)
    LANGFLOW_ID: Project ID (for Langflow Cloud)
    LANGFLOW_DEFAULT_FLOW: Default flow name (optional, can be selected in UI)
"""

from .client import Flow, LangflowClient, LangflowError
from .factory import get_langflow_client, is_langflow_configured, is_mock_langflow_enabled
from .mock_client import MockLangflowClient

__all__ = [
    "Flow",
    "LangflowClient",
    "LangflowError",
    "MockLangflowClient",
    "get_langflow_client",
    "is_langflow_configured",
    "is_mock_langflow_enabled",
]
