"""
End-to-end job lifecycle integration tests.

Tests the complete flow: message send -> job creation -> LangFlow background
execution -> result appears in chat. Uses MockLangflowClient.
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models import Chat, User


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
        title="Lifecycle Test Chat",
        user_id=dev_user.id,
    )
    session.add(chat)
    session.commit()
    session.refresh(chat)
    return chat


def create_test_chat(client: TestClient) -> dict:
    """Helper to create a chat via the API."""
    response = client.post(
        "/api/v1/chats/",
        json={"title": "E2E Test Chat"},
    )
    assert response.status_code == 200
    return response.json()


class TestJobLifecycleHappyPath:
    """E2E: user sends message, job is created, LangFlow executes, result in chat."""

    def test_full_lifecycle(
        self, client: TestClient, session: Session, test_chat: Chat
    ):
        """
        Complete happy path: message -> job created -> poll shows completed
        -> result in chat messages.
        """
        chat_id = test_chat.id

        # 1. Send message via job endpoint
        response = client.post(
            f"/api/v1/chats/{chat_id}/messages/job",
            json={"content": "What is enterprise architecture?"},
        )
        assert response.status_code == 200
        job = response.json()
        assert job["status"] in ("pending", "in_progress")
        job_id = job["id"]
        assert job["flow_id"] is not None

        # 2. Poll for job status with sync (mock client returns completed)
        response = client.get(f"/api/v1/jobs/{job_id}?sync=true")
        assert response.status_code == 200
        job = response.json()
        assert job["status"] == "completed"
        assert job["result_content"] is not None
        assert len(job["result_content"]) > 0

        # 3. Verify messages were created in the chat
        response = client.get(f"/api/v1/chats/{chat_id}/messages/")
        assert response.status_code == 200
        messages = response.json()
        assert messages["count"] >= 2  # user message + assistant message

        # Find the user and assistant messages
        roles = [m["role"] for m in messages["data"]]
        assert "user" in roles
        assert "assistant" in roles

    def test_job_response_includes_required_fields(
        self, client: TestClient, test_chat: Chat
    ):
        """Verify job response contains all fields needed by frontend polling."""
        response = client.post(
            f"/api/v1/chats/{test_chat.id}/messages/job",
            json={"content": "Test query"},
        )
        data = response.json()
        assert "id" in data
        assert "status" in data
        assert "chat_message_id" in data
        assert "langflow_job_id" in data
        assert "flow_id" in data
        assert "created_at" in data


class TestJobCancellation:
    """E2E: user cancels an in-progress job, cancellation reflected in chat."""

    def test_cancel_in_progress_job(
        self, client: TestClient, session: Session, test_chat: Chat
    ):
        """Create a job, cancel it, verify status is cancelled."""
        chat_id = test_chat.id

        # Create job
        response = client.post(
            f"/api/v1/chats/{chat_id}/messages/job",
            json={"content": "Long running query"},
        )
        assert response.status_code == 200
        job_id = response.json()["id"]

        # Cancel the job
        response = client.post(f"/api/v1/jobs/{job_id}/cancel")
        assert response.status_code == 200
        cancelled = response.json()
        assert cancelled["status"] == "cancelled"
        assert cancelled["completed_at"] is not None

    def test_cancel_already_terminal_returns_400(
        self, client: TestClient, session: Session, test_chat: Chat
    ):
        """Cancelling a completed job returns 400 (already terminal)."""
        chat_id = test_chat.id

        # Create job
        response = client.post(
            f"/api/v1/chats/{chat_id}/messages/job",
            json={"content": "Quick query"},
        )
        job_id = response.json()["id"]

        # Sync to complete the job (mock returns completed)
        client.get(f"/api/v1/jobs/{job_id}?sync=true")

        # Try to cancel the completed job
        response = client.post(f"/api/v1/jobs/{job_id}/cancel")
        assert response.status_code == 400
        assert "terminal" in response.json()["detail"].lower()


class TestPageRefreshRecovery:
    """E2E: page refresh during active job resumes polling and shows result."""

    def test_active_job_endpoint_returns_in_flight_job(
        self, client: TestClient, session: Session, test_chat: Chat
    ):
        """
        After creating a job, GET /chats/{id}/active-job returns the
        in-flight job for page refresh recovery.
        """
        chat_id = test_chat.id

        # Create job (mock returns in_progress status since submit succeeds)
        response = client.post(
            f"/api/v1/chats/{chat_id}/messages/job",
            json={"content": "In-flight query"},
        )
        assert response.status_code == 200
        job_id = response.json()["id"]

        # Check for active job (simulates page refresh)
        response = client.get(f"/api/v1/chats/{chat_id}/active-job")
        assert response.status_code == 200
        active_job = response.json()
        assert active_job["id"] == job_id
        assert active_job["status"] in ("pending", "in_progress")

    def test_no_active_job_after_completion(
        self, client: TestClient, session: Session, test_chat: Chat
    ):
        """After a job completes, active-job returns 404."""
        chat_id = test_chat.id

        # Create and complete a job
        response = client.post(
            f"/api/v1/chats/{chat_id}/messages/job",
            json={"content": "Quick query"},
        )
        job_id = response.json()["id"]

        # Sync to complete
        client.get(f"/api/v1/jobs/{job_id}?sync=true")

        # No active job should exist
        response = client.get(f"/api/v1/chats/{chat_id}/active-job")
        assert response.status_code == 404


class TestJobErrorHandling:
    """E2E: failed job shows error with expandable details and retry."""

    def test_job_not_found(self, client: TestClient, dev_user: User):
        """GET /jobs/99999 returns 404."""
        response = client.get("/api/v1/jobs/99999")
        assert response.status_code == 404

    def test_submit_error_creates_failed_job(
        self, client: TestClient, session: Session, test_chat: Chat, monkeypatch
    ):
        """
        When LangFlow submission fails, the job is created with status=failed
        and error_message is populated.
        """
        from app.services.langflow.mock_client import MockLangflowClient
        from app.services.langflow.client import LangflowError
        from app.api.routes.v1 import chat_messages

        class SubmitErrorClient(MockLangflowClient):
            async def submit_workflow(self, flow_id, inputs, session_id=None):
                raise LangflowError("V2 workflow submission failed", status_code=500)

        monkeypatch.setattr(
            chat_messages, "get_langflow_client", lambda: SubmitErrorClient()
        )

        response = client.post(
            f"/api/v1/chats/{test_chat.id}/messages/job",
            json={"content": "This will fail"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert "V2 workflow submission failed" in data["error_message"]

    def test_failed_job_preserves_messages(
        self, client: TestClient, session: Session, test_chat: Chat, monkeypatch
    ):
        """Even when a job fails, user and assistant messages are preserved."""
        from app.services.langflow.mock_client import MockLangflowClient
        from app.services.langflow.client import LangflowError
        from app.api.routes.v1 import chat_messages

        class SubmitErrorClient(MockLangflowClient):
            async def submit_workflow(self, flow_id, inputs, session_id=None):
                raise LangflowError("Submit failed", status_code=500)

        monkeypatch.setattr(
            chat_messages, "get_langflow_client", lambda: SubmitErrorClient()
        )

        client.post(
            f"/api/v1/chats/{test_chat.id}/messages/job",
            json={"content": "Error query"},
        )

        # Messages should still exist
        response = client.get(f"/api/v1/chats/{test_chat.id}/messages/")
        assert response.status_code == 200
        messages = response.json()
        assert messages["count"] >= 2  # user + placeholder assistant
