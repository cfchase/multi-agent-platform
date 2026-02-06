"""
Tests for Integration API endpoints.

Test values are set in conftest.py:
- GOOGLE_CLIENT_ID=test-google-client-id
- GOOGLE_CLIENT_SECRET=test-google-client-secret
- DATAVERSE_AUTH_URL=https://test.dataverse.org

Note: Dataverse uses dynamic client registration (RFC 7591), so no static
DATAVERSE_CLIENT_ID or DATAVERSE_CLIENT_SECRET are needed.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models import User


class TestIntegrationsList:
    """Tests for GET /api/v1/integrations/"""

    def test_list_integrations_empty(self, client: TestClient, session: Session):
        """Returns empty list when user has no integrations."""
        # Create a user first
        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()

        response = client.get(
            "/api/v1/integrations/",
            headers={
                "X-Forwarded-Preferred-Username": "testuser",
                "X-Forwarded-Email": "test@example.com",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["integrations"] == []
        assert data["count"] == 0

    def test_list_integrations_with_data(self, client: TestClient, session: Session):
        """Returns list of user's integrations."""
        from app.crud.integration import create_or_update_integration

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        # Create an integration
        create_or_update_integration(
            session=session,
            user_id=user.id,
            service_name="google_drive",
            access_token="test-token",
            expires_in=3600,
        )

        response = client.get(
            "/api/v1/integrations/",
            headers={
                "X-Forwarded-Preferred-Username": "testuser",
                "X-Forwarded-Email": "test@example.com",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["integrations"][0]["service_name"] == "google_drive"
        # Should NOT expose tokens
        assert "access_token" not in data["integrations"][0]
        assert "access_token_encrypted" not in data["integrations"][0]


class TestIntegrationsStatus:
    """Tests for GET /api/v1/integrations/status"""

    def test_status_shows_missing_services(self, client: TestClient, session: Session):
        """Returns list of services that need connection."""
        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()

        response = client.get(
            "/api/v1/integrations/status",
            headers={
                "X-Forwarded-Preferred-Username": "testuser",
                "X-Forwarded-Email": "test@example.com",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "missing_services" in data
        assert "connected_services" in data
        # With no integrations, all supported services should be missing
        assert "google_drive" in data["missing_services"]
        assert "dataverse" in data["missing_services"]
        assert data["connected_services"] == []


class TestOAuthStart:
    """Tests for POST /api/v1/integrations/oauth/start/{service}"""

    def test_oauth_start_returns_redirect_url(self, client: TestClient, session: Session):
        """Returns authorization URL for OAuth flow."""
        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()

        response = client.post(
            "/api/v1/integrations/oauth/start/google_drive",
            headers={
                "X-Forwarded-Preferred-Username": "testuser",
                "X-Forwarded-Email": "test@example.com",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "authorization_url" in data
        assert "accounts.google.com" in data["authorization_url"]
        assert "client_id=test-google-client-id" in data["authorization_url"]  # From conftest.py

    def test_oauth_start_unknown_service(self, client: TestClient, session: Session):
        """Returns 400 for unknown service."""
        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()

        response = client.post(
            "/api/v1/integrations/oauth/start/unknown_service",
            headers={
                "X-Forwarded-Preferred-Username": "testuser",
                "X-Forwarded-Email": "test@example.com",
            },
        )

        assert response.status_code == 400
        assert "Unknown service" in response.json()["detail"]


class TestOAuthCallback:
    """Tests for GET /api/v1/integrations/oauth/callback/{service}

    Note: The callback endpoint is unauthenticated because it's called by
    the OAuth provider's redirect, not the user's authenticated browser.
    User identity comes from the state parameter stored during oauth/start.
    Callback redirects to frontend settings page with success/error params.
    """

    def test_oauth_callback_missing_code(self, client: TestClient):
        """Redirects to settings with error when authorization code is missing."""
        # No auth headers needed - callback is unauthenticated
        response = client.get(
            "/api/v1/integrations/oauth/callback/google_drive?state=test-state",
            follow_redirects=False,
        )

        assert response.status_code == 302
        location = response.headers["location"]
        assert "/settings/integrations" in location
        assert "error=" in location

    def test_oauth_callback_invalid_state(self, client: TestClient):
        """Redirects to settings with error when state is invalid."""
        # No auth headers needed - callback is unauthenticated
        response = client.get(
            "/api/v1/integrations/oauth/callback/google_drive?code=test-code&state=invalid-state",
            follow_redirects=False,
        )

        assert response.status_code == 302
        location = response.headers["location"]
        assert "/settings/integrations" in location
        assert "error=" in location

    def test_oauth_callback_success(self, client: TestClient, session: Session):
        """Successful callback stores tokens and redirects to settings."""
        from app.crud.oauth_state import store_oauth_state_db
        from app.crud.integration import get_user_integration

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        # Store a valid state in the database (bound to user during oauth/start)
        state = "valid-test-state"
        store_oauth_state_db(
            session=session,
            state=state,
            user_id=user.id,
            service_name="google_drive",
            redirect_uri="http://testserver/api/v1/integrations/oauth/callback/google_drive",
            code_verifier=None,
        )

        # Mock the token exchange
        with patch("app.api.routes.v1.integrations.exchange_code_for_tokens") as mock_exchange:
            mock_exchange.return_value = {
                "access_token": "new-access-token",
                "refresh_token": "new-refresh-token",
                "expires_in": 3600,
                "token_type": "Bearer",
                "scope": "drive.readonly",
            }

            # No auth headers needed - user identity comes from state
            response = client.get(
                f"/api/v1/integrations/oauth/callback/google_drive?code=auth-code&state={state}",
                follow_redirects=False,
            )

        assert response.status_code == 302
        location = response.headers["location"]
        assert "/settings/integrations" in location
        assert "connected=google_drive" in location

        # Verify integration was stored for the correct user (from state)
        integration = get_user_integration(session=session, user_id=user.id, service_name="google_drive")
        assert integration is not None


class TestDisconnectIntegration:
    """Tests for DELETE /api/v1/integrations/{service}"""

    def test_disconnect_removes_integration(self, client: TestClient, session: Session):
        """Disconnecting removes the integration."""
        from app.crud.integration import create_or_update_integration, get_user_integration

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        # Create integration first
        create_or_update_integration(
            session=session,
            user_id=user.id,
            service_name="google_drive",
            access_token="test-token",
        )

        # Verify it exists
        assert get_user_integration(session=session, user_id=user.id, service_name="google_drive") is not None

        response = client.delete(
            "/api/v1/integrations/google_drive",
            headers={
                "X-Forwarded-Preferred-Username": "testuser",
                "X-Forwarded-Email": "test@example.com",
            },
        )

        assert response.status_code == 200
        assert response.json()["message"] == "Integration disconnected"

        # Verify it's gone
        assert get_user_integration(session=session, user_id=user.id, service_name="google_drive") is None

    def test_disconnect_nonexistent_returns_404(self, client: TestClient, session: Session):
        """Disconnecting non-existent integration returns 404."""
        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()

        response = client.delete(
            "/api/v1/integrations/google_drive",
            headers={
                "X-Forwarded-Preferred-Username": "testuser",
                "X-Forwarded-Email": "test@example.com",
            },
        )

        assert response.status_code == 404


class TestSupportedServices:
    """Tests for GET /api/v1/integrations/services"""

    def test_get_supported_services(self, client: TestClient, session: Session):
        """Returns list of supported OAuth services."""
        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()

        response = client.get(
            "/api/v1/integrations/services",
            headers={
                "X-Forwarded-Preferred-Username": "testuser",
                "X-Forwarded-Email": "test@example.com",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "services" in data
        assert "google_drive" in data["services"]
        assert "dataverse" in data["services"]
