"""
Models package for database models and schemas.

This package contains SQLModel database models and Pydantic schemas:
- User models and schemas
- Item models and schemas
- Shared base models

All models are re-exported here for backward compatibility.
Import from this module for convenience:

    from app.models import User, Item, Message

Or import from specific modules for clarity:

    from app.models.user import User, UserPublic
    from app.models.item import Item, ItemCreate
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

__all__ = [
    # SQLModel for migrations
    "SQLModel",
    # Base
    "Message",
    # User
    "User",
    "UserBase",
    "UserPublic",
    "UsersPublic",
    "UserUpdate",
    # Item
    "Item",
    "ItemBase",
    "ItemCreate",
    "ItemPublic",
    "ItemsPublic",
    "ItemUpdate",
]
