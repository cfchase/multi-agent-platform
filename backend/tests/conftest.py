"""
Pytest configuration and fixtures for backend tests.

This module is automatically loaded by pytest and provides:
- TESTING environment flag to disable .env loading
- Shared fixtures for database sessions and test clients
"""

import os

# Set TESTING flag BEFORE any app imports
# This prevents loading .env file during tests, ensuring test isolation
os.environ["TESTING"] = "1"

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.main import app
from app.api.deps import get_db


@pytest.fixture(name="session")
def session_fixture():
    """Create a new in-memory database session for each test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    """Create a test client with database session override."""

    def get_session_override():
        return session

    app.dependency_overrides[get_db] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
