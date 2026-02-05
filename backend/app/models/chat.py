"""
Chat model and related schemas.

This module contains:
- Chat database model (table=True)
- ChatBase, ChatCreate, ChatUpdate: Input schemas
- ChatPublic, ChatsPublic: Output schemas
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.chat_message import ChatMessage


class ChatBase(SQLModel):
    """Shared properties for Chat."""
    title: str = Field(min_length=1, max_length=255)


class ChatCreate(ChatBase):
    """Properties to receive on chat creation."""
    pass


class ChatUpdate(SQLModel):
    """Properties to receive on chat update."""
    title: str | None = Field(default=None, min_length=1, max_length=255)


class Chat(ChatBase, table=True):
    """Chat database model."""
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", nullable=False, ondelete="CASCADE")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )

    # Relationships
    user: Optional["User"] = Relationship(back_populates="chats")
    messages: list["ChatMessage"] = Relationship(
        back_populates="chat",
        cascade_delete=True,
    )


class ChatPublic(ChatBase):
    """Properties to return via API."""
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime


class ChatsPublic(SQLModel):
    """Paginated list of chats."""
    data: list[ChatPublic]
    count: int
