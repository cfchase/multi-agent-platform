"""
User model and related schemas.

This module contains:
- User database model (table=True)
- UserBase, UserUpdate: Input schemas
- UserPublic, UsersPublic: Output schemas
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.item import Item


class UserBase(SQLModel):
    """
    User model for OAuth proxy authentication.

    All users are authenticated via OAuth proxy which sets:
    - X-Forwarded-User or X-Forwarded-Preferred-Username: username from OAuth provider
    - X-Forwarded-Email: email from OAuth provider
    """
    email: str = Field(max_length=255, unique=True, index=True)
    username: str | None = Field(default=None, max_length=255, unique=True, index=True)
    full_name: str | None = Field(default=None, max_length=255)
    active: bool = Field(default=True)
    admin: bool = Field(default=False)


class UserUpdate(SQLModel):
    """Properties to receive via API on update, all are optional."""
    full_name: str | None = Field(default=None, max_length=255)
    active: bool | None = None
    admin: bool | None = None


class User(UserBase, table=True):
    """
    User table for OAuth-authenticated users.

    Users are automatically created from OAuth proxy headers.
    Admin access is controlled by the 'admin' boolean field.
    """
    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_login: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    items: list["Item"] = Relationship(back_populates="owner", cascade_delete=True)

    def __str__(self) -> str:
        """Display format for admin dropdowns and references."""
        if self.full_name:
            return f"{self.full_name} ({self.username})"
        return self.username or self.email


class UserPublic(UserBase):
    """Properties to return via API."""
    id: int
    created_at: datetime
    last_login: datetime


class UsersPublic(SQLModel):
    """Paginated list of users."""
    data: list[UserPublic]
    count: int
