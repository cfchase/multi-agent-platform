"""
Tests for flow token injection service.

Tests the generic settings injection pattern:
- build_user_settings_data: OAuth tokens via UserSettings component
- build_app_settings_data: App context via AppSettings component
- build_generic_tweaks: Tweak dict assembly for Langflow
"""

import pytest
from unittest.mock import patch, AsyncMock
from sqlmodel import Session

from app.models import User
from app.services.flow_token_injection import (
    build_app_settings_data,
    build_generic_tweaks,
    build_user_settings_data,
)


class TestBuildUserSettingsData:
    """Tests for building user settings with OAuth tokens."""

    @pytest.mark.asyncio
    async def test_with_single_integration(self, session: Session):
        """Injects token for a single connected service."""
        from app.crud.integration import create_or_update_integration

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        create_or_update_integration(
            session=session,
            user_id=user.id,
            service_name="google_drive",
            access_token="google-access-token",
            refresh_token="google-refresh-token",
            expires_in=3600,
        )

        user_data = await build_user_settings_data(
            session=session,
            user_id=user.id,
        )

        assert user_data["user_id"] == user.id
        assert user_data["google_drive_token"] == "google-access-token"

    @pytest.mark.asyncio
    async def test_with_multiple_integrations(self, session: Session):
        """Injects tokens for all connected services."""
        from app.crud.integration import create_or_update_integration

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        create_or_update_integration(
            session=session,
            user_id=user.id,
            service_name="google_drive",
            access_token="google-token",
            expires_in=3600,
        )
        create_or_update_integration(
            session=session,
            user_id=user.id,
            service_name="dataverse",
            access_token="dataverse-token",
            expires_in=3600,
        )

        user_data = await build_user_settings_data(
            session=session,
            user_id=user.id,
        )

        assert user_data["user_id"] == user.id
        assert user_data["google_drive_token"] == "google-token"
        assert user_data["dataverse_token"] == "dataverse-token"

    @pytest.mark.asyncio
    async def test_with_no_integrations(self, session: Session):
        """Returns only user_id when no services are connected."""
        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        user_data = await build_user_settings_data(
            session=session,
            user_id=user.id,
        )

        assert user_data["user_id"] == user.id
        assert "google_drive_token" not in user_data
        assert "dataverse_token" not in user_data

    @pytest.mark.asyncio
    async def test_expired_token_omitted(self, session: Session):
        """Expired tokens are omitted (get_valid_token returns None)."""
        from app.crud.integration import create_or_update_integration

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        # Create an expired integration (expires_in=0 makes it already expired)
        create_or_update_integration(
            session=session,
            user_id=user.id,
            service_name="google_drive",
            access_token="expired-token",
            expires_in=0,
        )

        # Mock get_valid_token to return None (simulating expired + refresh failure)
        with patch(
            "app.services.flow_token_injection.get_valid_token",
            new_callable=AsyncMock,
            return_value=None,
        ):
            user_data = await build_user_settings_data(
                session=session,
                user_id=user.id,
            )

        assert user_data["user_id"] == user.id
        assert "google_drive_token" not in user_data

    @pytest.mark.asyncio
    async def test_partial_tokens_when_one_expired(self, session: Session):
        """Injects only valid tokens when some integrations have expired."""
        from app.crud.integration import create_or_update_integration

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
        create_or_update_integration(
            session=session,
            user_id=user.id,
            service_name="dataverse",
            access_token="expired-token",
            expires_in=0,
        )

        async def selective_get_valid_token(*, session, user_id, service_name):
            if service_name == "google_drive":
                return "valid-token"
            return None  # dataverse expired

        with patch(
            "app.services.flow_token_injection.get_valid_token",
            new_callable=AsyncMock,
            side_effect=selective_get_valid_token,
        ):
            user_data = await build_user_settings_data(
                session=session,
                user_id=user.id,
            )

        assert user_data["google_drive_token"] == "valid-token"
        assert "dataverse_token" not in user_data
        assert user_data["user_id"] == user.id

    @pytest.mark.asyncio
    async def test_with_refreshed_token(self, session: Session):
        """Uses refreshed token value when get_valid_token refreshes."""
        from app.crud.integration import create_or_update_integration

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        create_or_update_integration(
            session=session,
            user_id=user.id,
            service_name="google_drive",
            access_token="old-token",
            expires_in=3600,
        )

        with patch(
            "app.services.flow_token_injection.get_valid_token",
            new_callable=AsyncMock,
            return_value="refreshed-token",
        ):
            user_data = await build_user_settings_data(
                session=session,
                user_id=user.id,
            )

        assert user_data["google_drive_token"] == "refreshed-token"


class TestBuildAppSettingsData:
    """Tests for building app settings."""

    def test_returns_expected_structure(self):
        """Returns dict with app_name and features."""
        app_data = build_app_settings_data()

        assert "app_name" in app_data
        assert app_data["app_name"] == "multi-agent-platform"
        assert "features" in app_data
        assert isinstance(app_data["features"], dict)

    def test_no_secrets_in_output(self):
        """App settings must not contain API keys or secrets."""
        app_data = build_app_settings_data()
        data_str = str(app_data).lower()

        for sensitive_key in ["api_key", "secret", "password", "token"]:
            assert sensitive_key not in data_str


class TestBuildGenericTweaks:
    """Tests for building generic Langflow tweaks."""

    def test_with_user_data_only(self):
        """Builds tweaks with only UserSettings."""
        user_data = {"user_id": 1, "google_drive_token": "abc"}
        tweaks = build_generic_tweaks(user_data=user_data)

        assert "User Settings" in tweaks
        assert tweaks["User Settings"]["settings_data"] == user_data
        assert "App Settings" not in tweaks

    def test_with_app_data_only(self):
        """Builds tweaks with only AppSettings."""
        app_data = {"app_name": "test", "features": {}}
        tweaks = build_generic_tweaks(app_data=app_data)

        assert "App Settings" in tweaks
        assert tweaks["App Settings"]["settings_data"] == app_data
        assert "User Settings" not in tweaks

    def test_with_both(self):
        """Builds tweaks with both UserSettings and AppSettings."""
        user_data = {"user_id": 1}
        app_data = {"app_name": "test"}
        tweaks = build_generic_tweaks(user_data=user_data, app_data=app_data)

        assert "User Settings" in tweaks
        assert "App Settings" in tweaks

    def test_with_neither(self):
        """Returns empty tweaks when no data provided."""
        tweaks = build_generic_tweaks()
        assert tweaks == {}

    def test_with_empty_dicts(self):
        """Empty dicts are falsy — no tweaks generated."""
        tweaks = build_generic_tweaks(user_data={}, app_data={})
        assert tweaks == {}
