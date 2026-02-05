"""
OAuth token exchange and refresh service.

Handles exchanging authorization codes for tokens and refreshing expired tokens.
"""

import httpx

from app.services.oauth_config import get_provider_config


class OAuthTokenError(Exception):
    """Error during OAuth token exchange or refresh."""

    def __init__(self, error: str, description: str | None = None):
        self.error = error
        self.description = description
        super().__init__(f"{error}: {description}" if description else error)


async def _post_token_request(token_url: str, data: dict) -> dict:
    """
    Make a POST request to an OAuth token endpoint.

    Args:
        token_url: The OAuth provider's token endpoint URL
        data: Form data to send with the request

    Returns:
        Parsed JSON response from the token endpoint

    Raises:
        OAuthTokenError: If the token request fails
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            token_url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    result = response.json()

    if response.status_code != 200:
        error = result.get("error", "unknown_error")
        description = result.get("error_description")
        raise OAuthTokenError(error, description)

    return result


async def exchange_code_for_tokens(
    service_name: str,
    code: str,
    redirect_uri: str,
    code_verifier: str | None = None,
    provider_client_id: str | None = None,
) -> dict:
    """
    Exchange an authorization code for access and refresh tokens.

    Args:
        service_name: Name of the OAuth service
        code: Authorization code from OAuth callback
        redirect_uri: The redirect URI used in the authorization request
        code_verifier: PKCE code verifier (required for PKCE flows)
        provider_client_id: Dynamic client_id for RFC 7591 providers (e.g., Dataverse).
            Required for providers with uses_dynamic_registration=True.

    Returns:
        Dictionary with access_token, refresh_token, expires_in, etc.

    Raises:
        ValueError: If service is unknown or not configured
        OAuthTokenError: If token exchange fails
    """
    config = get_provider_config(service_name)
    if config is None:
        raise ValueError(f"Unknown service or missing configuration: {service_name}")

    # For dynamic registration providers, use the provided client_id
    # Otherwise use the static client_id from config
    client_id = provider_client_id if config.uses_dynamic_registration else config.client_id

    # Build token request data
    data = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "code": code,
        "redirect_uri": redirect_uri,
    }

    # Only include client_secret for confidential clients (not public clients)
    if not config.is_public_client and config.client_secret:
        data["client_secret"] = config.client_secret

    # Add PKCE code verifier if provided
    if code_verifier:
        data["code_verifier"] = code_verifier

    result = await _post_token_request(config.token_url, data)

    return {
        "access_token": result["access_token"],
        "refresh_token": result.get("refresh_token"),
        "expires_in": result.get("expires_in"),
        "token_type": result.get("token_type", "Bearer"),
        "scope": result.get("scope"),
    }


async def refresh_access_token(
    service_name: str,
    refresh_token: str,
    provider_client_id: str | None = None,
) -> dict:
    """
    Refresh an expired access token using the refresh token.

    Args:
        service_name: Name of the OAuth service
        refresh_token: The refresh token to use
        provider_client_id: Dynamic client_id for RFC 7591 providers (e.g., Dataverse).
            Required for providers with uses_dynamic_registration=True.
            This should be retrieved from the stored UserIntegration.provider_client_id.

    Returns:
        Dictionary with new access_token, expires_in, and optionally new refresh_token

    Raises:
        ValueError: If service is unknown or not configured
        OAuthTokenError: If token refresh fails
    """
    config = get_provider_config(service_name)
    if config is None:
        raise ValueError(f"Unknown service or missing configuration: {service_name}")

    # For dynamic registration providers, use the provided client_id
    # Otherwise use the static client_id from config
    client_id = provider_client_id if config.uses_dynamic_registration else config.client_id

    data = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "refresh_token": refresh_token,
    }

    # Only include client_secret for confidential clients (not public clients)
    if not config.is_public_client and config.client_secret:
        data["client_secret"] = config.client_secret

    result = await _post_token_request(config.token_url, data)

    return {
        "access_token": result["access_token"],
        # Some providers don't return a new refresh token on refresh
        # In that case, preserve the original
        "refresh_token": result.get("refresh_token", refresh_token),
        "expires_in": result.get("expires_in"),
        "token_type": result.get("token_type", "Bearer"),
        "scope": result.get("scope"),
    }
