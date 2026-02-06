"""
Models package for database models and schemas.

This package contains SQLModel database models and Pydantic schemas:
- User models and schemas
- Item models and schemas
- Chat models and schemas
- ChatMessage models and schemas
- UserIntegration models and schemas
- Shared base models

All models are re-exported here for backward compatibility.
Import from this module for convenience:

    from app.models import User, Item, Chat, ChatMessage, UserIntegration, Message

Or import from specific modules for clarity:

    from app.models.user import User, UserPublic
    from app.models.item import Item, ItemCreate
    from app.models.chat import Chat, ChatCreate
    from app.models.chat_message import ChatMessage, ChatMessageCreate
    from app.models.user_integration import UserIntegration
"""

# Re-export SQLModel for Alembic migrations
from sqlmodel import SQLModel

# Base models
from app.models.base import Message

# User models
from app.models.user import (
    User,
    UserBase,
    UserPublic,
    UserMeResponse,
    IntegrationStatus,
    UsersPublic,
    UserUpdate,
)

# Item models
from app.models.item import (
    Item,
    ItemBase,
    ItemCreate,
    ItemPublic,
    ItemsPublic,
    ItemUpdate,
)

# Chat models
from app.models.chat import (
    Chat,
    ChatBase,
    ChatCreate,
    ChatPublic,
    ChatsPublic,
    ChatUpdate,
)

# ChatMessage models
from app.models.chat_message import (
    ChatMessage,
    ChatMessageBase,
    ChatMessageCreate,
    ChatMessagePublic,
    ChatMessagesPublic,
)

# Integration models
from app.models.user_integration import (
    UserIntegration,
    UserIntegrationPublic,
)

# OAuth state model
from app.models.oauth_state import (
    OAuthState,
    STATE_EXPIRATION_MINUTES,
)

__all__ = [
    # SQLModel for migrations
    "SQLModel",
    # Base
    "Message",
    # User
    "User",
    "UserBase",
    "UserPublic",
    "UserMeResponse",
    "IntegrationStatus",
    "UsersPublic",
    "UserUpdate",
    # Item
    "Item",
    "ItemBase",
    "ItemCreate",
    "ItemPublic",
    "ItemsPublic",
    "ItemUpdate",
    # Chat
    "Chat",
    "ChatBase",
    "ChatCreate",
    "ChatPublic",
    "ChatsPublic",
    "ChatUpdate",
    # ChatMessage
    "ChatMessage",
    "ChatMessageBase",
    "ChatMessageCreate",
    "ChatMessagePublic",
    "ChatMessagesPublic",
    # Integration
    "UserIntegration",
    "UserIntegrationPublic",
    # OAuth State
    "OAuthState",
    "STATE_EXPIRATION_MINUTES",
]
