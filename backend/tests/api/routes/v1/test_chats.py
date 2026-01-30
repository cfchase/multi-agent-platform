"""Tests for the Chat API endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models import Chat, ChatMessage, User


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
        assert response.status_code == 400
        assert "role" in response.json()["detail"].lower()

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
