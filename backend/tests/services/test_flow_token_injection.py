"""
Tests for flow token injection service.

Following TDD: These tests are written BEFORE the implementation.
"""

import os
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock
from sqlmodel import Session

from app.models import User


class TestBuildFlowTweaks:
    """Tests for building flow tweaks with user tokens."""

    @pytest.mark.asyncio
    async def test_build_flow_tweaks_with_valid_tokens(self, session: Session):
        """Builds tweaks with tokens for required services."""
        os.environ["GOOGLE_CLIENT_ID"] = "test-client-id"
        os.environ["GOOGLE_CLIENT_SECRET"] = "test-client-secret"

        from app.crud.integration import create_or_update_integration
        from app.services.flow_token_injection import build_flow_tweaks

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        # Create integration with valid token
        create_or_update_integration(
            session=session,
            user_id=user.id,
            service_name="google_drive",
            access_token="google-access-token",
            refresh_token="google-refresh-token",
            expires_in=3600,
        )

        # Configuration maps services to tweak paths
        token_config = {
            "google_drive": "GoogleDriveComponent.api_key",
        }

        tweaks = await build_flow_tweaks(
            session=session,
            user_id=user.id,
            token_config=token_config,
        )

        assert tweaks is not None
        assert "GoogleDriveComponent" in tweaks
        assert tweaks["GoogleDriveComponent"]["api_key"] == "google-access-token"

    @pytest.mark.asyncio
    async def test_build_flow_tweaks_multiple_services(self, session: Session):
        """Builds tweaks for multiple services."""
        os.environ["GOOGLE_CLIENT_ID"] = "test-client-id"
        os.environ["GOOGLE_CLIENT_SECRET"] = "test-client-secret"
        # Note: Dataverse uses dynamic client registration, no static credentials needed

        from app.crud.integration import create_or_update_integration
        from app.services.flow_token_injection import build_flow_tweaks

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        # Create integrations
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

        token_config = {
            "google_drive": "GoogleDrive.access_token",
            "dataverse": "DataverseLoader.api_token",
        }

        tweaks = await build_flow_tweaks(
            session=session,
            user_id=user.id,
            token_config=token_config,
        )

        assert "GoogleDrive" in tweaks
        assert tweaks["GoogleDrive"]["access_token"] == "google-token"
        assert "DataverseLoader" in tweaks
        assert tweaks["DataverseLoader"]["api_token"] == "dataverse-token"

    @pytest.mark.asyncio
    async def test_build_flow_tweaks_missing_integration(self, session: Session):
        """Raises error when required service is not connected."""
        from app.services.flow_token_injection import build_flow_tweaks, MissingTokenError

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        token_config = {
            "google_drive": "GoogleDrive.access_token",
        }

        with pytest.raises(MissingTokenError, match="google_drive"):
            await build_flow_tweaks(
                session=session,
                user_id=user.id,
                token_config=token_config,
            )

    @pytest.mark.asyncio
    async def test_build_flow_tweaks_merges_existing(self, session: Session):
        """Merges token tweaks with existing tweaks."""
        os.environ["GOOGLE_CLIENT_ID"] = "test-client-id"
        os.environ["GOOGLE_CLIENT_SECRET"] = "test-client-secret"

        from app.crud.integration import create_or_update_integration
        from app.services.flow_token_injection import build_flow_tweaks

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

        token_config = {
            "google_drive": "GoogleDrive.access_token",
        }

        existing_tweaks = {
            "SomeOtherComponent": {"setting": "value"},
            "GoogleDrive": {"other_setting": "other_value"},
        }

        tweaks = await build_flow_tweaks(
            session=session,
            user_id=user.id,
            token_config=token_config,
            existing_tweaks=existing_tweaks,
        )

        # Original tweaks preserved
        assert tweaks["SomeOtherComponent"]["setting"] == "value"
        # Token added to existing component config
        assert tweaks["GoogleDrive"]["access_token"] == "google-token"
        assert tweaks["GoogleDrive"]["other_setting"] == "other_value"

    @pytest.mark.asyncio
    async def test_build_flow_tweaks_refreshes_expired(self, session: Session):
        """Refreshes expired tokens before building tweaks."""
        os.environ["GOOGLE_CLIENT_ID"] = "test-client-id"
        os.environ["GOOGLE_CLIENT_SECRET"] = "test-client-secret"

        from app.crud.integration import create_or_update_integration
        from app.services.flow_token_injection import build_flow_tweaks

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        # Create integration with expired token
        integration = create_or_update_integration(
            session=session,
            user_id=user.id,
            service_name="google_drive",
            access_token="expired-token",
            refresh_token="refresh-token",
            expires_in=3600,
        )

        # Manually expire it
        integration.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        session.add(integration)
        session.commit()

        token_config = {
            "google_drive": "GoogleDrive.access_token",
        }

        # Mock the token refresh to return a new token
        with patch("app.services.flow_token_injection.get_valid_token") as mock_get_token:
            mock_get_token.return_value = "refreshed-token"

            tweaks = await build_flow_tweaks(
                session=session,
                user_id=user.id,
                token_config=token_config,
            )

            assert tweaks["GoogleDrive"]["access_token"] == "refreshed-token"
            mock_get_token.assert_called_once()


class TestParseTweakPath:
    """Tests for parsing tweak paths."""

    def test_parse_tweak_path_simple(self):
        """Parses simple component.field path."""
        from app.services.flow_token_injection import parse_tweak_path

        component, field = parse_tweak_path("GoogleDrive.access_token")

        assert component == "GoogleDrive"
        assert field == "access_token"

    def test_parse_tweak_path_with_underscores(self):
        """Parses paths with underscores in names."""
        from app.services.flow_token_injection import parse_tweak_path

        component, field = parse_tweak_path("My_Custom_Component.api_key")

        assert component == "My_Custom_Component"
        assert field == "api_key"

    def test_parse_tweak_path_invalid(self):
        """Raises error for invalid path format."""
        from app.services.flow_token_injection import parse_tweak_path

        with pytest.raises(ValueError, match="Invalid tweak path"):
            parse_tweak_path("invalid_path_without_dot")
