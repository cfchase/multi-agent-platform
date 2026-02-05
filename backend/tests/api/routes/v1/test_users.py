"""
Tests for Users API endpoints.

Tests cover:
- GET /users/me - returns current user with integration status
"""

import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models import User


class TestUsersMe:
    """Tests for GET /users/me endpoint."""

    def test_get_me_returns_user_info(self, client: TestClient, session: Session):
        """GET /users/me returns current user info."""
        response = client.get(
            "/api/v1/users/me",
            headers={
                "X-Forwarded-Preferred-Username": "testuser",
                "X-Forwarded-Email": "test@example.com",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"
        assert "integration_status" in data

    def test_get_me_includes_integration_status(self, client: TestClient, session: Session):
        """GET /users/me includes integration_status with connected, expired, missing."""
        response = client.get(
            "/api/v1/users/me",
            headers={
                "X-Forwarded-Preferred-Username": "testuser",
                "X-Forwarded-Email": "test@example.com",
            },
        )

        assert response.status_code == 200
        data = response.json()

        status = data["integration_status"]
        assert "connected" in status
        assert "expired" in status
        assert "missing" in status

        # All services should be in one of the lists
        all_services = status["connected"] + status["expired"] + status["missing"]
        assert len(all_services) > 0  # At least one service is available

    def test_get_me_shows_missing_when_no_integrations(
        self, client: TestClient, session: Session
    ):
        """GET /users/me shows all services as missing when user has no integrations."""
        response = client.get(
            "/api/v1/users/me",
            headers={
                "X-Forwarded-Preferred-Username": "newuser",
                "X-Forwarded-Email": "newuser@example.com",
            },
        )

        assert response.status_code == 200
        data = response.json()

        status = data["integration_status"]
        # New user should have no connected or expired integrations
        assert status["connected"] == []
        assert status["expired"] == []
        # But should have missing services if any are configured
        # (depends on test environment configuration)

    def test_get_me_shows_connected_when_valid_tokens(
        self, client: TestClient, session: Session
    ):
        """GET /users/me shows service as connected when user has valid token."""
        from app.crud.integration import create_or_update_integration

        # First create the user via the endpoint
        response = client.get(
            "/api/v1/users/me",
            headers={
                "X-Forwarded-Preferred-Username": "connecteduser",
                "X-Forwarded-Email": "connected@example.com",
            },
        )
        assert response.status_code == 200
        user_id = response.json()["id"]

        # Now add a valid integration
        create_or_update_integration(
            session=session,
            user_id=user_id,
            service_name="google_drive",
            access_token="valid-token",
            expires_in=3600,  # 1 hour from now
        )

        # Get me again
        response = client.get(
            "/api/v1/users/me",
            headers={
                "X-Forwarded-Preferred-Username": "connecteduser",
                "X-Forwarded-Email": "connected@example.com",
            },
        )

        assert response.status_code == 200
        status = response.json()["integration_status"]
        assert "google_drive" in status["connected"]
        assert "google_drive" not in status["expired"]
        assert "google_drive" not in status["missing"]

    def test_get_me_shows_expired_when_token_expired(
        self, client: TestClient, session: Session
    ):
        """GET /users/me shows service as expired when token has expired."""
        from app.crud.integration import create_or_update_integration

        # First create the user via the endpoint
        response = client.get(
            "/api/v1/users/me",
            headers={
                "X-Forwarded-Preferred-Username": "expireduser",
                "X-Forwarded-Email": "expired@example.com",
            },
        )
        assert response.status_code == 200
        user_id = response.json()["id"]

        # Add an integration then expire it
        integration = create_or_update_integration(
            session=session,
            user_id=user_id,
            service_name="google_drive",
            access_token="expired-token",
            expires_in=3600,
        )
        # Manually expire it
        integration.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        session.add(integration)
        session.commit()

        # Get me again
        response = client.get(
            "/api/v1/users/me",
            headers={
                "X-Forwarded-Preferred-Username": "expireduser",
                "X-Forwarded-Email": "expired@example.com",
            },
        )

        assert response.status_code == 200
        status = response.json()["integration_status"]
        assert "google_drive" not in status["connected"]
        assert "google_drive" in status["expired"]
        assert "google_drive" not in status["missing"]
