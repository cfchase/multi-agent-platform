"""
Tests for OAuth configuration service.

Test values are set in conftest.py:
- GOOGLE_CLIENT_ID=test-google-client-id
- GOOGLE_CLIENT_SECRET=test-google-client-secret
- DATAVERSE_AUTH_URL=https://test.dataverse.org

Note: Dataverse uses dynamic client registration (RFC 7591), so no static
DATAVERSE_CLIENT_ID or DATAVERSE_CLIENT_SECRET are needed.
"""

import pytest

from app.services.oauth_config import get_provider_config, get_supported_services


class TestOAuthProviderConfig:
    """Tests for OAuth provider configuration."""

    def test_get_google_provider_config(self):
        """get_provider_config returns Google OAuth configuration."""
        config = get_provider_config("google_drive")

        assert config is not None
        assert config.client_id == "test-google-client-id"
        assert config.client_secret == "test-google-client-secret"
        assert any("drive.readonly" in scope for scope in config.scopes)
        assert config.authorize_url == "https://accounts.google.com/o/oauth2/v2/auth"
        assert config.token_url == "https://oauth2.googleapis.com/token"

    def test_get_dataverse_provider_config(self):
        """get_provider_config returns Dataverse OAuth configuration with dynamic registration."""
        config = get_provider_config("dataverse")

        assert config is not None
        # Dataverse uses dynamic registration, so client_id is None until registered
        assert config.client_id is None
        assert config.client_secret is None
        assert config.uses_dynamic_registration is True
        assert config.is_public_client is True  # Dataverse uses public clients with PKCE
        assert config.use_pkce is True  # Dataverse requires PKCE
        assert "test.dataverse.org" in config.authorize_url

    def test_get_unknown_provider_returns_none(self):
        """get_provider_config returns None for unknown providers."""
        from app.services.oauth_config import get_provider_config

        config = get_provider_config("unknown_service")
        assert config is None

    def test_get_supported_services(self):
        """get_supported_services returns list of available OAuth services."""
        from app.services.oauth_config import get_supported_services

        services = get_supported_services()

        assert isinstance(services, list)
        assert "google_drive" in services
        assert "dataverse" in services

    def test_build_authorization_url_for_google(self):
        """build_authorization_url creates valid Google OAuth URL."""
        from app.services.oauth_config import build_authorization_url

        url, state = build_authorization_url(
            service_name="google_drive",
            redirect_uri="http://localhost:8000/api/v1/integrations/oauth/callback/google_drive",
            user_id=1,
        )

        assert "accounts.google.com" in url
        assert "client_id=test-google-client-id" in url  # From conftest.py
        assert "state=" in url
        assert "redirect_uri=" in url
        assert "access_type=offline" in url  # Google needs offline for refresh token
        assert state is not None

    def test_build_authorization_url_for_dataverse_requires_provider_client_id(self):
        """build_authorization_url raises error for Dataverse without provider_client_id."""
        from app.services.oauth_config import build_authorization_url

        # Dataverse uses dynamic registration, so provider_client_id is required
        with pytest.raises(ValueError, match="No client_id available"):
            build_authorization_url(
                service_name="dataverse",
                redirect_uri="http://localhost:8000/api/v1/integrations/oauth/callback/dataverse",
                user_id=1,
            )

    def test_build_authorization_url_unknown_service_raises(self):
        """build_authorization_url raises ValueError for unknown service."""
        from app.services.oauth_config import build_authorization_url

        with pytest.raises(ValueError, match="Unknown service"):
            build_authorization_url(
                service_name="unknown",
                redirect_uri="http://localhost:8000/callback",
                user_id=1,
            )


class TestOAuthStateManagement:
    """Tests for OAuth state management."""

    def test_generate_state_is_unique(self):
        """generate_oauth_state creates unique states."""
        from app.services.oauth_config import generate_oauth_state

        state1 = generate_oauth_state()
        state2 = generate_oauth_state()

        assert state1 != state2
        assert len(state1) >= 32  # Sufficient entropy

    def test_generate_pkce_pair(self):
        """generate_pkce_pair creates valid code verifier and challenge."""
        from app.services.oauth_config import generate_pkce_pair

        verifier, challenge = generate_pkce_pair()

        # Verifier should be 43-128 characters per RFC 7636
        assert 43 <= len(verifier) <= 128
        # Challenge is base64url encoded SHA256
        assert len(challenge) == 43  # Base64url of 32 bytes without padding

    def test_store_and_retrieve_oauth_state(self):
        """OAuth state can be stored and retrieved."""
        from app.services.oauth_config import store_oauth_state, get_oauth_state, OAuthStateData

        state = "test-state-123"
        state_data = OAuthStateData(
            service_name="google_drive",
            redirect_uri="http://localhost:8000/callback",
            user_id=1,
            code_verifier=None,
        )

        store_oauth_state(state, state_data)
        retrieved = get_oauth_state(state)

        assert retrieved is not None
        assert retrieved.service_name == "google_drive"
        assert retrieved.redirect_uri == "http://localhost:8000/callback"
        assert retrieved.user_id == 1

    def test_get_oauth_state_returns_none_for_unknown(self):
        """get_oauth_state returns None for unknown state."""
        from app.services.oauth_config import get_oauth_state

        result = get_oauth_state("nonexistent-state")
        assert result is None

    def test_consume_oauth_state_removes_state(self):
        """consume_oauth_state retrieves and removes state."""
        from app.services.oauth_config import (
            store_oauth_state,
            consume_oauth_state,
            get_oauth_state,
            OAuthStateData,
        )

        state = "test-state-to-consume"
        state_data = OAuthStateData(
            service_name="dataverse",
            redirect_uri="http://localhost:8000/callback",
            user_id=1,
            code_verifier="test-verifier",
        )

        store_oauth_state(state, state_data)

        # Consume should return and remove
        consumed = consume_oauth_state(state, user_id=1)
        assert consumed is not None
        assert consumed.code_verifier == "test-verifier"

        # Should be gone now
        assert get_oauth_state(state) is None

    def test_consume_oauth_state_validates_user_id(self):
        """consume_oauth_state rejects mismatched user_id."""
        from app.services.oauth_config import (
            store_oauth_state,
            consume_oauth_state,
            OAuthStateData,
        )

        state = "test-state-user-validation"
        state_data = OAuthStateData(
            service_name="google_drive",
            redirect_uri="http://localhost:8000/callback",
            user_id=1,
        )

        store_oauth_state(state, state_data)

        # Different user_id should fail
        consumed = consume_oauth_state(state, user_id=999)
        assert consumed is None

    def test_consume_oauth_state_rejects_expired(self):
        """consume_oauth_state rejects expired states."""
        from datetime import datetime, timedelta, timezone
        from app.services.oauth_config import (
            store_oauth_state,
            consume_oauth_state,
            OAuthStateData,
            STATE_EXPIRATION_MINUTES,
        )

        state = "test-state-expired"
        # Create state with old timestamp
        state_data = OAuthStateData(
            service_name="google_drive",
            redirect_uri="http://localhost:8000/callback",
            user_id=1,
            created_at=datetime.now(timezone.utc) - timedelta(minutes=STATE_EXPIRATION_MINUTES + 1),
        )

        store_oauth_state(state, state_data)

        # Should be rejected as expired
        consumed = consume_oauth_state(state, user_id=1)
        assert consumed is None
