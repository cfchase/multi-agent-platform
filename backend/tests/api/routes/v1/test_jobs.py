"""Tests for the Job API endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models import Chat, ChatMessage, Job, JobStatus, User


@pytest.fixture
def dev_user(session: Session) -> User:
    """Create the dev-user that matches the local development user."""
    user = User(
        email="dev-user@example.com",
        username="dev-user",
        full_name="Development User",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture
def test_chat(session: Session, dev_user: User) -> Chat:
    """Create a test chat owned by the dev user."""
    chat = Chat(
        title="Test Chat",
        user_id=dev_user.id,
    )
    session.add(chat)
    session.commit()
    session.refresh(chat)
    return chat


@pytest.fixture
def test_message(session: Session, test_chat: Chat) -> ChatMessage:
    """Create a test assistant message linked to the chat."""
    message = ChatMessage(
        chat_id=test_chat.id,
        content="",
        role="assistant",
    )
    session.add(message)
    session.commit()
    session.refresh(message)
    return message


@pytest.fixture
def test_job(session: Session, test_message: ChatMessage) -> Job:
    """Create a test job in pending state."""
    job = Job(
        chat_message_id=test_message.id,
        flow_id="mock-flow-1",
        status=JobStatus.PENDING.value,
        langflow_job_id="mock-lf-job-123",
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


@pytest.fixture
def completed_job(session: Session, test_message: ChatMessage) -> Job:
    """Create a test job in completed state."""
    job = Job(
        chat_message_id=test_message.id,
        flow_id="mock-flow-1",
        status=JobStatus.COMPLETED.value,
        langflow_job_id="mock-lf-job-456",
        result_content="Test result",
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


class TestGetJob:
    """Tests for GET /v1/jobs/{id} endpoint."""

    def test_get_job(self, client: TestClient, test_job: Job):
        """Test getting a job by ID."""
        response = client.get(f"/api/v1/jobs/{test_job.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_job.id
        assert data["status"] == "pending"
        assert data["langflow_job_id"] == "mock-lf-job-123"
        assert data["flow_id"] == "mock-flow-1"

    def test_get_job_not_found(self, client: TestClient, dev_user: User):
        """Test getting a non-existent job returns 404."""
        response = client.get("/api/v1/jobs/99999")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_job_with_sync(self, client: TestClient, test_job: Job):
        """Test getting a job with sync=true triggers LangFlow poll."""
        response = client.get(f"/api/v1/jobs/{test_job.id}?sync=true")
        assert response.status_code == 200
        data = response.json()
        # Mock client returns "completed" status, so after sync the job
        # should be updated to completed
        assert data["status"] == "completed"
        assert data["result_content"] is not None

    def test_get_job_sync_skips_terminal(
        self, client: TestClient, completed_job: Job
    ):
        """Test that sync=true skips polling for terminal state jobs."""
        response = client.get(f"/api/v1/jobs/{completed_job.id}?sync=true")
        assert response.status_code == 200
        data = response.json()
        # Should still be completed (sync skipped)
        assert data["status"] == "completed"

    def test_get_job_without_sync(self, client: TestClient, test_job: Job):
        """Test that without sync=true, the job status is returned as-is."""
        response = client.get(f"/api/v1/jobs/{test_job.id}")
        assert response.status_code == 200
        data = response.json()
        # Should remain pending since we didn't sync
        assert data["status"] == "pending"


class TestCancelJob:
    """Tests for POST /v1/jobs/{id}/cancel endpoint."""

    def test_cancel_pending_job(self, client: TestClient, test_job: Job):
        """Test cancelling a pending job."""
        response = client.post(f"/api/v1/jobs/{test_job.id}/cancel")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"
        assert data["completed_at"] is not None

    def test_cancel_job_not_found(self, client: TestClient, dev_user: User):
        """Test cancelling a non-existent job returns 404."""
        response = client.post("/api/v1/jobs/99999/cancel")
        assert response.status_code == 404

    def test_cancel_completed_job_returns_400(
        self, client: TestClient, completed_job: Job
    ):
        """Test that cancelling a completed job returns 400."""
        response = client.post(f"/api/v1/jobs/{completed_job.id}/cancel")
        assert response.status_code == 400
        assert "terminal" in response.json()["detail"].lower()

    def test_cancel_job_without_langflow_id(
        self, client: TestClient, session: Session, test_message: ChatMessage
    ):
        """Test cancelling a job that has no langflow_job_id (still pending)."""
        job = Job(
            chat_message_id=test_message.id,
            flow_id="mock-flow-1",
            status=JobStatus.PENDING.value,
            langflow_job_id=None,
        )
        session.add(job)
        session.commit()
        session.refresh(job)

        response = client.post(f"/api/v1/jobs/{job.id}/cancel")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"


class TestJobOwnership:
    """Tests for job ownership verification."""

    def test_get_job_forbidden_for_other_user(
        self, session: Session, test_job: Job
    ):
        """Test that a user cannot access another user's job."""
        from app.api.deps import get_current_user, get_db
        from app.main import app

        # Create another user
        other_user = User(
            email="other@example.com",
            username="other-user",
            full_name="Other User",
        )
        session.add(other_user)
        session.commit()
        session.refresh(other_user)

        def get_other_user():
            return other_user

        def get_session_override():
            return session

        app.dependency_overrides[get_current_user] = get_other_user
        app.dependency_overrides[get_db] = get_session_override

        other_client = TestClient(app)
        response = other_client.get(f"/api/v1/jobs/{test_job.id}")
        assert response.status_code == 403

        app.dependency_overrides.clear()
