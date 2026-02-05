"""
Token refresh service for maintaining valid OAuth tokens.

Automatically refreshes expired or expiring tokens to ensure
seamless access to external services.

Supports service-specific refresh thresholds:
- Google Drive: 5 minutes (short operations)
- Dataverse: 60 minutes (long-running agentic tasks)
"""

import logging
from sqlmodel import Session

from app.crud.integration import (
    create_or_update_integration,
    get_decrypted_tokens,
    get_user_integration,
)
from app.services.oauth_token import refresh_access_token, OAuthTokenError

logger = logging.getLogger(__name__)

# Default refresh threshold (5 minutes before expiry)
DEFAULT_REFRESH_THRESHOLD_MINUTES = 5

# Service-specific refresh thresholds
# Dataverse needs a longer buffer for long-running agentic tasks
SERVICE_REFRESH_THRESHOLDS: dict[str, int] = {
    "google_drive": 5,   # Short operations, 5-minute buffer
    "dataverse": 60,     # Long-running agentic tasks, 60-minute buffer
}


def get_refresh_threshold_minutes(service_name: str) -> int:
    """
    Get the refresh threshold in minutes for a specific service.

    Different services have different refresh thresholds based on
    their typical operation duration:
    - Google Drive: 5 minutes (quick file operations)
    - Dataverse: 60 minutes (long-running data processing tasks)

    Args:
        service_name: Name of the service

    Returns:
        Refresh threshold in minutes
    """
    return SERVICE_REFRESH_THRESHOLDS.get(
        service_name,
        DEFAULT_REFRESH_THRESHOLD_MINUTES,
    )


async def get_valid_token(
    *,
    session: Session,
    user_id: int,
    service_name: str,
) -> str | None:
    """
    Get a valid access token for a service, refreshing if needed.

    This function:
    1. Checks if the user has an integration for the service
    2. If the token is valid, returns it
    3. If expired or expiring soon, attempts to refresh
    4. Returns the (possibly refreshed) access token

    Args:
        session: Database session
        user_id: User ID
        service_name: Name of the service

    Returns:
        Valid access token string, or None if unavailable
    """
    integration = get_user_integration(
        session=session,
        user_id=user_id,
        service_name=service_name,
    )

    if integration is None:
        return None

    # Get service-specific refresh threshold
    threshold_minutes = get_refresh_threshold_minutes(service_name)

    # Check if token needs refresh
    needs_refresh = (
        integration.is_expired() or
        integration.is_expiring_soon(minutes=threshold_minutes)
    )

    if needs_refresh:
        # Try to refresh the token
        refreshed = await refresh_integration_token(
            session=session,
            user_id=user_id,
            service_name=service_name,
        )

        if not refreshed:
            # Refresh failed - if expired, return None
            if integration.is_expired():
                logger.warning(
                    "Token for %s is expired and refresh failed for user %s",
                    service_name,
                    user_id,
                )
                return None
            # If just expiring soon, we can still use the current token
            logger.warning(
                "Token for %s is expiring soon and refresh failed for user %s",
                service_name,
                user_id,
            )

        # Re-fetch the integration to get updated token
        integration = get_user_integration(
            session=session,
            user_id=user_id,
            service_name=service_name,
        )

    # Return the decrypted access token
    tokens = get_decrypted_tokens(integration)
    return tokens["access_token"]


async def refresh_integration_token(
    *,
    session: Session,
    user_id: int,
    service_name: str,
) -> bool:
    """
    Refresh an integration's access token using the refresh token.

    Args:
        session: Database session
        user_id: User ID
        service_name: Name of the service

    Returns:
        True if refresh succeeded, False otherwise
    """
    integration = get_user_integration(
        session=session,
        user_id=user_id,
        service_name=service_name,
    )

    if integration is None:
        logger.error("Cannot refresh: no integration found for %s", service_name)
        return False

    # Get the refresh token
    tokens = get_decrypted_tokens(integration)
    refresh_token = tokens.get("refresh_token")

    if not refresh_token:
        logger.error("Cannot refresh: no refresh token for %s", service_name)
        return False

    try:
        # Call the OAuth provider to refresh
        # For dynamic registration providers (e.g., Dataverse), pass the stored provider_client_id
        new_tokens = await refresh_access_token(
            service_name=service_name,
            refresh_token=refresh_token,
            provider_client_id=integration.provider_client_id,
        )

        # Update the stored integration (preserve provider_client_id)
        create_or_update_integration(
            session=session,
            user_id=user_id,
            service_name=service_name,
            access_token=new_tokens["access_token"],
            refresh_token=new_tokens.get("refresh_token"),
            expires_in=new_tokens.get("expires_in"),
            scopes=new_tokens.get("scope"),
            provider_client_id=integration.provider_client_id,
        )

        logger.info("Successfully refreshed token for %s user %s", service_name, user_id)
        return True

    except OAuthTokenError as e:
        logger.error("Token refresh failed for %s: %s", service_name, e)
        return False
    except Exception:
        logger.exception("Unexpected error refreshing token for %s", service_name)
        return False
