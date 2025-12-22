"""Tests for the main FastAPI application."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings


def test_read_root(client: TestClient):
    """Test the root endpoint returns API information."""
    response = client.get("/")
    assert response.status_code == 200

    data = response.json()
    assert "message" in data
    assert settings.PROJECT_NAME in data["message"]
    assert "version" in data
    assert data["rest_api"] == "/api/v1/"
    assert data["graphql_api"] == "/api/graphql"
    assert data["admin"] == "/admin"
    assert data["docs"] == "/docs"


def test_health_check(client: TestClient):
    """Test the health check endpoint with database connectivity."""
    response = client.get("/api/v1/utils/health-check")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert data["message"] == "Backend is running"
    assert "database" in data
    assert data["database"]["status"] == "healthy"
    assert "message" in data["database"]


def test_admin_panel_accessible(client: TestClient):
    """Test the admin panel is accessible."""
    response = client.get("/admin/")
    # Admin redirects to login or renders directly
    assert response.status_code in [200, 302]
