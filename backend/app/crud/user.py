"""
CRUD operations for User model.
"""

from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.models import User


def get_user_by_email(*, session: Session, email: str) -> User | None:
    """
    Get a user by email.

    Args:
        session: Database session
        email: Email to search for

    Returns:
        User if found, None otherwise
    """
    statement = select(User).where(User.email == email)
    return session.exec(statement).first()


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

    Handles the case where a user's username might change but email stays the same
    (e.g., different OAuth provider or username change in provider).

    Args:
        session: Database session
        username: User's username (from OAuth header)
        email: User's email (from OAuth X-Forwarded-Email header)

    Returns:
        Tuple of (User object, created boolean)
        - created=True if user was created
        - created=False if user already existed
    """
    # First try to find by username
    user = get_user_by_username(session=session, username=username)

    if user:
        # User exists by username, update email in case it changed
        user.email = email
        update_user_last_login(session=session, user=user)
        return user, False

    # Try to find by email (handles username changes)
    user = get_user_by_email(session=session, email=email)

    if user:
        # User exists by email, update username in case it changed
        user.username = username
        update_user_last_login(session=session, user=user)
        return user, False

    # User doesn't exist, create it
    # Handle race condition where another request creates the user simultaneously
    try:
        user = create_user(
            session=session,
            username=username,
            email=email,
        )
        return user, True
    except IntegrityError:
        # Race condition: another request created the user
        session.rollback()
        # Try to fetch the user that was created by the other request
        user = get_user_by_email(session=session, email=email)
        if user:
            update_user_last_login(session=session, user=user)
            return user, False
        # Try by username as fallback
        user = get_user_by_username(session=session, username=username)
        if user:
            update_user_last_login(session=session, user=user)
            return user, False
        # This shouldn't happen, but re-raise if we still can't find the user
        raise
