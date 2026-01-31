"""Tests for the Chat API endpoints."""

import json

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from sqlmodel import Session

from app.models import Chat, ChatMessage, User
from app.api.deps import get_current_user
from app.main import app


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


class TestChatCRUD:
    """Tests for Chat CRUD operations."""

    def test_create_chat(self, client: TestClient, dev_user: User):
        """Test creating a new chat."""
        response = client.post(
            "/api/v1/chats/",
            json={"title": "New Chat"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "New Chat"
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_chat_empty_title(self, client: TestClient, dev_user: User):
        """Test creating a chat with empty title fails."""
        response = client.post(
            "/api/v1/chats/",
            json={"title": ""},
        )
        assert response.status_code == 422

    def test_read_chats(self, client: TestClient, test_chat: Chat):
        """Test listing chats."""
        response = client.get("/api/v1/chats/")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "count" in data
        assert data["count"] >= 1
        assert len(data["data"]) >= 1

    def test_read_chat_by_id(self, client: TestClient, test_chat: Chat):
        """Test getting a specific chat."""
        response = client.get(f"/api/v1/chats/{test_chat.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_chat.id
        assert data["title"] == test_chat.title

    def test_read_chat_not_found(self, client: TestClient, dev_user: User):
        """Test getting a non-existent chat returns 404."""
        response = client.get("/api/v1/chats/99999")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_update_chat(self, client: TestClient, test_chat: Chat):
        """Test updating a chat."""
        response = client.put(
            f"/api/v1/chats/{test_chat.id}",
            json={"title": "Updated Title"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Title"

    def test_update_chat_not_found(self, client: TestClient, dev_user: User):
        """Test updating a non-existent chat returns 404."""
        response = client.put(
            "/api/v1/chats/99999",
            json={"title": "Updated Title"},
        )
        assert response.status_code == 404

    def test_delete_chat(
        self, client: TestClient, session: Session, test_chat: Chat
    ):
        """Test deleting a chat."""
        chat_id = test_chat.id
        response = client.delete(f"/api/v1/chats/{chat_id}")
        assert response.status_code == 200
        assert "deleted" in response.json()["message"].lower()

        # Verify chat is deleted
        deleted_chat = session.get(Chat, chat_id)
        assert deleted_chat is None

    def test_delete_chat_not_found(self, client: TestClient, dev_user: User):
        """Test deleting a non-existent chat returns 404."""
        response = client.delete("/api/v1/chats/99999")
        assert response.status_code == 404


class TestChatMessages:
    """Tests for Chat Message operations."""

    def test_create_message(self, client: TestClient, test_chat: Chat):
        """Test creating a new message."""
        response = client.post(
            f"/api/v1/chats/{test_chat.id}/messages/",
            json={"content": "Hello, world!", "role": "user"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "Hello, world!"
        assert data["role"] == "user"
        assert data["chat_id"] == test_chat.id

    def test_create_message_assistant(self, client: TestClient, test_chat: Chat):
        """Test creating an assistant message."""
        response = client.post(
            f"/api/v1/chats/{test_chat.id}/messages/",
            json={"content": "Hello! How can I help?", "role": "assistant"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "assistant"

    def test_create_message_invalid_role(self, client: TestClient, test_chat: Chat):
        """Test creating a message with invalid role fails."""
        response = client.post(
            f"/api/v1/chats/{test_chat.id}/messages/",
            json={"content": "Hello!", "role": "invalid"},
        )
        # Pydantic validates role via Literal type, returns 422
        assert response.status_code == 422

    def test_create_message_chat_not_found(
        self, client: TestClient, dev_user: User
    ):
        """Test creating a message in non-existent chat returns 404."""
        response = client.post(
            "/api/v1/chats/99999/messages/",
            json={"content": "Hello!", "role": "user"},
        )
        assert response.status_code == 404

    def test_read_messages(
        self, client: TestClient, session: Session, test_chat: Chat
    ):
        """Test listing messages in a chat."""
        # Create some messages
        messages = [
            ChatMessage(chat_id=test_chat.id, content="Message 1", role="user"),
            ChatMessage(chat_id=test_chat.id, content="Message 2", role="assistant"),
        ]
        for msg in messages:
            session.add(msg)
        session.commit()

        response = client.get(f"/api/v1/chats/{test_chat.id}/messages/")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "count" in data
        assert data["count"] >= 2
        assert len(data["data"]) >= 2

    def test_read_messages_chat_not_found(
        self, client: TestClient, dev_user: User
    ):
        """Test listing messages in non-existent chat returns 404."""
        response = client.get("/api/v1/chats/99999/messages/")
        assert response.status_code == 404

    def test_delete_message(
        self, client: TestClient, session: Session, test_chat: Chat
    ):
        """Test deleting a message."""
        # Create a message
        message = ChatMessage(
            chat_id=test_chat.id, content="To be deleted", role="user"
        )
        session.add(message)
        session.commit()
        session.refresh(message)

        response = client.delete(
            f"/api/v1/chats/{test_chat.id}/messages/{message.id}"
        )
        assert response.status_code == 200
        assert "deleted" in response.json()["message"].lower()

        # Verify message is deleted
        deleted_message = session.get(ChatMessage, message.id)
        assert deleted_message is None

    def test_delete_message_not_found(
        self, client: TestClient, test_chat: Chat
    ):
        """Test deleting a non-existent message returns 404."""
        response = client.delete(
            f"/api/v1/chats/{test_chat.id}/messages/99999"
        )
        assert response.status_code == 404

    def test_delete_chat_cascades_messages(
        self, client: TestClient, session: Session, dev_user: User
    ):
        """Test that deleting a chat also deletes all its messages."""
        # Create a chat with messages
        chat = Chat(title="Chat with messages", user_id=dev_user.id)
        session.add(chat)
        session.commit()
        session.refresh(chat)

        messages = [
            ChatMessage(chat_id=chat.id, content="Message 1", role="user"),
            ChatMessage(chat_id=chat.id, content="Message 2", role="assistant"),
        ]
        for msg in messages:
            session.add(msg)
        session.commit()

        message_ids = [msg.id for msg in messages]

        # Delete the chat
        response = client.delete(f"/api/v1/chats/{chat.id}")
        assert response.status_code == 200

        # Verify messages are also deleted
        for msg_id in message_ids:
            deleted_message = session.get(ChatMessage, msg_id)
            assert deleted_message is None


class TestMessageStreaming:
    """Tests for streaming message endpoint."""

    def test_stream_message_chat_not_found(
        self, client: TestClient, dev_user: User
    ):
        """Test streaming to non-existent chat returns 404."""
        response = client.post(
            "/api/v1/chats/99999/messages/stream",
            json={"content": "Hello!"},
        )
        assert response.status_code == 404

    def test_stream_message_returns_sse_format(
        self, client: TestClient, test_chat: Chat
    ):
        """Test streaming endpoint returns SSE formatted response."""
        response = client.post(
            f"/api/v1/chats/{test_chat.id}/messages/stream",
            json={"content": "Hello, AI!"},
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

        # Parse SSE events from response
        events = []
        for line in response.text.split("\n\n"):
            if line.startswith("data: "):
                data = json.loads(line[6:])
                events.append(data)

        # Should have at least content and done events
        assert len(events) >= 1
        event_types = [e["type"] for e in events]
        # Last event should be done
        assert events[-1]["type"] == "done"

    def test_stream_message_saves_user_message(
        self, client: TestClient, session: Session, test_chat: Chat
    ):
        """Test that user message is saved before streaming."""
        # Consume the streaming response
        client.post(
            f"/api/v1/chats/{test_chat.id}/messages/stream",
            json={"content": "Test message to save"},
        )

        # Check that user message was saved
        messages = session.query(ChatMessage).filter(
            ChatMessage.chat_id == test_chat.id,
            ChatMessage.role == "user"
        ).all()

        assert len(messages) == 1
        assert messages[0].content == "Test message to save"

    def test_stream_message_saves_assistant_response(
        self, client: TestClient, session: Session, test_chat: Chat
    ):
        """Test that assistant response is saved after streaming."""
        # Consume the streaming response
        client.post(
            f"/api/v1/chats/{test_chat.id}/messages/stream",
            json={"content": "Hello!"},
        )

        # Check that assistant message was saved
        messages = session.query(ChatMessage).filter(
            ChatMessage.chat_id == test_chat.id,
            ChatMessage.role == "assistant"
        ).all()

        assert len(messages) == 1
        # Mock client returns canned responses
        assert len(messages[0].content) > 0

    def test_stream_message_langflow_error(
        self, client: TestClient, session: Session, test_chat: Chat, monkeypatch
    ):
        """Test that Langflow errors return SSE error event."""
        from app.services.langflow.mock_client import MockLangflowClient
        from app.api.routes.v1 import chat_messages

        # Create a mock client that simulates errors
        error_client = MockLangflowClient(
            simulate_error=True,
            error_message="Simulated Langflow connection error"
        )

        # Patch the function where it's imported (in the route module)
        monkeypatch.setattr(chat_messages, "get_langflow_client", lambda: error_client)

        response = client.post(
            f"/api/v1/chats/{test_chat.id}/messages/stream",
            json={"content": "This will fail"},
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

        # Parse SSE events - should contain error event
        events = []
        for line in response.text.split("\n\n"):
            if line.startswith("data: "):
                data = json.loads(line[6:])
                events.append(data)

        # Should have an error event
        error_events = [e for e in events if e.get("type") == "error"]
        assert len(error_events) == 1
        assert "Simulated Langflow connection error" in error_events[0].get("error", "")

    def test_stream_message_langflow_error_still_saves_user_message(
        self, client: TestClient, session: Session, test_chat: Chat, monkeypatch
    ):
        """Test that user message is saved even when Langflow fails."""
        from app.services.langflow.mock_client import MockLangflowClient
        from app.api.routes.v1 import chat_messages

        # Create a mock client that simulates errors
        error_client = MockLangflowClient(simulate_error=True)
        monkeypatch.setattr(chat_messages, "get_langflow_client", lambda: error_client)

        # Consume the streaming response (will get error)
        client.post(
            f"/api/v1/chats/{test_chat.id}/messages/stream",
            json={"content": "Message before error"},
        )

        # Refresh session to get updated data
        session.expire_all()

        # Check that user message was still saved
        user_messages = session.query(ChatMessage).filter(
            ChatMessage.chat_id == test_chat.id,
            ChatMessage.role == "user"
        ).all()

        assert len(user_messages) == 1
        assert user_messages[0].content == "Message before error"

        # But no assistant message should be saved (since Langflow failed)
        assistant_messages = session.query(ChatMessage).filter(
            ChatMessage.chat_id == test_chat.id,
            ChatMessage.role == "assistant"
        ).all()
        assert len(assistant_messages) == 0


@pytest.fixture
def other_user(session: Session) -> User:
    """
    Create a second user for authorization testing.

    This user is different from dev_user and should NOT have access
    to dev_user's chats.
    """
    user = User(
        email="other-user@example.com",
        username="other-user",
        full_name="Other User",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture
def other_user_client(session: Session, other_user: User) -> TestClient:
    """
    Create a test client that authenticates as other_user.

    This is used to test authorization - other_user should NOT be able
    to access dev_user's chats.
    """
    from app.api.deps import get_db

    def get_other_user():
        return other_user

    def get_session_override():
        return session

    app.dependency_overrides[get_current_user] = get_other_user
    app.dependency_overrides[get_db] = get_session_override

    client = TestClient(app)
    yield client

    # Clean up: restore to original overrides
    app.dependency_overrides.clear()


class TestChatAuthorization:
    """Tests for chat authorization - verify users cannot access other users' chats."""

    def test_read_chat_forbidden_for_other_user(
        self, other_user_client: TestClient, test_chat: Chat, other_user: User
    ):
        """Test that a user cannot read another user's chat (403 Forbidden)."""
        response = other_user_client.get(f"/api/v1/chats/{test_chat.id}")
        assert response.status_code == 403
        assert "permission" in response.json()["detail"].lower()

    def test_update_chat_forbidden_for_other_user(
        self, other_user_client: TestClient, test_chat: Chat, other_user: User
    ):
        """Test that a user cannot update another user's chat (403 Forbidden)."""
        response = other_user_client.put(
            f"/api/v1/chats/{test_chat.id}",
            json={"title": "Hacked Title"},
        )
        assert response.status_code == 403
        assert "permission" in response.json()["detail"].lower()

    def test_delete_chat_forbidden_for_other_user(
        self, other_user_client: TestClient, test_chat: Chat, other_user: User
    ):
        """Test that a user cannot delete another user's chat (403 Forbidden)."""
        response = other_user_client.delete(f"/api/v1/chats/{test_chat.id}")
        assert response.status_code == 403
        assert "permission" in response.json()["detail"].lower()

    def test_read_messages_forbidden_for_other_user(
        self, other_user_client: TestClient, test_chat: Chat, other_user: User
    ):
        """Test that a user cannot read another user's chat messages (403 Forbidden)."""
        response = other_user_client.get(f"/api/v1/chats/{test_chat.id}/messages/")
        assert response.status_code == 403
        assert "permission" in response.json()["detail"].lower()

    def test_create_message_forbidden_for_other_user(
        self, other_user_client: TestClient, test_chat: Chat, other_user: User
    ):
        """Test that a user cannot create messages in another user's chat (403 Forbidden)."""
        response = other_user_client.post(
            f"/api/v1/chats/{test_chat.id}/messages/",
            json={"content": "Malicious message", "role": "user"},
        )
        assert response.status_code == 403
        assert "permission" in response.json()["detail"].lower()

    def test_stream_message_forbidden_for_other_user(
        self, other_user_client: TestClient, test_chat: Chat, other_user: User
    ):
        """Test that a user cannot stream messages to another user's chat (403 Forbidden)."""
        response = other_user_client.post(
            f"/api/v1/chats/{test_chat.id}/messages/stream",
            json={"content": "Malicious stream"},
        )
        assert response.status_code == 403
        assert "permission" in response.json()["detail"].lower()

    def test_delete_message_forbidden_for_other_user(
        self,
        other_user_client: TestClient,
        session: Session,
        test_chat: Chat,
        other_user: User,
    ):
        """Test that a user cannot delete another user's chat message (403 Forbidden)."""
        # Create a message in the chat
        message = ChatMessage(
            chat_id=test_chat.id, content="Private message", role="user"
        )
        session.add(message)
        session.commit()
        session.refresh(message)

        response = other_user_client.delete(
            f"/api/v1/chats/{test_chat.id}/messages/{message.id}"
        )
        assert response.status_code == 403
        assert "permission" in response.json()["detail"].lower()

    def test_list_chats_only_shows_own_chats(
        self,
        other_user_client: TestClient,
        session: Session,
        test_chat: Chat,
        other_user: User,
    ):
        """Test that listing chats only shows the current user's chats, not others'."""
        # Create a chat for other_user
        other_chat = Chat(title="Other User's Chat", user_id=other_user.id)
        session.add(other_chat)
        session.commit()

        response = other_user_client.get("/api/v1/chats/")
        assert response.status_code == 200
        data = response.json()

        # Should only see other_user's chat, not test_chat (which belongs to dev_user)
        chat_ids = [chat["id"] for chat in data["data"]]
        assert other_chat.id in chat_ids
        assert test_chat.id not in chat_ids
