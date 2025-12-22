"""GraphQL User type."""

from datetime import datetime
from typing import TYPE_CHECKING

import strawberry

if TYPE_CHECKING:
    from app.models import User as UserModel


@strawberry.type
class UserType:
    """GraphQL representation of a User."""

    id: int
    email: str
    username: str | None
    full_name: str | None
    active: bool
    admin: bool
    created_at: datetime
    last_login: datetime

    @classmethod
    def from_orm(cls, user: "UserModel") -> "UserType":
        """Create UserType from SQLModel User."""
        return cls(
            id=user.id,
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            active=user.active,
            admin=user.admin,
            created_at=user.created_at,
            last_login=user.last_login,
        )
