"""GraphQL Schema definition.

This module defines the GraphQL schema with Query type and security extensions.
"""

from typing import Sequence

import strawberry
from sqlmodel import Session, select, func, col
from strawberry.types import Info
from strawberry.extensions import QueryDepthLimiter, MaxTokensLimiter

from app.models import Item, User
from app.graphql_api.types import ItemType, UserType


@strawberry.type
class Query:
    """Root Query type for GraphQL API."""

    @strawberry.field
    def items(
        self,
        info: Info,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        sort_by: str = "id",
        sort_order: str = "asc",
    ) -> list[ItemType]:
        """Get a list of items with optional filtering and pagination.

        Args:
            skip: Number of items to skip (for pagination)
            limit: Maximum number of items to return
            search: Optional search term for title/description
            sort_by: Field to sort by (id, title)
            sort_order: Sort direction (asc, desc)

        Returns:
            List of items
        """
        session: Session = info.context["session"]

        statement = select(Item)

        # Apply search filter
        if search:
            search_pattern = f"%{search}%"
            statement = statement.where(
                (col(Item.title).ilike(search_pattern))
                | (col(Item.description).ilike(search_pattern))
            )

        # Apply sorting
        sort_column = getattr(Item, sort_by, Item.id)
        if sort_order.lower() == "desc":
            statement = statement.order_by(sort_column.desc())
        else:
            statement = statement.order_by(sort_column.asc())

        # Apply pagination
        statement = statement.offset(skip).limit(limit)

        items = session.exec(statement).all()
        return [ItemType.from_orm(item) for item in items]

    @strawberry.field
    def items_count(
        self,
        info: Info,
        search: str | None = None,
    ) -> int:
        """Get total count of items (for pagination).

        Args:
            search: Optional search term to filter count

        Returns:
            Total number of items matching criteria
        """
        session: Session = info.context["session"]

        statement = select(func.count()).select_from(Item)

        if search:
            search_pattern = f"%{search}%"
            statement = statement.where(
                (col(Item.title).ilike(search_pattern))
                | (col(Item.description).ilike(search_pattern))
            )

        count = session.exec(statement).one()
        return count

    @strawberry.field
    def item(self, info: Info, id: int) -> ItemType | None:
        """Get a single item by ID.

        Args:
            id: The item ID

        Returns:
            The item if found, None otherwise
        """
        session: Session = info.context["session"]
        item = session.get(Item, id)
        return ItemType.from_orm(item) if item else None

    @strawberry.field
    def users(
        self,
        info: Info,
        skip: int = 0,
        limit: int = 100,
    ) -> list[UserType]:
        """Get a list of users with pagination.

        Args:
            skip: Number of users to skip
            limit: Maximum number of users to return

        Returns:
            List of users
        """
        session: Session = info.context["session"]

        statement = select(User).offset(skip).limit(limit)
        users = session.exec(statement).all()
        return [UserType.from_orm(user) for user in users]

    @strawberry.field
    def user(self, info: Info, id: int) -> UserType | None:
        """Get a single user by ID.

        Args:
            id: The user ID

        Returns:
            The user if found, None otherwise
        """
        session: Session = info.context["session"]
        user = session.get(User, id)
        return UserType.from_orm(user) if user else None

    @strawberry.field
    def me(self, info: Info) -> UserType | None:
        """Get the current authenticated user.

        Returns:
            The current user if authenticated, None otherwise
        """
        current_user = info.context.get("current_user")
        return UserType.from_orm(current_user) if current_user else None


# Create the schema with security extensions
schema = strawberry.Schema(
    query=Query,
    extensions=[
        QueryDepthLimiter(max_depth=10),
        MaxTokensLimiter(max_token_count=2000),
    ],
)
