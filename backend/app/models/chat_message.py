"""
ChatMessage model and related schemas.

This module contains:
- ChatMessage database model (table=True)
- ChatMessageBase, ChatMessageCreate: Input schemas
- ChatMessagePublic, ChatMessagesPublic: Output schemas
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Literal, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.chat import Chat


# Valid roles for chat messages
MessageRole = Literal["user", "assistant"]


class ChatMessageBase(SQLModel):
    """Shared properties for ChatMessage."""
    content: str = Field(min_length=1, max_length=10000)
    role: str = Field(max_length=20)  # "user" or "assistant"


class ChatMessageCreate(ChatMessageBase):
    """Properties to receive on message creation."""
    pass


class ChatMessage(ChatMessageBase, table=True):
    """ChatMessage database model."""
    __tablename__ = "chat_message"

    id: int | None = Field(default=None, primary_key=True)
    chat_id: int = Field(foreign_key="chat.id", nullable=False, ondelete="CASCADE")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationship
    chat: Optional["Chat"] = Relationship(back_populates="messages")


class ChatMessagePublic(ChatMessageBase):
    """Properties to return via API."""
    id: int
    chat_id: int
    created_at: datetime


class ChatMessagesPublic(SQLModel):
    """Paginated list of chat messages."""
    data: list[ChatMessagePublic]
    count: int
