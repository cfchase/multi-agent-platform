"""
Mock Langflow client for testing and development without real Langflow connection.

This module provides a mock implementation of the LangflowClientProtocol that:
- Returns configurable canned responses
- Simulates streaming with configurable delays
- Supports error simulation for testing error handling

The mock client enables full testing of the chat workflow without requiring
a real Langflow instance.
"""

import asyncio
import logging
from typing import AsyncGenerator

from .client import Flow, LangflowError


logger = logging.getLogger(__name__)


# Default mock responses for different scenarios
DEFAULT_RESPONSES = [
    "I'm a mock AI assistant. This is a simulated response for testing purposes.",
    "Here's another mock response to help you test the chat interface.",
    "This mock response demonstrates that the chat system is working correctly.",
]


class MockLangflowClient:
    """
    Mock Langflow client for testing without real Langflow connection.

    Simulates Langflow responses:
    - Returns canned responses from a configurable list
    - Supports streaming simulation with delays
    - Can simulate errors for testing error handling

    Usage:
        client = MockLangflowClient()
        response = await client.chat("Hello!")
        # response = "I'm a mock AI assistant..."

        # For testing errors
        client = MockLangflowClient(simulate_error=True)
        await client.chat("Hello!")  # Raises LangflowError

    Configuration:
        - responses: List of canned responses to cycle through
        - stream_delay: Delay between chunks when streaming (seconds)
        - chunk_size: Number of characters per chunk when streaming
        - simulate_error: If True, raises LangflowError on all calls
    """

    def __init__(
        self,
        responses: list[str] | None = None,
        stream_delay: float = 0.05,
        chunk_size: int = 10,
        simulate_error: bool = False,
        error_message: str = "Simulated Langflow error",
    ):
        """
        Initialize mock Langflow client.

        Args:
            responses: List of canned responses to return (cycles through)
            stream_delay: Delay between chunks when streaming (seconds)
            chunk_size: Number of characters per chunk when streaming
            simulate_error: If True, all calls raise LangflowError
            error_message: Error message to use when simulating errors
        """
        self.responses = responses or DEFAULT_RESPONSES
        self.stream_delay = stream_delay
        self.chunk_size = chunk_size
        self.simulate_error = simulate_error
        self.error_message = error_message
        self._response_index = 0
        self._call_history: list[dict] = []

        logger.info("[MOCK] MockLangflowClient initialized")

    def _get_next_response(self) -> str:
        """Get the next response from the list, cycling through."""
        response = self.responses[self._response_index % len(self.responses)]
        self._response_index += 1
        return response

    def _record_call(self, method: str, message: str, session_id: str | None) -> None:
        """Record a call for test verification."""
        self._call_history.append({
            "method": method,
            "message": message,
            "session_id": session_id,
        })

    async def list_flows(self) -> list[Flow]:
        """
        Return mock flows for testing.

        Returns:
            A list of mock Flow objects
        """
        logger.debug("[MOCK] list_flows called")

        if self.simulate_error:
            raise LangflowError(self.error_message, status_code=500)

        return [
            Flow(
                id="mock-flow-1",
                name="Mock Chat Flow",
                description="A mock flow for testing chat functionality",
            ),
            Flow(
                id="mock-flow-2",
                name="Mock Research Flow",
                description="A mock flow for testing research queries",
            ),
        ]

    async def chat(
        self,
        message: str,
        session_id: str | None = None,
        tweaks: dict | None = None,
        flow_id: str | None = None,
    ) -> str:
        """
        Return a mock response (non-streaming).

        Args:
            message: The user message (logged but not processed)
            session_id: Optional session ID (logged)
            tweaks: Optional tweaks (ignored)

        Returns:
            A canned response string

        Raises:
            LangflowError: If simulate_error is True
        """
        self._record_call("chat", message, session_id)
        logger.debug(f"[MOCK] chat called: message={message[:50]}..., session_id={session_id}")

        if self.simulate_error:
            raise LangflowError(self.error_message, status_code=500)

        # Small delay to simulate network latency
        await asyncio.sleep(0.1)

        response = self._get_next_response()
        logger.debug(f"[MOCK] Returning response: {response[:50]}...")
        return response

    async def chat_stream(
        self,
        message: str,
        session_id: str | None = None,
        tweaks: dict | None = None,
        flow_id: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream a mock response in chunks.

        Args:
            message: The user message (logged but not processed)
            session_id: Optional session ID (logged)
            tweaks: Optional tweaks (ignored)

        Yields:
            Chunks of the response string

        Raises:
            LangflowError: If simulate_error is True
        """
        self._record_call("chat_stream", message, session_id)
        logger.debug(f"[MOCK] chat_stream called: message={message[:50]}..., session_id={session_id}")

        if self.simulate_error:
            raise LangflowError(self.error_message, status_code=500)

        response = self._get_next_response()

        # Stream the response in chunks
        for i in range(0, len(response), self.chunk_size):
            chunk = response[i:i + self.chunk_size]
            await asyncio.sleep(self.stream_delay)
            yield chunk

        logger.debug(f"[MOCK] Finished streaming response: {response[:50]}...")

    # Test helper methods

    def get_call_history(self) -> list[dict]:
        """Get the history of calls made to this client (for test assertions)."""
        return self._call_history.copy()

    def reset(self) -> None:
        """Reset the client state (call history, response index)."""
        self._call_history.clear()
        self._response_index = 0
        logger.debug("[MOCK] Reset client state")

    def set_responses(self, responses: list[str]) -> None:
        """Set custom responses for testing."""
        self.responses = responses
        self._response_index = 0

    def set_error_mode(self, enabled: bool, message: str = "Simulated error") -> None:
        """Enable or disable error simulation."""
        self.simulate_error = enabled
        self.error_message = message
