"""
Flow token injection service for Langflow integration.

Injects user OAuth tokens into Langflow flow tweaks, enabling flows
to access external services on behalf of the user.
"""

import logging
from copy import deepcopy
from sqlmodel import Session

from app.services.token_refresh import get_valid_token

logger = logging.getLogger(__name__)


class MissingTokenError(Exception):
    """Error raised when a required service token is missing."""

    def __init__(self, service_name: str, message: str | None = None):
        self.service_name = service_name
        default_msg = f"Missing or expired token for service: {service_name}"
        super().__init__(message or default_msg)


def parse_tweak_path(path: str) -> tuple[str, str]:
    """
    Parse a tweak path into component and field names.

    Args:
        path: Dot-separated path like "ComponentName.field_name"

    Returns:
        Tuple of (component_name, field_name)

    Raises:
        ValueError: If path format is invalid
    """
    parts = path.split(".", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid tweak path format: {path}. Expected 'Component.field'")

    return parts[0], parts[1]


async def build_flow_tweaks(
    *,
    session: Session,
    user_id: int,
    token_config: dict[str, str],
    existing_tweaks: dict | None = None,
) -> dict:
    """
    Build Langflow tweaks dict with user tokens for required services.

    Args:
        session: Database session
        user_id: User ID
        token_config: Mapping of service_name to tweak_path
                      e.g., {"google_drive": "GoogleDriveComponent.api_key"}
        existing_tweaks: Optional existing tweaks to merge with

    Returns:
        Tweaks dict ready to pass to Langflow

    Raises:
        MissingTokenError: If a required service token is not available

    Example:
        token_config = {
            "google_drive": "GoogleDrive.access_token",
            "dataverse": "DataverseLoader.api_token",
        }

        tweaks = await build_flow_tweaks(
            session=session,
            user_id=user.id,
            token_config=token_config,
        )

        # Result:
        # {
        #     "GoogleDrive": {"access_token": "user's-google-token"},
        #     "DataverseLoader": {"api_token": "user's-dataverse-token"},
        # }
    """
    # Start with existing tweaks or empty dict
    tweaks = deepcopy(existing_tweaks) if existing_tweaks else {}

    for service_name, tweak_path in token_config.items():
        # Get valid token (refreshes if needed)
        token = await get_valid_token(
            session=session,
            user_id=user_id,
            service_name=service_name,
        )

        if token is None:
            logger.error("Missing token for service %s for user %s", service_name, user_id)
            raise MissingTokenError(service_name)

        # Parse the tweak path
        component_name, field_name = parse_tweak_path(tweak_path)

        # Add or update the component's tweaks
        if component_name not in tweaks:
            tweaks[component_name] = {}

        tweaks[component_name][field_name] = token

        logger.debug("Injected token for %s into %s", service_name, tweak_path)

    return tweaks


def get_required_services_for_flow(flow_name: str) -> dict[str, str]:
    """
    Get the token configuration for a flow.

    This defines which services a flow requires and where to inject the tokens.

    Args:
        flow_name: Name of the Langflow flow

    Returns:
        Mapping of service_name to tweak_path

    Note:
        In a future iteration, this could be stored in the database
        or read from a configuration file. For now, it's hardcoded.
    """
    # Default configurations for common flows
    # This maps flow names to their required service tokens
    flow_configs = {
        # Example: A flow that needs Google Drive access
        "google_drive_rag": {
            "google_drive": "GoogleDriveLoader.credentials",
        },
        # Example: A flow that needs Dataverse access
        "dataverse_search": {
            "dataverse": "DataverseSearchTool.api_token",
        },
        # Example: A flow that needs both services
        "multi_source_rag": {
            "google_drive": "GoogleDriveLoader.credentials",
            "dataverse": "DataverseSearchTool.api_token",
        },
        # Test flows for settings validation (Phase 2)
        "test-google-drive": {
            "google_drive": "GoogleDriveSearch.access_token",
        },
        "test-dataverse": {
            "dataverse": "DataverseSearchTool.api_token",
        },
    }

    return flow_configs.get(flow_name, {})
