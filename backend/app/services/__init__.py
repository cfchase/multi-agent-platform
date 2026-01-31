"""
Services package for external integrations.

This package provides clients for external services with automatic
mock/real selection based on configuration.

Usage:
    from app.services.langflow import get_langflow_client, LangflowError
    from app.services.protocols import LangflowClientProtocol

Available services:
    - langflow: AI chat via Langflow API
"""

from .protocols import LangflowClientProtocol
from .langflow import (
    LangflowClient,
    LangflowError,
    MockLangflowClient,
    get_langflow_client,
    is_langflow_configured,
)

__all__ = [
    # Protocols
    "LangflowClientProtocol",
    # Langflow
    "LangflowClient",
    "LangflowError",
    "MockLangflowClient",
    "get_langflow_client",
    "is_langflow_configured",
]
