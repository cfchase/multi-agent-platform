"""DataLoaders for batching and caching GraphQL queries.

DataLoaders solve the N+1 problem by batching multiple individual loads
into a single database query.
"""

from typing import Any

from sqlmodel import Session, select
from strawberry.dataloader import DataLoader

from app.models import User
from app.graphql_api.types.user import UserType


async def load_users_batch(keys: list[int], session: Session) -> list[UserType | None]:
    """Batch load users by their IDs.

    Args:
        keys: List of user IDs to load
        session: Database session

    Returns:
        List of UserType objects in the same order as keys
    """
    statement = select(User).where(User.id.in_(keys))
    users = session.exec(statement).all()

    # Create a mapping for O(1) lookup
    user_map = {user.id: UserType.from_orm(user) for user in users}

    # Return users in the same order as keys, with None for missing
    return [user_map.get(key) for key in keys]


def create_loaders(session: Session) -> dict[str, DataLoader[int, Any]]:
    """Create DataLoaders for the current request.

    A new set of loaders should be created for each request to ensure
    proper caching boundaries.

    Args:
        session: Database session for this request

    Returns:
        Dictionary of named DataLoaders
    """
    return {
        "users": DataLoader(
            load_fn=lambda keys: load_users_batch(keys, session)
        ),
    }
