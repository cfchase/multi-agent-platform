"""
Flow token injection service for Langflow integration.

Injects user OAuth tokens into Langflow flow tweaks via the generic
UserSettings component. The platform is flow-agnostic: it always injects
all available tokens and lets flows take what they need.

Architecture:
- API keys (OPENAI_API_KEY, etc.) -> environment variables (forwarded by dev-langflow.sh)
- User tokens (OAuth) -> UserSettings.data via tweaks
- App context (feature flags, etc.) -> AppSettings.data via tweaks
"""

import logging
from sqlmodel import Session

from app.crud.integration import get_user_integrations
from app.services.token_refresh import get_valid_token

logger = logging.getLogger(__name__)


async def build_user_settings_data(
    *,
    session: Session,
    user_id: int,
) -> dict:
    """
    Build user settings dict with all available OAuth tokens.

    Discovers the user's connected integrations and injects valid tokens
    for each. Flows opt in by reading the tokens they need from
    UserSettings.data — the platform does not need to know which flows
    use which services.

    Args:
        session: Database session
        user_id: User ID

    Returns:
        Dict suitable for UserSettings.data injection

    Example:
        user_data = await build_user_settings_data(
            session=session, user_id=user.id,
        )
        # Result: {"google_drive_token": "...", "dataverse_token": "...", "user_id": 123}
    """
    user_data: dict = {"user_id": user_id}

    integrations = get_user_integrations(session=session, user_id=user_id)

    for integration in integrations:
        token = await get_valid_token(
            session=session,
            user_id=user_id,
            service_name=integration.service_name,
        )

        if token is not None:
            user_data[f"{integration.service_name}_token"] = token
            logger.debug("Added token for %s to user settings", integration.service_name)
        else:
            logger.warning(
                "Omitted token for %s user %s (expired or unavailable)",
                integration.service_name,
                user_id,
            )

    return user_data


def build_app_settings_data() -> dict:
    """
    Build app settings dict with application context.

    Returns non-secret application configuration:
    - App name
    - Feature flags
    - Version info

    API keys are NOT included - they reach LangFlow via environment variables.

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
