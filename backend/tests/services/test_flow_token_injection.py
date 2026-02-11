"""
Tests for flow token injection service.

Tests the generic settings injection pattern:
- build_user_settings_data: OAuth tokens via UserSettings component
- build_app_settings_data: App context via AppSettings component
- build_generic_tweaks: Tweak dict assembly for Langflow
- get_required_services_for_flow: Flow-to-services mapping
"""

import pytest
from unittest.mock import patch, AsyncMock
from sqlmodel import Session

from app.models import User
from app.services.flow_token_injection import (
    build_app_settings_data,
    build_generic_tweaks,
    build_user_settings_data,
    get_required_services_for_flow,
    MissingTokenError,
)


class TestBuildUserSettingsData:
    """Tests for building user settings with OAuth tokens."""

    @pytest.mark.asyncio
    async def test_with_valid_token_single_service(self, session: Session):
        """Builds user data with token for a single service."""
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
            services=["google_drive"],
        )

        assert user_data["user_id"] == user.id
        assert user_data["google_drive_token"] == "google-access-token"

    @pytest.mark.asyncio
    async def test_with_multiple_services(self, session: Session):
        """Builds user data with tokens for multiple services."""
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
            services=["google_drive", "dataverse"],
        )

        assert user_data["user_id"] == user.id
        assert user_data["google_drive_token"] == "google-token"
        assert user_data["dataverse_token"] == "dataverse-token"

    @pytest.mark.asyncio
    async def test_with_no_services_defaults_to_all(self, session: Session):
        """When services is None, defaults to checking all known services."""
        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        # No integrations created — get_valid_token returns None for each
        user_data = await build_user_settings_data(
            session=session,
            user_id=user.id,
            services=None,
        )

        # Should still have user_id, but no tokens (none connected)
        assert user_data["user_id"] == user.id
        assert "google_drive_token" not in user_data
        assert "dataverse_token" not in user_data

    @pytest.mark.asyncio
    async def test_with_empty_services_list(self, session: Session):
        """Empty list means no services needed — returns only user_id."""
        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        user_data = await build_user_settings_data(
            session=session,
            user_id=user.id,
            services=[],
        )

        assert user_data == {"user_id": user.id}

    @pytest.mark.asyncio
    async def test_missing_integration_skips_gracefully(self, session: Session):
        """When a service has no integration, its token is omitted (not error)."""
        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        # No google_drive integration created
        user_data = await build_user_settings_data(
            session=session,
            user_id=user.id,
            services=["google_drive"],
        )

        assert user_data["user_id"] == user.id
        assert "google_drive_token" not in user_data

    @pytest.mark.asyncio
    async def test_with_refreshed_token(self, session: Session):
        """Uses refreshed token value when get_valid_token refreshes."""
        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        with patch(
            "app.services.flow_token_injection.get_valid_token",
            new_callable=AsyncMock,
            return_value="refreshed-token",
        ):
            user_data = await build_user_settings_data(
                session=session,
                user_id=user.id,
                services=["google_drive"],
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


class TestGetRequiredServicesForFlow:
    """Tests for flow-to-services mapping."""

    def test_known_flow_returns_services(self):
        """Known flow returns its required OAuth services."""
        services = get_required_services_for_flow("enterprise-agent")
        assert services == ["google_drive"]

    def test_unknown_flow_returns_empty(self):
        """Unknown flow returns empty list (no OAuth needed)."""
        services = get_required_services_for_flow("unknown-flow-name")
        assert services == []

    def test_return_type_is_list(self):
        """Return type is always list[str]."""
        services = get_required_services_for_flow("enterprise-agent")
        assert isinstance(services, list)
        for s in services:
            assert isinstance(s, str)

    def test_multi_service_flow(self):
        """Flow requiring multiple services returns all of them."""
        services = get_required_services_for_flow("multi-source-rag")
        assert "google_drive" in services
        assert "dataverse" in services
