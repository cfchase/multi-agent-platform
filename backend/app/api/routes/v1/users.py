import logging
from typing import Any

from fastapi import APIRouter

from app.api.deps import CurrentUser, SessionDep
from app.crud.integration import get_integration_status
from app.models import IntegrationStatus, UserMeResponse
from app.services.oauth_config import get_supported_services
from app.services.token_refresh import refresh_integration_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserMeResponse)
async def read_user_me(current_user: CurrentUser, session: SessionDep) -> Any:
    """
    Get current user info with integration status.

    Returns the current authenticated user's information based on
    OAuth proxy headers, along with the status of their external
    service integrations (connected, expired, missing).

    Automatically attempts to refresh expired tokens if a refresh token
    is available.
    """
    # Get integration status for all supported services
    available_services = get_supported_services()
    status = get_integration_status(
        session=session,
        user_id=current_user.id,
        available_services=available_services,
    )

    # Attempt to refresh any expired tokens
    if status["expired"]:
        for service_name in status["expired"]:
            logger.info(f"Attempting to refresh expired token for {service_name}")
            refreshed = await refresh_integration_token(
                session=session,
                user_id=current_user.id,
                service_name=service_name,
            )
            if refreshed:
                logger.info(f"Successfully refreshed token for {service_name}")
            else:
                logger.warning(f"Failed to refresh token for {service_name}")

        # Re-fetch status after refresh attempts
        status = get_integration_status(
            session=session,
            user_id=current_user.id,
            available_services=available_services,
        )

    # Build response with integration status
    return UserMeResponse(
        id=current_user.id,
        email=current_user.email,
        username=current_user.username,
        full_name=current_user.full_name,
        active=current_user.active,
        admin=current_user.admin,
        created_at=current_user.created_at,
        last_login=current_user.last_login,
        integration_status=IntegrationStatus(
            connected=status["connected"],
            expired=status["expired"],
            missing=status["missing"],
        ),
    )
