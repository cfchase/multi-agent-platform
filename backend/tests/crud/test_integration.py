"""
Tests for Integration CRUD operations.

Following TDD: These tests are written BEFORE the implementation.
"""

import pytest
from datetime import datetime, timezone, timedelta
from sqlmodel import Session

from app.models import User


class TestIntegrationCRUD:
    """Tests for integration CRUD functions."""

    def test_get_user_integration_returns_none_when_not_exists(self, session: Session):
        """get_user_integration returns None when no integration exists."""
        from app.crud.integration import get_user_integration

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        result = get_user_integration(
            session=session, user_id=user.id, service_name="google_drive"
        )
        assert result is None

    def test_get_user_integration_returns_integration(self, session: Session):
        """get_user_integration returns the integration when it exists."""
        from app.crud.integration import get_user_integration, create_or_update_integration

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        # Create integration
        create_or_update_integration(
            session=session,
            user_id=user.id,
            service_name="google_drive",
            access_token="test-token",
            refresh_token="test-refresh",
            expires_in=3600,
            scopes="drive.readonly",
        )

        result = get_user_integration(
            session=session, user_id=user.id, service_name="google_drive"
        )
        assert result is not None
        assert result.service_name == "google_drive"

    def test_get_user_integrations_returns_all(self, session: Session):
        """get_user_integrations returns all integrations for a user."""
        from app.crud.integration import get_user_integrations, create_or_update_integration

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        # Create multiple integrations
        for service in ["google_drive", "dataverse"]:
            create_or_update_integration(
                session=session,
                user_id=user.id,
                service_name=service,
                access_token=f"token-{service}",
            )

        results = get_user_integrations(session=session, user_id=user.id)
        assert len(results) == 2
        service_names = {r.service_name for r in results}
        assert service_names == {"google_drive", "dataverse"}

    def test_create_or_update_integration_creates_new(self, session: Session):
        """create_or_update_integration creates a new integration."""
        from app.crud.integration import create_or_update_integration, get_user_integration

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        integration = create_or_update_integration(
            session=session,
            user_id=user.id,
            service_name="google_drive",
            access_token="new-token",
            refresh_token="new-refresh",
            expires_in=3600,
            scopes="drive.readonly",
        )

        assert integration.id is not None
        assert integration.service_name == "google_drive"

        # Verify it's persisted
        fetched = get_user_integration(
            session=session, user_id=user.id, service_name="google_drive"
        )
        assert fetched is not None
        assert fetched.id == integration.id

    def test_create_or_update_integration_updates_existing(self, session: Session):
        """create_or_update_integration updates an existing integration."""
        from app.crud.integration import create_or_update_integration, get_decrypted_tokens

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        # Create initial integration
        integration1 = create_or_update_integration(
            session=session,
            user_id=user.id,
            service_name="google_drive",
            access_token="old-token",
        )
        original_id = integration1.id

        # Update with new token
        integration2 = create_or_update_integration(
            session=session,
            user_id=user.id,
            service_name="google_drive",
            access_token="new-token",
        )

        # Should be same record, updated
        assert integration2.id == original_id

        # Verify token was updated
        tokens = get_decrypted_tokens(integration2)
        assert tokens["access_token"] == "new-token"

    def test_delete_integration_removes_record(self, session: Session):
        """delete_integration removes the integration."""
        from app.crud.integration import (
            create_or_update_integration,
            delete_integration,
            get_user_integration,
        )

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        # Create integration
        create_or_update_integration(
            session=session,
            user_id=user.id,
            service_name="google_drive",
            access_token="token",
        )

        # Delete it
        result = delete_integration(
            session=session, user_id=user.id, service_name="google_drive"
        )
        assert result is True

        # Verify it's gone
        fetched = get_user_integration(
            session=session, user_id=user.id, service_name="google_drive"
        )
        assert fetched is None

    def test_delete_integration_returns_false_when_not_exists(self, session: Session):
        """delete_integration returns False when integration doesn't exist."""
        from app.crud.integration import delete_integration

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        result = delete_integration(
            session=session, user_id=user.id, service_name="nonexistent"
        )
        assert result is False

    def test_get_decrypted_tokens_returns_tokens(self, session: Session):
        """get_decrypted_tokens returns decrypted access and refresh tokens."""
        from app.crud.integration import create_or_update_integration, get_decrypted_tokens

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        integration = create_or_update_integration(
            session=session,
            user_id=user.id,
            service_name="google_drive",
            access_token="my-access-token",
            refresh_token="my-refresh-token",
        )

        tokens = get_decrypted_tokens(integration)

        assert tokens["access_token"] == "my-access-token"
        assert tokens["refresh_token"] == "my-refresh-token"

    def test_get_decrypted_tokens_handles_none_refresh(self, session: Session):
        """get_decrypted_tokens handles None refresh token."""
        from app.crud.integration import create_or_update_integration, get_decrypted_tokens

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        integration = create_or_update_integration(
            session=session,
            user_id=user.id,
            service_name="google_drive",
            access_token="my-access-token",
            refresh_token=None,
        )

        tokens = get_decrypted_tokens(integration)

        assert tokens["access_token"] == "my-access-token"
        assert tokens["refresh_token"] is None

    def test_is_expired_returns_false_for_valid_token(self, session: Session):
        """Integration.is_expired() returns False for non-expired token."""
        from app.crud.integration import create_or_update_integration

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        integration = create_or_update_integration(
            session=session,
            user_id=user.id,
            service_name="google_drive",
            access_token="token",
            expires_in=3600,  # 1 hour from now
        )

        assert integration.is_expired() is False

    def test_is_expired_returns_true_for_expired_token(self, session: Session):
        """Integration.is_expired() returns True for expired token."""
        from app.crud.integration import create_or_update_integration

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        integration = create_or_update_integration(
            session=session,
            user_id=user.id,
            service_name="google_drive",
            access_token="token",
            expires_in=3600,
        )

        # Manually set expires_at to past
        integration.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        session.add(integration)
        session.commit()
        session.refresh(integration)

        assert integration.is_expired() is True

    def test_is_expired_returns_false_for_no_expiry(self, session: Session):
        """Integration.is_expired() returns False when no expiry is set."""
        from app.crud.integration import create_or_update_integration

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        integration = create_or_update_integration(
            session=session,
            user_id=user.id,
            service_name="google_drive",
            access_token="token",
            expires_in=None,  # No expiry
        )

        assert integration.is_expired() is False

    def test_get_missing_integrations_returns_all_when_none_exist(self, session: Session):
        """get_missing_integrations returns all required when none exist."""
        from app.crud.integration import get_missing_integrations

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        required = ["google_drive", "dataverse"]
        missing = get_missing_integrations(
            session=session, user_id=user.id, required_services=required
        )

        assert set(missing) == set(required)

    def test_get_missing_integrations_returns_only_missing(self, session: Session):
        """get_missing_integrations returns only services not connected."""
        from app.crud.integration import (
            create_or_update_integration,
            get_missing_integrations,
        )

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        # Connect google_drive
        create_or_update_integration(
            session=session,
            user_id=user.id,
            service_name="google_drive",
            access_token="token",
            expires_in=3600,
        )

        required = ["google_drive", "dataverse"]
        missing = get_missing_integrations(
            session=session, user_id=user.id, required_services=required
        )

        assert missing == ["dataverse"]

    def test_get_missing_integrations_includes_expired(self, session: Session):
        """get_missing_integrations includes services with expired tokens."""
        from app.crud.integration import (
            create_or_update_integration,
            get_missing_integrations,
        )

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        # Connect google_drive with expired token
        integration = create_or_update_integration(
            session=session,
            user_id=user.id,
            service_name="google_drive",
            access_token="token",
            expires_in=3600,
        )
        # Manually expire it
        integration.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        session.add(integration)
        session.commit()

        required = ["google_drive", "dataverse"]
        missing = get_missing_integrations(
            session=session, user_id=user.id, required_services=required
        )

        # Both should be missing (google_drive is expired)
        assert set(missing) == {"google_drive", "dataverse"}

    def test_get_integration_status_all_missing(self, session: Session):
        """get_integration_status returns all services as missing when none connected."""
        from app.crud.integration import get_integration_status

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        available = ["google_drive", "dataverse"]
        status = get_integration_status(
            session=session, user_id=user.id, available_services=available
        )

        assert status["connected"] == []
        assert status["expired"] == []
        assert set(status["missing"]) == {"google_drive", "dataverse"}

    def test_get_integration_status_all_connected(self, session: Session):
        """get_integration_status returns all services as connected when all valid."""
        from app.crud.integration import (
            create_or_update_integration,
            get_integration_status,
        )

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        # Connect both services with valid tokens
        for service in ["google_drive", "dataverse"]:
            create_or_update_integration(
                session=session,
                user_id=user.id,
                service_name=service,
                access_token=f"token-{service}",
                expires_in=3600,
            )

        available = ["google_drive", "dataverse"]
        status = get_integration_status(
            session=session, user_id=user.id, available_services=available
        )

        assert set(status["connected"]) == {"google_drive", "dataverse"}
        assert status["expired"] == []
        assert status["missing"] == []

    def test_get_integration_status_mixed(self, session: Session):
        """get_integration_status correctly categorizes connected, expired, and missing."""
        from app.crud.integration import (
            create_or_update_integration,
            get_integration_status,
        )

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        # Connect google_drive with valid token
        create_or_update_integration(
            session=session,
            user_id=user.id,
            service_name="google_drive",
            access_token="google-token",
            expires_in=3600,
        )

        # Connect dataverse with expired token
        dv_integration = create_or_update_integration(
            session=session,
            user_id=user.id,
            service_name="dataverse",
            access_token="dv-token",
            expires_in=3600,
        )
        dv_integration.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        session.add(dv_integration)
        session.commit()

        # "other_service" is not connected at all
        available = ["google_drive", "dataverse", "other_service"]
        status = get_integration_status(
            session=session, user_id=user.id, available_services=available
        )

        assert status["connected"] == ["google_drive"]
        assert status["expired"] == ["dataverse"]
        assert status["missing"] == ["other_service"]

    def test_get_integration_status_no_expiry_is_connected(self, session: Session):
        """get_integration_status treats tokens without expiry as connected."""
        from app.crud.integration import (
            create_or_update_integration,
            get_integration_status,
        )

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        # Connect with no expiry (some services don't expire tokens)
        create_or_update_integration(
            session=session,
            user_id=user.id,
            service_name="google_drive",
            access_token="token",
            expires_in=None,  # No expiry
        )

        available = ["google_drive"]
        status = get_integration_status(
            session=session, user_id=user.id, available_services=available
        )

        assert status["connected"] == ["google_drive"]
        assert status["expired"] == []
        assert status["missing"] == []
