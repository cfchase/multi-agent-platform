"""
CRUD operations for User model.
"""

from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models import User


def get_user_by_username(*, session: Session, username: str) -> User | None:
    """
    Get a user by username.

    Args:
        session: Database session
        username: Username to search for

    Returns:
        User if found, None otherwise
    """
    statement = select(User).where(User.username == username)
    return session.exec(statement).first()


def create_user(
    *,
    session: Session,
    username: str,
    email: str,
) -> User:
    """
    Create a new user.

    Args:
        session: Database session
        username: User's username (from OAuth X-Forwarded-Preferred-Username header)
        email: User's email (from OAuth X-Forwarded-Email header)

    Returns:
        Created User object
    """
    user = User(
        username=username,
        email=email,
        active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def update_user_last_login(*, session: Session, user: User) -> User:
    """
    Update the last_login timestamp for a user.

    Args:
        session: Database session
        user: User object to update

    Returns:
        Updated User object
    """
    user.last_login = datetime.now(timezone.utc)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def get_or_create_user(
    *,
    session: Session,
    username: str,
    email: str,
) -> tuple[User, bool]:
    """
    Get an existing user or create a new one if it doesn't exist.
    Updates last_login timestamp for existing users.

    Args:
        session: Database session
        username: User's username (from OAuth header, used as unique identifier)
        email: User's email (from OAuth X-Forwarded-Email header)

    Returns:
        Tuple of (User object, created boolean)
        - created=True if user was created
        - created=False if user already existed
    """
    user = get_user_by_username(session=session, username=username)

    if user:
        # User exists, update email in case it changed and update last login
        user.email = email
        update_user_last_login(session=session, user=user)
        return user, False

    # User doesn't exist, create it
    user = create_user(
        session=session,
        username=username,
        email=email,
    )
    return user, True
