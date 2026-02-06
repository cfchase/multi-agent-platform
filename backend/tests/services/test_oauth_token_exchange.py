"""
Tests for OAuth token exchange service.

Test values are set in conftest.py:
- GOOGLE_CLIENT_ID=test-google-client-id
- GOOGLE_CLIENT_SECRET=test-google-client-secret
- DATAVERSE_AUTH_URL=https://test.dataverse.org

Note: Dataverse uses dynamic client registration (RFC 7591), so no static
DATAVERSE_CLIENT_ID or DATAVERSE_CLIENT_SECRET are needed. The provider_client_id
is passed to the exchange function for Dataverse.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


class TestTokenExchange:
    """Tests for OAuth token exchange."""

    @pytest.mark.asyncio
    async def test_exchange_code_for_tokens_google(self):
        """exchange_code_for_tokens returns tokens from Google."""
        from app.services.oauth_token import exchange_code_for_tokens

        # Mock the httpx response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "google-access-token",
            "refresh_token": "google-refresh-token",
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "https://www.googleapis.com/auth/drive.readonly",
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            tokens = await exchange_code_for_tokens(
                service_name="google_drive",
                code="authorization-code",
                redirect_uri="http://localhost:8000/callback",
                code_verifier=None,
            )

            assert tokens["access_token"] == "google-access-token"
            assert tokens["refresh_token"] == "google-refresh-token"
            assert tokens["expires_in"] == 3600

    @pytest.mark.asyncio
    async def test_exchange_code_for_tokens_dataverse_with_pkce_and_dynamic_client(self):
        """exchange_code_for_tokens includes code_verifier and uses dynamic client_id for Dataverse."""
        from app.services.oauth_token import exchange_code_for_tokens

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "dataverse-access-token",
            "refresh_token": "dataverse-refresh-token",
            "expires_in": 7200,
            "token_type": "Bearer",
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            tokens = await exchange_code_for_tokens(
                service_name="dataverse",
                code="authorization-code",
                redirect_uri="http://localhost:8000/callback",
                code_verifier="test-code-verifier",
                provider_client_id="dynamic-client-id-12345",  # Dynamic client_id
            )

            # Verify code_verifier was included in the request
            call_args = mock_instance.post.call_args
            request_data = call_args.kwargs.get("data", {})
            assert "code_verifier" in request_data
            # Verify dynamic client_id was used
            assert request_data["client_id"] == "dynamic-client-id-12345"
            # Verify no client_secret (public client)
            assert "client_secret" not in request_data
            assert tokens["access_token"] == "dataverse-access-token"

    @pytest.mark.asyncio
    async def test_exchange_code_for_tokens_error_response(self):
        """exchange_code_for_tokens raises on error response."""
        from app.services.oauth_token import exchange_code_for_tokens, OAuthTokenError

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "error": "invalid_grant",
            "error_description": "Code has expired",
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with pytest.raises(OAuthTokenError, match="invalid_grant"):
                await exchange_code_for_tokens(
                    service_name="google_drive",
                    code="expired-code",
                    redirect_uri="http://localhost:8000/callback",
                    code_verifier=None,
                )

    @pytest.mark.asyncio
    async def test_exchange_code_unknown_service(self):
        """exchange_code_for_tokens raises for unknown service."""
        from app.services.oauth_token import exchange_code_for_tokens

        with pytest.raises(ValueError, match="Unknown service"):
            await exchange_code_for_tokens(
                service_name="unknown",
                code="code",
                redirect_uri="http://localhost:8000/callback",
                code_verifier=None,
            )


class TestTokenRefresh:
    """Tests for OAuth token refresh."""

    @pytest.mark.asyncio
    async def test_refresh_access_token_google(self):
        """refresh_access_token returns new tokens for Google."""
        from app.services.oauth_token import refresh_access_token

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new-access-token",
            "expires_in": 3600,
            "token_type": "Bearer",
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            tokens = await refresh_access_token(
                service_name="google_drive",
                refresh_token="old-refresh-token",
            )

            assert tokens["access_token"] == "new-access-token"
            assert tokens["expires_in"] == 3600

    @pytest.mark.asyncio
    async def test_refresh_access_token_preserves_refresh_token(self):
        """refresh_access_token preserves refresh token when not returned."""
        from app.services.oauth_token import refresh_access_token

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new-access-token",
            "expires_in": 3600,
            "token_type": "Bearer",
            # No refresh_token - Google only returns it on first auth
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            tokens = await refresh_access_token(
                service_name="google_drive",
                refresh_token="original-refresh-token",
            )

            # Should return original refresh token when not provided in response
            assert tokens.get("refresh_token") == "original-refresh-token"

    @pytest.mark.asyncio
    async def test_refresh_access_token_dataverse_with_dynamic_client(self):
        """refresh_access_token uses dynamic client_id for Dataverse (no client_secret)."""
        from app.services.oauth_token import refresh_access_token

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new-dataverse-access-token",
            "refresh_token": "new-dataverse-refresh-token",
            "expires_in": 7200,
            "token_type": "Bearer",
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            tokens = await refresh_access_token(
                service_name="dataverse",
                refresh_token="old-refresh-token",
                provider_client_id="dynamic-client-id-12345",  # From stored integration
            )

            # Verify dynamic client_id was used
            call_args = mock_instance.post.call_args
            request_data = call_args.kwargs.get("data", {})
            assert request_data["client_id"] == "dynamic-client-id-12345"
            # Verify no client_secret (public client)
            assert "client_secret" not in request_data
            assert tokens["access_token"] == "new-dataverse-access-token"


class TestNonJsonErrorResponses:
    """Tests for handling non-JSON error responses from OAuth providers."""

    @pytest.mark.asyncio
    async def test_exchange_code_handles_html_error_response(self):
        """exchange_code_for_tokens handles HTML error responses gracefully."""
        from app.services.oauth_token import exchange_code_for_tokens, OAuthTokenError
        import json

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "<html><body>Internal Server Error</body></html>"
        # Simulate json() raising an error when response is HTML
        mock_response.json.side_effect = json.JSONDecodeError("Expecting value", "", 0)

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with pytest.raises(OAuthTokenError) as exc_info:
                await exchange_code_for_tokens(
                    service_name="google_drive",
                    code="some-code",
                    redirect_uri="http://localhost:8000/callback",
                    code_verifier=None,
                )

            # Should contain status code and text in error
            assert "500" in str(exc_info.value) or "server_error" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_exchange_code_handles_empty_response(self):
        """exchange_code_for_tokens handles empty response body."""
        from app.services.oauth_token import exchange_code_for_tokens, OAuthTokenError
        import json

        mock_response = MagicMock()
        mock_response.status_code = 502
        mock_response.text = ""
        mock_response.json.side_effect = json.JSONDecodeError("Expecting value", "", 0)

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with pytest.raises(OAuthTokenError) as exc_info:
                await exchange_code_for_tokens(
                    service_name="google_drive",
                    code="some-code",
                    redirect_uri="http://localhost:8000/callback",
                    code_verifier=None,
                )

            # Should handle gracefully with status code info
            assert "502" in str(exc_info.value) or "server_error" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_refresh_token_handles_html_error_response(self):
        """refresh_access_token handles HTML error responses gracefully."""
        from app.services.oauth_token import refresh_access_token, OAuthTokenError
        import json

        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.text = "<html>Service Unavailable</html>"
        mock_response.json.side_effect = json.JSONDecodeError("Expecting value", "", 0)

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with pytest.raises(OAuthTokenError) as exc_info:
                await refresh_access_token(
                    service_name="google_drive",
                    refresh_token="some-token",
                )

            # Should contain status code info
            assert "503" in str(exc_info.value) or "server_error" in str(exc_info.value).lower()
