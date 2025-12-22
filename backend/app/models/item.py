"""
Item model and related schemas.

This module contains:
- Item database model (table=True)
- ItemBase, ItemCreate, ItemUpdate: Input schemas
- ItemPublic, ItemsPublic: Output schemas
"""

from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.user import User


class ItemBase(SQLModel):
    """Shared properties for Item."""
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


class ItemCreate(ItemBase):
    """Properties to receive on item creation."""
    pass


class ItemUpdate(ItemBase):
    """Properties to receive on item update."""
    title: str | None = Field(default=None, min_length=1, max_length=255)  # type: ignore


class Item(ItemBase, table=True):
    """Item database model."""
    id: int | None = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="user.id", nullable=False, ondelete="CASCADE")
    owner: Optional["User"] = Relationship(back_populates="items")


class ItemPublic(ItemBase):
    """Properties to return via API."""
    id: int
    owner_id: int


class ItemsPublic(SQLModel):
    """Paginated list of items."""
    data: list[ItemPublic]
    count: int
