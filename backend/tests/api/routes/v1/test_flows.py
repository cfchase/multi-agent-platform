"""Tests for the Flows API endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models import User


@pytest.fixture
def dev_user(session: Session) -> User:
    """
    Create the dev-user that matches the local development user.

    In local mode, the app uses 'dev-user' as the default authenticated user.
    This fixture creates that user in the test database.
    """
    user = User(
        email="dev-user@example.com",
        username="dev-user",
        full_name="Development User",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


class TestFlowsAPI:
    """Tests for Flows API operations."""

    def test_list_flows_returns_flows(self, client: TestClient, dev_user: User):
        """Test that list_flows returns mock flows."""
        response = client.get("/api/v1/flows/")
        assert response.status_code == 200

        data = response.json()
        assert "data" in data
        assert "count" in data
        assert data["count"] >= 1

        # Check flow structure
        flow = data["data"][0]
        assert "id" in flow
        assert "name" in flow
        assert "description" in flow

    def test_list_flows_returns_proper_format(
        self, client: TestClient, dev_user: User
    ):
        """Test that flows have expected fields."""
        response = client.get("/api/v1/flows/")
        assert response.status_code == 200

        data = response.json()
        for flow in data["data"]:
            assert isinstance(flow["id"], str)
            assert isinstance(flow["name"], str)
            # description can be None or string
            assert flow["description"] is None or isinstance(flow["description"], str)

    def test_list_flows_count_matches_data(
        self, client: TestClient, dev_user: User
    ):
        """Test that count field matches actual data length."""
        response = client.get("/api/v1/flows/")
        assert response.status_code == 200

        data = response.json()
        assert data["count"] == len(data["data"])
