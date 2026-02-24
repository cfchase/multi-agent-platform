"""
Tests for token refresh service.

Following TDD: These tests are written BEFORE the implementation.
"""

import os
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock, AsyncMock
from sqlmodel import Session

from app.models import User


class TestGetValidToken:
    """Tests for get_valid_token function."""

    @pytest.mark.asyncio
    async def test_get_valid_token_returns_token_when_valid(self, session: Session):
        """Returns existing token when it's still valid."""
        os.environ["GOOGLE_CLIENT_ID"] = "test-client-id"
        os.environ["GOOGLE_CLIENT_SECRET"] = "test-client-secret"

        from app.crud.integration import create_or_update_integration
        from app.services.token_refresh import get_valid_token

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        # Create integration with valid token (expires in 1 hour)
        create_or_update_integration(
            session=session,
            user_id=user.id,
            service_name="google_drive",
            access_token="test-token-valid",  # noqa
            refresh_token="refresh-token",
            expires_in=3600,
        )

        token = await get_valid_token(
            session=session,
            user_id=user.id,
            service_name="google_drive",
        )

        assert token == "test-token-valid"

    @pytest.mark.asyncio
    async def test_get_valid_token_refreshes_expired(self, session: Session):
        """Refreshes and returns new token when expired."""
        os.environ["GOOGLE_CLIENT_ID"] = "test-client-id"
        os.environ["GOOGLE_CLIENT_SECRET"] = "test-client-secret"

        from app.crud.integration import create_or_update_integration, get_user_integration
        from app.services.token_refresh import get_valid_token

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        # Create integration with expired token
        integration = create_or_update_integration(
            session=session,
            user_id=user.id,
            service_name="google_drive",
            access_token="test-token-expired",  # noqa
            refresh_token="refresh-token",
            expires_in=3600,
        )

        # Manually set expires_at to past
        integration.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        session.add(integration)
        session.commit()

        # Mock the refresh
        with patch("app.services.token_refresh.refresh_access_token") as mock_refresh:
            mock_refresh.return_value = {
                "access_token": "test-token-new",
                "refresh_token": "new-refresh-token",
                "expires_in": 3600,
            }

            token = await get_valid_token(
                session=session,
                user_id=user.id,
                service_name="google_drive",
            )

            assert token == "test-token-new"
            mock_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_valid_token_refreshes_expiring_soon(self, session: Session):
        """Refreshes token when expiring within 5 minutes."""
        os.environ["GOOGLE_CLIENT_ID"] = "test-client-id"
        os.environ["GOOGLE_CLIENT_SECRET"] = "test-client-secret"

        from app.crud.integration import create_or_update_integration
        from app.services.token_refresh import get_valid_token

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        # Create integration expiring in 2 minutes
        integration = create_or_update_integration(
            session=session,
            user_id=user.id,
            service_name="google_drive",
            access_token="expiring-soon-token",  # noqa
            refresh_token="refresh-token",
            expires_in=120,  # 2 minutes
        )

        # Mock the refresh
        with patch("app.services.token_refresh.refresh_access_token") as mock_refresh:
            mock_refresh.return_value = {
                "access_token": "refreshed-token",
                "refresh_token": "new-refresh-token",
                "expires_in": 3600,
            }

            token = await get_valid_token(
                session=session,
                user_id=user.id,
                service_name="google_drive",
            )

            # Should have refreshed because expiring soon
            assert token == "refreshed-token"
            mock_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_valid_token_returns_none_on_decrypt_failure(self, session: Session):
        """Returns None when stored token cannot be decrypted (key mismatch)."""
        from cryptography.fernet import InvalidToken
        from app.crud.integration import create_or_update_integration
        from app.services.token_refresh import get_valid_token

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        create_or_update_integration(
            session=session,
            user_id=user.id,
            service_name="google_drive",
            access_token="valid-token",
            expires_in=3600,
        )

        with patch(
            "app.services.token_refresh.get_decrypted_tokens",
            side_effect=InvalidToken,
        ):
            token = await get_valid_token(
                session=session,
                user_id=user.id,
                service_name="google_drive",
            )

        assert token is None

    @pytest.mark.asyncio
    async def test_get_valid_token_returns_none_for_missing(self, session: Session):
        """Returns None when integration doesn't exist."""
        from app.services.token_refresh import get_valid_token

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        token = await get_valid_token(
            session=session,
            user_id=user.id,
            service_name="google_drive",
        )

        assert token is None

    @pytest.mark.asyncio
    async def test_get_valid_token_returns_none_when_no_refresh_token(self, session: Session):
        """Returns None when expired and no refresh token available."""
        os.environ["GOOGLE_CLIENT_ID"] = "test-client-id"
        os.environ["GOOGLE_CLIENT_SECRET"] = "test-client-secret"

        from app.crud.integration import create_or_update_integration
        from app.services.token_refresh import get_valid_token

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        # Create integration with expired token and no refresh token
        integration = create_or_update_integration(
            session=session,
            user_id=user.id,
            service_name="google_drive",
            access_token="expired-token",  # noqa
            refresh_token=None,  # No refresh token
            expires_in=3600,
        )

        # Manually expire it
        integration.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        session.add(integration)
        session.commit()

        token = await get_valid_token(
            session=session,
            user_id=user.id,
            service_name="google_drive",
        )

        assert token is None


class TestRefreshIntegrationToken:
    """Tests for refresh_integration_token function."""

    @pytest.mark.asyncio
    async def test_refresh_integration_token_updates_stored_token(self, session: Session):
        """Refreshing updates the stored token in database."""
        os.environ["GOOGLE_CLIENT_ID"] = "test-client-id"
        os.environ["GOOGLE_CLIENT_SECRET"] = "test-client-secret"

        from app.crud.integration import create_or_update_integration, get_user_integration, get_decrypted_tokens
        from app.services.token_refresh import refresh_integration_token

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        # Create integration
        create_or_update_integration(
            session=session,
            user_id=user.id,
            service_name="google_drive",
            access_token="test-token-old",  # noqa
            refresh_token="refresh-token",
            expires_in=3600,
        )

        # Mock the refresh
        with patch("app.services.token_refresh.refresh_access_token") as mock_refresh:
            mock_refresh.return_value = {
                "access_token": "test-token-new",
                "refresh_token": "new-refresh-token",
                "expires_in": 7200,
            }

            result = await refresh_integration_token(
                session=session,
                user_id=user.id,
                service_name="google_drive",
            )

            assert result is True

        # Verify stored token was updated
        integration = get_user_integration(session=session, user_id=user.id, service_name="google_drive")
        tokens = get_decrypted_tokens(integration)
        assert tokens["access_token"] == "test-token-new"
        assert tokens["refresh_token"] == "new-refresh-token"

    @pytest.mark.asyncio
    async def test_refresh_integration_token_handles_failure(self, session: Session):
        """Handles refresh failure gracefully."""
        os.environ["GOOGLE_CLIENT_ID"] = "test-client-id"
        os.environ["GOOGLE_CLIENT_SECRET"] = "test-client-secret"

        from app.crud.integration import create_or_update_integration
        from app.services.token_refresh import refresh_integration_token
        from app.services.oauth_token import OAuthTokenError

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        # Create integration
        create_or_update_integration(
            session=session,
            user_id=user.id,
            service_name="google_drive",
            access_token="old-token",  # noqa
            refresh_token="invalid-refresh-token",
            expires_in=3600,
        )

        # Mock refresh failure
        with patch("app.services.token_refresh.refresh_access_token") as mock_refresh:
            mock_refresh.side_effect = OAuthTokenError("invalid_grant", "Token has been revoked")

            result = await refresh_integration_token(
                session=session,
                user_id=user.id,
                service_name="google_drive",
            )

            assert result is False


class TestServiceSpecificRefreshThreshold:
    """Tests for service-specific refresh thresholds."""

    def test_get_refresh_threshold_google_drive(self):
        """Google Drive uses 5-minute threshold for short operations."""
        from app.services.token_refresh import get_refresh_threshold_minutes

        threshold = get_refresh_threshold_minutes("google_drive")
        assert threshold == 5

    def test_get_refresh_threshold_dataverse(self):
        """Dataverse uses 60-minute threshold for long-running tasks."""
        from app.services.token_refresh import get_refresh_threshold_minutes

        threshold = get_refresh_threshold_minutes("dataverse")
        assert threshold == 60

    def test_get_refresh_threshold_unknown_service(self):
        """Unknown services use default 5-minute threshold."""
        from app.services.token_refresh import get_refresh_threshold_minutes

        threshold = get_refresh_threshold_minutes("unknown_service")
        assert threshold == 5  # Default value

    @pytest.mark.asyncio
    async def test_dataverse_token_refreshes_with_longer_buffer(self, session: Session):
        """Dataverse token refreshes when expiring within 60 minutes."""
        # Dataverse uses dynamic registration, no static credentials needed
        # Only DATAVERSE_AUTH_URL is required (set in conftest.py)

        from app.crud.integration import create_or_update_integration
        from app.services.token_refresh import get_valid_token

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        # Create integration expiring in 30 minutes (within 60-min threshold)
        # Include provider_client_id for Dataverse dynamic client
        integration = create_or_update_integration(
            session=session,
            user_id=user.id,
            service_name="dataverse",
            access_token="expiring-soon-token",  # noqa
            refresh_token="refresh-token",
            expires_in=1800,  # 30 minutes
            provider_client_id="dynamic-client-id-12345",
        )

        # Mock the refresh
        with patch("app.services.token_refresh.refresh_access_token") as mock_refresh:
            mock_refresh.return_value = {
                "access_token": "refreshed-dataverse-token",
                "refresh_token": "new-refresh-token",
                "expires_in": 3600,
            }

            token = await get_valid_token(
                session=session,
                user_id=user.id,
                service_name="dataverse",
            )

            # Should have refreshed because expiring within 60-min threshold
            assert token == "refreshed-dataverse-token"
            mock_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_google_drive_does_not_refresh_at_30_minutes(self, session: Session):
        """Google Drive does NOT refresh when 30 minutes remaining (outside 5-min threshold)."""
        os.environ["GOOGLE_CLIENT_ID"] = "test-client-id"
        os.environ["GOOGLE_CLIENT_SECRET"] = "test-client-secret"

        from app.crud.integration import create_or_update_integration
        from app.services.token_refresh import get_valid_token

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        # Create integration expiring in 30 minutes (outside 5-min threshold)
        create_or_update_integration(
            session=session,
            user_id=user.id,
            service_name="google_drive",
            access_token="valid-for-30-mins",  # noqa
            refresh_token="refresh-token",
            expires_in=1800,  # 30 minutes
        )

        # Mock refresh - should NOT be called
        with patch("app.services.token_refresh.refresh_access_token") as mock_refresh:
            token = await get_valid_token(
                session=session,
                user_id=user.id,
                service_name="google_drive",
            )

            # Should NOT have refreshed
            assert token == "valid-for-30-mins"
            mock_refresh.assert_not_called()


class TestRefreshRaceCondition:
    """Tests for preventing race conditions on concurrent token refresh."""

    @pytest.mark.asyncio
    async def test_refresh_skipped_when_lock_held(self, session: Session):
        """Refresh is skipped when another refresh is in progress (lock held)."""
        os.environ["GOOGLE_CLIENT_ID"] = "test-client-id"
        os.environ["GOOGLE_CLIENT_SECRET"] = "test-client-secret"

        from app.crud.integration import create_or_update_integration
        from app.services.token_refresh import refresh_integration_token

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        # Create integration with expired token
        integration = create_or_update_integration(
            session=session,
            user_id=user.id,
            service_name="google_drive",
            access_token="expired-token",  # noqa
            refresh_token="refresh-token",
            expires_in=3600,
        )

        # Manually set expires_at to past and set a refresh lock
        integration.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        integration.refresh_locked_at = datetime.now(timezone.utc)  # Lock is active
        session.add(integration)
        session.commit()

        # Attempt to refresh should be skipped due to lock
        with patch("app.services.token_refresh.refresh_access_token") as mock_refresh:
            mock_refresh.return_value = {
                "access_token": "new-token",
                "refresh_token": "new-refresh-token",
                "expires_in": 3600,
            }

            result = await refresh_integration_token(
                session=session,
                user_id=user.id,
                service_name="google_drive",
            )

            # Should return False because refresh was skipped (lock held)
            assert result is False
            # OAuth provider should NOT have been called
            mock_refresh.assert_not_called()

    @pytest.mark.asyncio
    async def test_refresh_proceeds_when_lock_expired(self, session: Session):
        """Refresh proceeds when the lock has expired (stale lock)."""
        os.environ["GOOGLE_CLIENT_ID"] = "test-client-id"
        os.environ["GOOGLE_CLIENT_SECRET"] = "test-client-secret"

        from app.crud.integration import create_or_update_integration
        from app.services.token_refresh import refresh_integration_token, REFRESH_LOCK_TIMEOUT_SECONDS

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        # Create integration with expired token
        integration = create_or_update_integration(
            session=session,
            user_id=user.id,
            service_name="google_drive",
            access_token="expired-token",  # noqa
            refresh_token="refresh-token",
            expires_in=3600,
        )

        # Set expired lock (older than timeout)
        integration.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        integration.refresh_locked_at = datetime.now(timezone.utc) - timedelta(
            seconds=REFRESH_LOCK_TIMEOUT_SECONDS + 10
        )
        session.add(integration)
        session.commit()

        # Refresh should proceed because lock is stale
        with patch("app.services.token_refresh.refresh_access_token") as mock_refresh:
            mock_refresh.return_value = {
                "access_token": "new-token",
                "refresh_token": "new-refresh-token",
                "expires_in": 3600,
            }

            result = await refresh_integration_token(
                session=session,
                user_id=user.id,
                service_name="google_drive",
            )

            # Should succeed
            assert result is True
            mock_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_clears_lock_on_success(self, session: Session):
        """Lock is cleared after successful refresh."""
        os.environ["GOOGLE_CLIENT_ID"] = "test-client-id"
        os.environ["GOOGLE_CLIENT_SECRET"] = "test-client-secret"

        from app.crud.integration import create_or_update_integration, get_user_integration
        from app.services.token_refresh import refresh_integration_token

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        # Create integration with expired token (no lock)
        integration = create_or_update_integration(
            session=session,
            user_id=user.id,
            service_name="google_drive",
            access_token="expired-token",  # noqa
            refresh_token="refresh-token",
            expires_in=3600,
        )

        integration.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        session.add(integration)
        session.commit()

        with patch("app.services.token_refresh.refresh_access_token") as mock_refresh:
            mock_refresh.return_value = {
                "access_token": "new-token",
                "refresh_token": "new-refresh-token",
                "expires_in": 3600,
            }

            result = await refresh_integration_token(
                session=session,
                user_id=user.id,
                service_name="google_drive",
            )

            assert result is True

        # Lock should be cleared after success
        integration = get_user_integration(
            session=session, user_id=user.id, service_name="google_drive"
        )
        assert integration.refresh_locked_at is None

    @pytest.mark.asyncio
    async def test_refresh_clears_lock_on_failure(self, session: Session):
        """Lock is cleared even if refresh fails."""
        os.environ["GOOGLE_CLIENT_ID"] = "test-client-id"
        os.environ["GOOGLE_CLIENT_SECRET"] = "test-client-secret"

        from app.crud.integration import create_or_update_integration, get_user_integration
        from app.services.token_refresh import refresh_integration_token
        from app.services.oauth_token import OAuthTokenError

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        # Create integration with expired token
        integration = create_or_update_integration(
            session=session,
            user_id=user.id,
            service_name="google_drive",
            access_token="expired-token",  # noqa
            refresh_token="refresh-token",
            expires_in=3600,
        )

        integration.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        session.add(integration)
        session.commit()

        with patch("app.services.token_refresh.refresh_access_token") as mock_refresh:
            mock_refresh.side_effect = OAuthTokenError("invalid_grant", "Token revoked")

            result = await refresh_integration_token(
                session=session,
                user_id=user.id,
                service_name="google_drive",
            )

            assert result is False

        # Lock should be cleared even on failure
        integration = get_user_integration(
            session=session, user_id=user.id, service_name="google_drive"
        )
        assert integration.refresh_locked_at is None


class TestRefreshRateLimiting:
    """Tests for rate limiting on token refresh."""

    @pytest.mark.asyncio
    async def test_refresh_skipped_when_recently_attempted(self, session: Session):
        """Refresh is skipped if attempted too recently."""
        os.environ["GOOGLE_CLIENT_ID"] = "test-client-id"
        os.environ["GOOGLE_CLIENT_SECRET"] = "test-client-secret"

        from app.crud.integration import create_or_update_integration
        from app.services.token_refresh import refresh_integration_token, RATE_LIMIT_SECONDS

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        # Create integration with expired token
        integration = create_or_update_integration(
            session=session,
            user_id=user.id,
            service_name="google_drive",
            access_token="expired-token",  # noqa
            refresh_token="refresh-token",
            expires_in=3600,
        )

        # Set expired token and recent refresh attempt
        integration.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        integration.last_refresh_attempt = datetime.now(timezone.utc) - timedelta(seconds=30)
        session.add(integration)
        session.commit()

        with patch("app.services.token_refresh.refresh_access_token") as mock_refresh:
            mock_refresh.return_value = {
                "access_token": "new-token",
                "refresh_token": "new-refresh-token",
                "expires_in": 3600,
            }

            result = await refresh_integration_token(
                session=session,
                user_id=user.id,
                service_name="google_drive",
            )

            # Should return False because rate limited
            assert result is False
            mock_refresh.assert_not_called()

    @pytest.mark.asyncio
    async def test_refresh_proceeds_after_rate_limit_expires(self, session: Session):
        """Refresh proceeds after rate limit period has passed."""
        os.environ["GOOGLE_CLIENT_ID"] = "test-client-id"
        os.environ["GOOGLE_CLIENT_SECRET"] = "test-client-secret"

        from app.crud.integration import create_or_update_integration
        from app.services.token_refresh import refresh_integration_token, RATE_LIMIT_SECONDS

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        # Create integration with expired token
        integration = create_or_update_integration(
            session=session,
            user_id=user.id,
            service_name="google_drive",
            access_token="expired-token",  # noqa
            refresh_token="refresh-token",
            expires_in=3600,
        )

        # Set expired token and old refresh attempt (beyond rate limit)
        integration.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        integration.last_refresh_attempt = datetime.now(timezone.utc) - timedelta(
            seconds=RATE_LIMIT_SECONDS + 10
        )
        session.add(integration)
        session.commit()

        with patch("app.services.token_refresh.refresh_access_token") as mock_refresh:
            mock_refresh.return_value = {
                "access_token": "new-token",
                "refresh_token": "new-refresh-token",
                "expires_in": 3600,
            }

            result = await refresh_integration_token(
                session=session,
                user_id=user.id,
                service_name="google_drive",
            )

            # Should succeed
            assert result is True
            mock_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_updates_last_attempt_timestamp(self, session: Session):
        """Last refresh attempt timestamp is updated on attempt."""
        os.environ["GOOGLE_CLIENT_ID"] = "test-client-id"
        os.environ["GOOGLE_CLIENT_SECRET"] = "test-client-secret"

        from app.crud.integration import create_or_update_integration, get_user_integration
        from app.services.token_refresh import refresh_integration_token

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        # Create integration with expired token
        integration = create_or_update_integration(
            session=session,
            user_id=user.id,
            service_name="google_drive",
            access_token="expired-token",  # noqa
            refresh_token="refresh-token",
            expires_in=3600,
        )

        integration.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        session.add(integration)
        session.commit()

        before_refresh = datetime.now(timezone.utc)

        with patch("app.services.token_refresh.refresh_access_token") as mock_refresh:
            mock_refresh.return_value = {
                "access_token": "new-token",
                "refresh_token": "new-refresh-token",
                "expires_in": 3600,
            }

            await refresh_integration_token(
                session=session,
                user_id=user.id,
                service_name="google_drive",
            )

        # Check that last_refresh_attempt was updated
        integration = get_user_integration(
            session=session, user_id=user.id, service_name="google_drive"
        )
        assert integration.last_refresh_attempt is not None
        # Handle naive datetime from SQLite in tests
        last_attempt = integration.last_refresh_attempt
        if last_attempt.tzinfo is None:
            last_attempt = last_attempt.replace(tzinfo=timezone.utc)
        assert last_attempt >= before_refresh
