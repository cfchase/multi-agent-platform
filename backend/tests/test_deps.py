"""Tests for API dependencies, particularly OAuth header handling."""

import os
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.main import app
from app.api.deps import get_db


@pytest.fixture(name="production_client")
def production_client_fixture(session: Session):
    """Create a test client simulating production environment (non-local)."""
    # Save original environment
    original_env = os.environ.get("ENVIRONMENT")

    # Set to production mode
    os.environ["ENVIRONMENT"] = "production"

    def get_session_override():
        return session

    app.dependency_overrides[get_db] = get_session_override

    # Need to reload settings to pick up new environment
    from app.core.config import settings
    original_setting = settings.ENVIRONMENT
    settings.ENVIRONMENT = "production"

    client = TestClient(app)
    yield client

    # Restore
    app.dependency_overrides.clear()
    settings.ENVIRONMENT = original_setting
    if original_env is not None:
        os.environ["ENVIRONMENT"] = original_env
    elif "ENVIRONMENT" in os.environ:
        del os.environ["ENVIRONMENT"]


class TestOAuthHeaderHandling:
    """Test OAuth2 proxy header handling in get_current_user."""

    def test_get_current_user_with_oauth_headers(self, production_client: TestClient):
        """Test that OAuth2 proxy headers are correctly parsed."""
        response = production_client.get(
            "/api/v1/users/me",
            headers={
                "X-Forwarded-Preferred-Username": "testuser",
                "X-Forwarded-Email": "testuser@example.com",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testuser"
        assert data["email"] == "testuser@example.com"

    def test_get_current_user_with_openshift_oauth_header(
        self, production_client: TestClient
    ):
        """Test fallback to X-Forwarded-User header (OpenShift OAuth proxy)."""
        response = production_client.get(
            "/api/v1/users/me",
            headers={
                "X-Forwarded-User": "openshiftuser",
                "X-Forwarded-Email": "openshift@example.com",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "openshiftuser"
        assert data["email"] == "openshift@example.com"

    def test_oauth_preferred_username_takes_precedence(
        self, production_client: TestClient
    ):
        """Test that X-Forwarded-Preferred-Username takes precedence over X-Forwarded-User."""
        response = production_client.get(
            "/api/v1/users/me",
            headers={
                "X-Forwarded-Preferred-Username": "preferred",
                "X-Forwarded-User": "fallback",
                "X-Forwarded-Email": "user@example.com",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "preferred"

    def test_missing_headers_returns_401_in_production(
        self, production_client: TestClient
    ):
        """Test that missing OAuth headers return 401 in production mode."""
        response = production_client.get("/api/v1/users/me")

        assert response.status_code == 401
        assert "Authentication required" in response.json()["detail"]

    def test_missing_email_returns_401(self, production_client: TestClient):
        """Test that missing email header returns 401."""
        response = production_client.get(
            "/api/v1/users/me",
            headers={
                "X-Forwarded-Preferred-Username": "testuser",
                # Missing X-Forwarded-Email
            },
        )

        assert response.status_code == 401

    def test_local_mode_uses_dev_user(self, client: TestClient):
        """Test that local mode falls back to dev-user when no headers provided."""
        # The default client fixture uses TESTING=1 which behaves like local
        # We need to check what the actual behavior is in local mode
        response = client.get("/api/v1/users/me")

        # In local/test mode, should use dev-user fallback
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "dev-user"
        assert data["email"] == "dev-user@example.com"
