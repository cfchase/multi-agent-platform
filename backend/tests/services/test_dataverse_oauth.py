"""
Tests for Dataverse dynamic OAuth client registration service.

Tests cover:
- Successful dynamic client registration
- Registration with correct request format
- Error handling for failed registration
- HTTP error responses

Test values from conftest.py:
- DATAVERSE_AUTH_URL=https://test.dataverse.org
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


class TestDataverseDynamicClientRegistration:
    """Tests for Dataverse dynamic OAuth client registration."""

    @pytest.mark.asyncio
    async def test_register_client_success(self):
        """register_dataverse_client returns client_id on successful registration."""
        from app.services.dataverse_oauth import register_dataverse_client

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "client_id": "dynamic-client-id-12345",
            "client_name": "Multi-Agent Platform",
            "redirect_uris": ["http://localhost:8000/callback"],
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            client_id = await register_dataverse_client(
                redirect_uri="http://localhost:8000/callback",
            )

            assert client_id == "dynamic-client-id-12345"

    @pytest.mark.asyncio
    async def test_register_client_sends_correct_request(self):
        """register_dataverse_client sends correct registration data."""
        from app.services.dataverse_oauth import register_dataverse_client

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "client_id": "test-client-id",
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            await register_dataverse_client(
                redirect_uri="http://localhost:8000/api/v1/integrations/oauth/callback/dataverse",
            )

            # Verify the POST was called with correct URL and data
            call_args = mock_instance.post.call_args
            url = call_args[0][0] if call_args[0] else call_args.kwargs.get("url")
            json_data = call_args.kwargs.get("json")

            # URL should be the Dataverse registration endpoint
            assert "test.dataverse.org/register" in url

            # Verify required registration fields
            assert json_data["client_name"] == "Multi-Agent Platform"
            assert "http://localhost:8000/api/v1/integrations/oauth/callback/dataverse" in json_data["redirect_uris"]
            assert "authorization_code" in json_data["grant_types"]
            assert "refresh_token" in json_data["grant_types"]
            assert "code" in json_data["response_types"]
            assert json_data["token_endpoint_auth_method"] == "none"
            assert json_data["application_type"] == "native"

    @pytest.mark.asyncio
    async def test_register_client_handles_200_response(self):
        """register_dataverse_client handles 200 status (some servers return 200 instead of 201)."""
        from app.services.dataverse_oauth import register_dataverse_client

        mock_response = MagicMock()
        mock_response.status_code = 200  # Some OAuth servers return 200
        mock_response.json.return_value = {
            "client_id": "client-from-200-response",
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            client_id = await register_dataverse_client(
                redirect_uri="http://localhost:8000/callback",
            )

            assert client_id == "client-from-200-response"

    @pytest.mark.asyncio
    async def test_register_client_error_response(self):
        """register_dataverse_client raises error on non-2xx response."""
        from app.services.dataverse_oauth import (
            register_dataverse_client,
            DataverseRegistrationError,
        )

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Invalid request"

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with pytest.raises(DataverseRegistrationError, match="400"):
                await register_dataverse_client(
                    redirect_uri="http://localhost:8000/callback",
                )

    @pytest.mark.asyncio
    async def test_register_client_missing_client_id_in_response(self):
        """register_dataverse_client raises error when response lacks client_id."""
        from app.services.dataverse_oauth import (
            register_dataverse_client,
            DataverseRegistrationError,
        )

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "client_name": "Multi-Agent Platform",
            # Missing client_id
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with pytest.raises(DataverseRegistrationError, match="client_id"):
                await register_dataverse_client(
                    redirect_uri="http://localhost:8000/callback",
                )

    @pytest.mark.asyncio
    async def test_register_client_uses_custom_auth_url(self):
        """register_dataverse_client uses provided auth_url parameter."""
        from app.services.dataverse_oauth import register_dataverse_client

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "client_id": "custom-server-client",
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            await register_dataverse_client(
                redirect_uri="http://localhost:8000/callback",
                auth_url="https://custom.dataverse.org/auth",
            )

            call_args = mock_instance.post.call_args
            url = call_args[0][0] if call_args[0] else call_args.kwargs.get("url")
            assert "custom.dataverse.org/auth/register" in url

    @pytest.mark.asyncio
    async def test_register_client_network_error(self):
        """register_dataverse_client handles network errors gracefully."""
        from app.services.dataverse_oauth import (
            register_dataverse_client,
            DataverseRegistrationError,
        )
        import httpx

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = httpx.ConnectError("Connection refused")
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with pytest.raises(DataverseRegistrationError, match="Connection"):
                await register_dataverse_client(
                    redirect_uri="http://localhost:8000/callback",
                )
