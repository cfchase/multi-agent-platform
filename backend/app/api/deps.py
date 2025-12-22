"""
Dependency injection for FastAPI routes.

SECURITY WARNING:
This module trusts X-Forwarded-* headers for user identity.
The backend MUST be deployed behind an OAuth2-proxy with proper
network isolation. Direct access to the backend from untrusted
networks would allow header spoofing and user impersonation.

Required deployment architecture:
- OAuth2-proxy handles all authentication
- Backend is only accessible from OAuth2-proxy (not public)
- Use NetworkPolicy or service mesh to enforce this

See docs/AUTHENTICATION.md for deployment details.
"""

from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlmodel import Session

from app.core.db import engine
from app.core.config import settings
from app.crud import get_or_create_user
from app.models import User


def get_db() -> Generator[Session, None, None]:
    """Get database session"""
    with Session(engine) as session:
        yield session


def get_current_user(
    session: Annotated[Session, Depends(get_db)],
    x_forwarded_preferred_username: str | None = Header(None, alias="X-Forwarded-Preferred-Username"),
    x_forwarded_user: str | None = Header(None, alias="X-Forwarded-User"),
    x_forwarded_email: str | None = Header(None, alias="X-Forwarded-Email"),
) -> User:
    """
    Extract the authenticated username from OAuth proxy headers and
    automatically create or update the user in the database.

    Supports both OAuth proxy types:
    - oauth2-proxy with Keycloak: Sets X-Forwarded-Preferred-Username
    - OpenShift OAuth Proxy: Sets X-Forwarded-User (configured with --pass-user-headers=true)

    Headers checked (in order of preference):
    - X-Forwarded-Preferred-Username: Username from oauth2-proxy/Keycloak (checked first)
    - X-Forwarded-User: Username from OpenShift OAuth proxy (fallback)
    - X-Forwarded-Email: Email from both proxy types

    In local development mode (ENVIRONMENT=local), this function returns a
    default test user to allow development without the OAuth proxy.

    This function automatically:
    1. Creates a new user in the database if they don't exist
    2. Updates the last_login timestamp for existing users
    3. Updates email if it has changed

    Returns:
        User: The User database object

    Raises:
        HTTPException: 401 if no authenticated user is found (production/staging only)
    """
    # Try oauth2-proxy header first, fall back to OpenShift OAuth header
    username = x_forwarded_preferred_username or x_forwarded_user
    email = x_forwarded_email

    if settings.ENVIRONMENT == "local" and not username:
        username = "dev-user"
        email = "dev-user@example.com"

    # In staging/production, require OAuth proxy headers
    if not username or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. No user information found in request headers.",
        )

    # Get or create user in database (also updates last_login and email)
    user, created = get_or_create_user(
        session=session,
        username=username,
        email=email,
    )

    return user


def get_current_admin_user(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    """
    Verify current OAuth user has admin privileges.

    This dependency can be used to protect API endpoints that require admin access.

    Args:
        current_user: Current authenticated user from OAuth

    Returns:
        User object if user has admin access

    Raises:
        HTTPException: 403 if user does not have admin privileges
    """
    if not current_user.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    return current_user


# Type annotations for dependency injection
SessionDep = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentAdminUser = Annotated[User, Depends(get_current_admin_user)]
