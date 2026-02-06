"""
CRUD operations for UserIntegration model.

Handles creation, retrieval, update, and deletion of OAuth integrations
for external services (Google Drive, Dataverse, etc.).
"""

from datetime import datetime, timezone, timedelta

from sqlmodel import Session, select

from app.core.encryption import get_encryption
from app.models import UserIntegration


def get_user_integration(
    *, session: Session, user_id: int, service_name: str
) -> UserIntegration | None:
    """
    Get a user's integration for a specific service.

    Args:
        session: Database session
        user_id: User ID
        service_name: Name of the service (e.g., "google_drive", "dataverse")

    Returns:
        UserIntegration if found, None otherwise
    """
    statement = select(UserIntegration).where(
        UserIntegration.user_id == user_id,
        UserIntegration.service_name == service_name,
    )
    return session.exec(statement).first()


def get_user_integrations(
    *, session: Session, user_id: int
) -> list[UserIntegration]:
    """
    Get all integrations for a user.

    Args:
        session: Database session
        user_id: User ID

    Returns:
        List of UserIntegration objects
    """
    statement = select(UserIntegration).where(UserIntegration.user_id == user_id)
    return list(session.exec(statement).all())


def create_or_update_integration(
    *,
    session: Session,
    user_id: int,
    service_name: str,
    access_token: str,
    refresh_token: str | None = None,
    expires_in: int | None = None,
    scopes: str | None = None,
    token_type: str = "Bearer",
    provider_client_id: str | None = None,
) -> UserIntegration:
    """
    Create a new integration or update an existing one.

    If an integration already exists for this user+service, it will be updated.
    Otherwise, a new integration will be created.

    Args:
        session: Database session
        user_id: User ID
        service_name: Name of the service
        access_token: OAuth access token (will be encrypted)
        refresh_token: OAuth refresh token (will be encrypted, optional)
        expires_in: Token lifetime in seconds (optional)
        scopes: Space-separated OAuth scopes (optional)
        token_type: Token type, typically "Bearer"
        provider_client_id: Dynamic client_id for RFC 7591 providers (optional)

    Returns:
        Created or updated UserIntegration
    """
    encryption = get_encryption()

    # Calculate expiry time
    expires_at = None
    if expires_in is not None:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    # Check if integration already exists
    existing = get_user_integration(
        session=session, user_id=user_id, service_name=service_name
    )

    if existing:
        # Update existing integration
        existing.access_token_encrypted = encryption.encrypt(access_token)
        if refresh_token is not None:
            existing.refresh_token_encrypted = encryption.encrypt(refresh_token)
        existing.expires_at = expires_at
        existing.scopes = scopes
        existing.token_type = token_type
        if provider_client_id is not None:
            existing.provider_client_id = provider_client_id
        existing.updated_at = datetime.now(timezone.utc)
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    # Create new integration
    integration = UserIntegration(
        user_id=user_id,
        service_name=service_name,
        access_token_encrypted=encryption.encrypt(access_token),
        refresh_token_encrypted=(
            encryption.encrypt(refresh_token) if refresh_token else None
        ),
        expires_at=expires_at,
        scopes=scopes,
        token_type=token_type,
        provider_client_id=provider_client_id,
    )
    session.add(integration)
    session.commit()
    session.refresh(integration)
    return integration


def delete_integration(
    *, session: Session, user_id: int, service_name: str
) -> bool:
    """
    Delete a user's integration for a specific service.

    Args:
        session: Database session
        user_id: User ID
        service_name: Name of the service

    Returns:
        True if deleted, False if not found
    """
    integration = get_user_integration(
        session=session, user_id=user_id, service_name=service_name
    )
    if integration is None:
        return False

    session.delete(integration)
    session.commit()
    return True


def get_decrypted_tokens(integration: UserIntegration) -> dict[str, str | None]:
    """
    Get decrypted tokens from an integration.

    Args:
        integration: UserIntegration object

    Returns:
        Dictionary with "access_token" and "refresh_token" keys
    """
    encryption = get_encryption()

    access_token = encryption.decrypt(integration.access_token_encrypted)
    refresh_token = None
    if integration.refresh_token_encrypted is not None:
        refresh_token = encryption.decrypt(integration.refresh_token_encrypted)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": integration.token_type,
        "expires_at": integration.expires_at.isoformat() if integration.expires_at else None,
        "scopes": integration.scopes,
    }


def get_missing_integrations(
    *,
    session: Session,
    user_id: int,
    required_services: list[str],
) -> list[str]:
    """
    Get list of services that need to be connected or have expired tokens.

    Args:
        session: Database session
        user_id: User ID
        required_services: List of required service names

    Returns:
        List of service names that are missing or have expired tokens
    """
    integrations = get_user_integrations(session=session, user_id=user_id)

    # Build set of valid (non-expired) integrations
    valid_services = {
        i.service_name for i in integrations if not i.is_expired()
    }

    # Return services that are not in the valid set
    return [s for s in required_services if s not in valid_services]


def get_integration_status(
    *,
    session: Session,
    user_id: int,
    available_services: list[str],
) -> dict[str, list[str]]:
    """
    Get the status of all integrations for a user.

    Categorizes services into connected, expired, and missing.

    Args:
        session: Database session
        user_id: User ID
        available_services: List of all available service names

    Returns:
        Dictionary with keys: "connected", "expired", "missing"
    """
    integrations = get_user_integrations(session=session, user_id=user_id)

    # Build maps of integration status
    integration_map = {i.service_name: i for i in integrations}

    connected: list[str] = []
    expired: list[str] = []
    missing: list[str] = []

    for service in available_services:
        integration = integration_map.get(service)
        if integration is None:
            missing.append(service)
        elif integration.is_expired():
            expired.append(service)
        else:
            connected.append(service)

    return {
        "connected": connected,
        "expired": expired,
        "missing": missing,
    }
