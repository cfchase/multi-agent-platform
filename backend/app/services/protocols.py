"""
Protocol definitions for external service clients.

This module defines Protocol classes (PEP 544) for external service integrations,
enabling type-safe dependency injection and easy mocking for tests.

Both real and mock implementations must satisfy these protocols.
"""

from typing import AsyncGenerator, Protocol, runtime_checkable


@runtime_checkable
class LangflowClientProtocol(Protocol):
    """
    Protocol defining the interface for Langflow clients.

    Both LangflowClient (real) and MockLangflowClient (mock) implement this protocol,
    allowing type-safe substitution via factory functions.

    Example:
        def get_langflow_client(settings: Settings) -> LangflowClientProtocol:
            if settings.LANGFLOW_URL == "mock":
                return MockLangflowClient()
            return LangflowClient(settings)
    """

    async def chat(
        self,
        message: str,
        session_id: str | None = None,
        tweaks: dict | None = None,
    ) -> str:
        """
        Send a chat message and get a response (non-streaming).

        Args:
            message: The user message to send
            session_id: Optional session ID for conversation continuity
            tweaks: Optional tweaks to modify flow behavior

        Returns:
            The assistant's response text

        Raises:
            LangflowError: If the API call fails
        """
        ...

    async def chat_stream(
        self,
        message: str,
        session_id: str | None = None,
        tweaks: dict | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Send a chat message and stream the response.

        Args:
            message: The user message to send
            session_id: Optional session ID for conversation continuity
            tweaks: Optional tweaks to modify flow behavior

        Yields:
            Chunks of the assistant's response text

        Raises:
            LangflowError: If the API call fails
        """
        ...
