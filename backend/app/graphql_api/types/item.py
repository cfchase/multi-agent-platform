"""GraphQL Item type with owner relationship."""

from typing import TYPE_CHECKING, Annotated

import strawberry
from strawberry.types import Info

if TYPE_CHECKING:
    from app.models import Item as ItemModel


@strawberry.type
class ItemType:
    """GraphQL representation of an Item with relationships."""

    id: int
    title: str
    description: str | None
    owner_id: int

    @strawberry.field
    async def owner(self, info: Info) -> Annotated["UserType", strawberry.lazy(".user")]:
        """Resolve the owner relationship using DataLoader."""
        loaders = info.context["loaders"]
        return await loaders["users"].load(self.owner_id)

    @classmethod
    def from_orm(cls, item: "ItemModel") -> "ItemType":
        """Create ItemType from SQLModel Item."""
        return cls(
            id=item.id,
            title=item.title,
            description=item.description,
            owner_id=item.owner_id,
        )
