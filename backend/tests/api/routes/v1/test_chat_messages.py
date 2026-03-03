"""Tests for the job-based chat message endpoint."""

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


class TestCreateJobMessage:
    """Tests for POST /v1/chats/{id}/messages/job endpoint."""

    def test_create_job_message(
        self, client: TestClient, session: Session, test_chat: Chat
    ):
        """Test creating a job-based message returns JobPublic."""
        response = client.post(
            f"/api/v1/chats/{test_chat.id}/messages/job",
            json={"content": "Hello, AI!"},
        )
        assert response.status_code == 200
        data = response.json()

        # Should return JobPublic
        assert "id" in data
        assert "status" in data
        assert "chat_message_id" in data
        assert data["status"] == "in_progress"
        assert data["langflow_job_id"] == "mock-job-123"
        assert data["flow_id"] == "mock-flow-1"

    def test_create_job_message_saves_user_message(
        self, client: TestClient, session: Session, test_chat: Chat
    ):
        """Test that user message is saved to database."""
        client.post(
            f"/api/v1/chats/{test_chat.id}/messages/job",
            json={"content": "Test user message"},
        )

        # Check user message was saved
        user_messages = (
            session.query(ChatMessage)
            .filter(
                ChatMessage.chat_id == test_chat.id,
                ChatMessage.role == "user",
            )
            .all()
        )
        assert len(user_messages) == 1
        assert user_messages[0].content == "Test user message"

    def test_create_job_message_creates_placeholder(
        self, client: TestClient, session: Session, test_chat: Chat
    ):
        """Test that a placeholder assistant message is created."""
        response = client.post(
            f"/api/v1/chats/{test_chat.id}/messages/job",
            json={"content": "Hello!"},
        )
        data = response.json()

        # Check placeholder assistant message
        assistant_msg = session.get(ChatMessage, data["chat_message_id"])
        assert assistant_msg is not None
        assert assistant_msg.role == "assistant"
        assert assistant_msg.content == ""  # placeholder

    def test_create_job_message_creates_job_record(
        self, client: TestClient, session: Session, test_chat: Chat
    ):
        """Test that a Job record is created and linked to the assistant message."""
        response = client.post(
            f"/api/v1/chats/{test_chat.id}/messages/job",
            json={"content": "Hello!"},
        )
        data = response.json()
        job_id = data["id"]

        # Verify job exists in database
        job = session.get(Job, job_id)
        assert job is not None
        assert job.status == JobStatus.IN_PROGRESS.value
        assert job.langflow_job_id == "mock-job-123"

    def test_create_job_message_sets_flow_name(
        self, client: TestClient, session: Session, test_chat: Chat
    ):
        """Test that flow_name is locked on the chat."""
        assert test_chat.flow_name is None

        client.post(
            f"/api/v1/chats/{test_chat.id}/messages/job",
            json={"content": "Hello!", "flow_name": "test-flow"},
        )

        session.expire_all()
        updated_chat = session.get(Chat, test_chat.id)
        # The mock client resolve_flow_id returns "mock-flow-1" regardless,
        # but the chat's flow_name should be set from the request
        assert updated_chat.flow_name == "test-flow"

    def test_create_job_message_chat_not_found(
        self, client: TestClient, dev_user: User
    ):
        """Test creating a job message in non-existent chat returns 404."""
        response = client.post(
            "/api/v1/chats/99999/messages/job",
            json={"content": "Hello!"},
        )
        assert response.status_code == 404

    def test_create_job_message_submit_error_results_in_failed_job(
        self, client: TestClient, session: Session, test_chat: Chat, monkeypatch
    ):
        """Test that LangFlow submission errors result in FAILED job status."""
        from app.services.langflow.mock_client import MockLangflowClient
        from app.api.routes.v1 import chat_messages

        # Create a custom mock that only errors on submit_workflow (not resolve_flow_id)
        class SubmitErrorClient(MockLangflowClient):
            async def submit_workflow(self, flow_id, inputs, session_id=None):
                from app.services.langflow.client import LangflowError
                raise LangflowError("V2 submission failed", status_code=500)

        error_client = SubmitErrorClient()
        monkeypatch.setattr(
            chat_messages, "get_langflow_client", lambda: error_client
        )

        response = client.post(
            f"/api/v1/chats/{test_chat.id}/messages/job",
            json={"content": "This will fail on submit"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert "V2 submission failed" in data["error_message"]

    def test_create_job_preserves_existing_stream(
        self, client: TestClient, test_chat: Chat
    ):
        """Test that the existing /stream endpoint still works."""
        response = client.post(
            f"/api/v1/chats/{test_chat.id}/messages/stream",
            json={"content": "Hello via stream!"},
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
