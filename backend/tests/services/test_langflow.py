"""Tests for Langflow client and factory."""

import pytest
from unittest.mock import patch, MagicMock

from app.services.langflow import (
    LangflowClient,
    LangflowError,
    MockLangflowClient,
    get_langflow_client,
    is_langflow_configured,
)
from app.services.protocols import LangflowClientProtocol


class TestMockLangflowClient:
    """Tests for MockLangflowClient."""

    @pytest.mark.asyncio
    async def test_chat_returns_canned_response(self):
        """Test that chat returns a canned response."""
        client = MockLangflowClient(responses=["Test response"])
        response = await client.chat("Hello")
        assert response == "Test response"

    @pytest.mark.asyncio
    async def test_chat_cycles_through_responses(self):
        """Test that multiple calls cycle through responses."""
        client = MockLangflowClient(responses=["First", "Second", "Third"])

        assert await client.chat("1") == "First"
        assert await client.chat("2") == "Second"
        assert await client.chat("3") == "Third"
        assert await client.chat("4") == "First"  # Cycles back

    @pytest.mark.asyncio
    async def test_chat_stream_yields_chunks(self):
        """Test that chat_stream yields response in chunks."""
        client = MockLangflowClient(
            responses=["Hello World"],
            chunk_size=5,
            stream_delay=0.001,  # Fast for testing
        )

        chunks = []
        async for chunk in client.chat_stream("Test"):
            chunks.append(chunk)

        assert "".join(chunks) == "Hello World"
        assert len(chunks) == 3  # "Hello", " Worl", "d"

    @pytest.mark.asyncio
    async def test_chat_raises_error_when_simulating(self):
        """Test that error simulation works."""
        client = MockLangflowClient(simulate_error=True, error_message="Test error")

        with pytest.raises(LangflowError) as exc_info:
            await client.chat("Hello")

        assert "Test error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_chat_stream_raises_error_when_simulating(self):
        """Test that streaming error simulation works."""
        client = MockLangflowClient(simulate_error=True)

        with pytest.raises(LangflowError):
            async for _ in client.chat_stream("Hello"):
                pass

    @pytest.mark.asyncio
    async def test_call_history_records_calls(self):
        """Test that call history is recorded."""
        client = MockLangflowClient()

        await client.chat("Message 1", session_id="sess1")
        await client.chat("Message 2")

        history = client.get_call_history()
        assert len(history) == 2
        assert history[0]["message"] == "Message 1"
        assert history[0]["session_id"] == "sess1"
        assert history[1]["message"] == "Message 2"

    @pytest.mark.asyncio
    async def test_reset_clears_state(self):
        """Test that reset clears call history and response index."""
        client = MockLangflowClient(responses=["A", "B"])

        await client.chat("Test")

        client.reset()

        assert len(client.get_call_history()) == 0
        # Response index should be reset
        response = await client.chat("Test")
        assert response == "A"

    def test_implements_protocol(self):
        """Test that MockLangflowClient implements the protocol."""
        client = MockLangflowClient()
        assert isinstance(client, LangflowClientProtocol)


class TestLangflowClient:
    """Tests for the real LangflowClient (without network calls)."""

    def test_build_url_self_hosted(self):
        """Test URL building for self-hosted Langflow."""
        client = LangflowClient(
            base_url="http://langflow.example.com",
            flow_id="test-flow-123",
            langflow_id=None,
        )

        url = client._get_run_url(stream=False)
        assert url == "http://langflow.example.com/api/v1/run/test-flow-123"

        stream_url = client._get_run_url(stream=True)
        assert stream_url == "http://langflow.example.com/api/v1/run/test-flow-123?stream=true"

    def test_build_url_langflow_cloud(self):
        """Test URL building for Langflow Cloud."""
        client = LangflowClient(
            base_url="https://api.langflow.astra.datastax.com",
            flow_id="test-flow-123",
            langflow_id="my-project-id",
        )

        url = client._get_run_url(stream=False)
        assert url == "https://api.langflow.astra.datastax.com/lf/my-project-id/api/v1/run/test-flow-123"

    def test_headers_without_api_key(self):
        """Test that headers are set correctly without API key."""
        client = LangflowClient(
            base_url="http://localhost",
            flow_id="test",
            api_key=None,
        )

        assert "Content-Type" in client.headers
        assert "Authorization" not in client.headers

    def test_headers_with_api_key(self):
        """Test that headers include authorization with API key."""
        client = LangflowClient(
            base_url="http://localhost",
            flow_id="test",
            api_key="secret-key",
        )

        assert client.headers["Authorization"] == "Bearer secret-key"

    def test_implements_protocol(self):
        """Test that LangflowClient implements the protocol."""
        client = LangflowClient(base_url="http://localhost", flow_id="test")
        assert isinstance(client, LangflowClientProtocol)


class TestLangflowFactory:
    """Tests for the factory function."""

    def test_returns_mock_when_url_is_mock(self):
        """Test that mock client is returned when URL is 'mock'."""
        with patch("app.services.langflow.factory.settings") as mock_settings:
            mock_settings.LANGFLOW_URL = "mock"
            mock_settings.LANGFLOW_FLOW_ID = "test"

            client = get_langflow_client()
            assert isinstance(client, MockLangflowClient)

    def test_returns_mock_when_url_is_mock_uppercase(self):
        """Test that mock client is returned when URL is 'MOCK' (case insensitive)."""
        with patch("app.services.langflow.factory.settings") as mock_settings:
            mock_settings.LANGFLOW_URL = "MOCK"

            client = get_langflow_client()
            assert isinstance(client, MockLangflowClient)

    def test_returns_real_client_when_configured(self):
        """Test that real client is returned when properly configured."""
        with patch("app.services.langflow.factory.settings") as mock_settings:
            mock_settings.LANGFLOW_URL = "http://langflow.example.com"
            mock_settings.LANGFLOW_API_KEY = "secret"
            mock_settings.LANGFLOW_ID = None
            mock_settings.LANGFLOW_FLOW_ID = "flow-123"

            client = get_langflow_client()
            assert isinstance(client, LangflowClient)

    def test_returns_mock_when_not_configured(self):
        """Test that mock client is returned when not configured (fallback)."""
        with patch("app.services.langflow.factory.settings") as mock_settings:
            mock_settings.LANGFLOW_URL = None
            mock_settings.LANGFLOW_FLOW_ID = None

            client = get_langflow_client()
            assert isinstance(client, MockLangflowClient)

    def test_is_langflow_configured_mock(self):
        """Test is_langflow_configured returns True for mock."""
        with patch("app.services.langflow.factory.settings") as mock_settings:
            mock_settings.LANGFLOW_URL = "mock"
            mock_settings.LANGFLOW_FLOW_ID = None

            assert is_langflow_configured() is True

    def test_is_langflow_configured_real(self):
        """Test is_langflow_configured returns True when configured."""
        with patch("app.services.langflow.factory.settings") as mock_settings:
            mock_settings.LANGFLOW_URL = "http://langflow.example.com"
            mock_settings.LANGFLOW_FLOW_ID = "flow-123"

            assert is_langflow_configured() is True

    def test_is_langflow_configured_missing(self):
        """Test is_langflow_configured returns False when not configured."""
        with patch("app.services.langflow.factory.settings") as mock_settings:
            mock_settings.LANGFLOW_URL = None
            mock_settings.LANGFLOW_FLOW_ID = None

            assert is_langflow_configured() is False
