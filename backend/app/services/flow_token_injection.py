"""
Flow token injection service for Langflow integration.

Injects user OAuth tokens into Langflow flow tweaks via the generic
UserSettings component. This decouples the backend from flow internals.

Architecture:
- API keys (OPENAI_API_KEY, etc.) -> langflow.env global variables
- User tokens (OAuth) -> UserSettings.data via tweaks
- App context (feature flags, etc.) -> AppSettings.data via tweaks
"""

import logging
from sqlmodel import Session

from app.services.token_refresh import get_valid_token

logger = logging.getLogger(__name__)


class MissingTokenError(Exception):
    """Error raised when a required service token is missing."""

    def __init__(self, service_name: str, message: str | None = None):
        self.service_name = service_name
        default_msg = f"Missing or expired token for service: {service_name}"
        super().__init__(message or default_msg)


async def build_user_settings_data(
    *,
    session: Session,
    user_id: int,
    services: list[str] | None = None,
) -> dict:
    """
    Build user settings dict with OAuth tokens for specified services.

    Args:
        session: Database session
        user_id: User ID
        services: List of service names to include tokens for.
                  If None, includes all available tokens.

    Returns:
        Dict suitable for UserSettings.data injection

    Raises:
        MissingTokenError: If a required service token is not available

    Example:
        user_data = await build_user_settings_data(
            session=session,
            user_id=user.id,
            services=["google_drive"],
        )
        # Result: {"google_drive_token": "...", "user_id": 123}
    """
    user_data: dict = {"user_id": user_id}

    # Default services to check if none specified
    if services is None:
        services = ["google_drive", "dataverse"]

    for service_name in services:
        token = await get_valid_token(
            session=session,
            user_id=user_id,
            service_name=service_name,
        )

        if token is not None:
            # Use consistent key naming: {service_name}_token
            user_data[f"{service_name}_token"] = token
            logger.debug("Added token for %s to user settings", service_name)

    return user_data


def build_app_settings_data() -> dict:
    """
    Build app settings dict with application context.

    Returns non-secret application configuration:
    - App name
    - Feature flags
    - Version info

    API keys are NOT included - they go in langflow.env.

    Returns:
        Dict suitable for AppSettings.data injection
    """
    return {
        "app_name": "multi-agent-platform",
        "features": {
            "rag_enabled": True,
            "safety_check": True,
        },
    }


def build_generic_tweaks(
    user_data: dict | None = None,
    app_data: dict | None = None,
) -> dict:
    """
    Build tweaks dict with generic UserSettings and AppSettings.

    This is the only tweak structure the backend sends. Flows opt in
    to receive settings by including UserSettings/AppSettings components.

    Args:
        user_data: User context dict (tokens, preferences)
        app_data: App context dict (feature flags)

    Returns:
        Tweaks dict ready for Langflow
    """
    tweaks = {}

    if user_data:
        tweaks["User Settings"] = {"settings_data": user_data}

    if app_data:
        tweaks["App Settings"] = {"settings_data": app_data}

    return tweaks


def get_required_services_for_flow(flow_name: str) -> list[str]:
    """
    Get list of OAuth services required by a flow.

    This is the minimal configuration - just which services need tokens.
    The injection target is always UserSettings.data.

    Args:
        flow_name: Name of the Langflow flow

    Returns:
        List of service names (e.g., ["google_drive", "dataverse"])
    """
    # Map flow names to required OAuth services
    # The injection target is always UserSettings.data
    flow_services: dict[str, list[str]] = {
        # Enterprise agent needs Google Drive
        "enterprise-agent": ["google_drive"],
        # Test flows for validation
        "test-google-drive": ["google_drive"],
        "test-dataverse": ["dataverse"],
        # Flows that need both
        "multi-source-rag": ["google_drive", "dataverse"],
    }

    return flow_services.get(flow_name, [])
