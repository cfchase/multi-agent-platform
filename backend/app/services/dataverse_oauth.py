"""
Dataverse dynamic OAuth client registration service.

Implements OAuth 2.0 Dynamic Client Registration (RFC 7591) for Dataverse.
This allows the application to register as an OAuth client dynamically,
eliminating the need for pre-configured client credentials.

Dataverse uses public clients (no client_secret) with PKCE for security.
"""

import logging

import httpx

from app.core.config import settings


logger = logging.getLogger(__name__)


class DataverseRegistrationError(Exception):
    """Error during Dataverse dynamic client registration."""

    def __init__(self, message: str, status_code: int | None = None):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


async def register_dataverse_client(
    redirect_uri: str,
    auth_url: str | None = None,
    client_name: str = "Multi-Agent Platform",
) -> str:
    """
    Register an OAuth client with Dataverse using dynamic client registration.

    This implements RFC 7591 (OAuth 2.0 Dynamic Client Registration Protocol)
    to obtain a client_id without pre-configuration.

    Args:
        redirect_uri: The OAuth callback URL for this application.
        auth_url: Dataverse OAuth URL (defaults to settings.DATAVERSE_AUTH_URL).
        client_name: Name to register the client as (defaults to "Multi-Agent Platform").

    Returns:
        The dynamically assigned client_id.

    Raises:
        DataverseRegistrationError: If registration fails.

    Example:
        client_id = await register_dataverse_client(
            redirect_uri="http://localhost:8000/api/v1/integrations/oauth/callback/dataverse"
        )
    """
    if auth_url is None:
        auth_url = settings.DATAVERSE_AUTH_URL

    if not auth_url:
        raise DataverseRegistrationError("DATAVERSE_AUTH_URL is not configured")

    registration_url = f"{auth_url.rstrip('/')}/register"

    registration_data = {
        "client_name": client_name,
        "redirect_uris": [redirect_uri],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",  # Public client - no secret
        "application_type": "native",
    }

    logger.info(
        f"[DATAVERSE] Registering OAuth client with dynamic registration at {registration_url}"
    )
    logger.debug(
        f"[DATAVERSE] Registration data: client_name='{client_name}', "
        f"redirect_uri='{redirect_uri}'"
    )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(registration_url, json=registration_data)

            if response.status_code in [200, 201]:
                client_info = response.json()
                client_id = client_info.get("client_id")

                if client_id:
                    logger.info(
                        f"[DATAVERSE] OAuth client registered successfully! "
                        f"client_id={client_id}"
                    )
                    return client_id
                else:
                    error_msg = f"No client_id in registration response: {client_info}"
                    logger.error(f"[DATAVERSE] {error_msg}")
                    raise DataverseRegistrationError(error_msg)
            else:
                error_msg = (
                    f"Client registration failed: HTTP {response.status_code} - "
                    f"{response.text}"
                )
                logger.error(f"[DATAVERSE] {error_msg}")
                raise DataverseRegistrationError(error_msg, response.status_code)

    except httpx.HTTPError as e:
        error_msg = f"Connection error during client registration: {e}"
        logger.error(f"[DATAVERSE] {error_msg}")
        raise DataverseRegistrationError(error_msg)
