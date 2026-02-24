"""
OAuth retry service for automatic token refresh on 401 responses.

Provides utilities for making authenticated requests to external services
with automatic retry when the token is rejected (401 response).
"""

import logging
from typing import Any, Callable, Awaitable

import httpx
from cryptography.fernet import InvalidToken
from sqlmodel import Session

from app.crud.integration import get_decrypted_tokens, get_user_integration
from app.services.token_refresh import refresh_integration_token

logger = logging.getLogger(__name__)


async def with_oauth_retry(
    *,
    session: Session,
    user_id: int,
    service_name: str,
    request_func: Callable[[str], Awaitable[Any]],
) -> Any:
    """
    Execute a request with automatic token refresh on 401 response.

    This utility:
    1. Gets the current access token for the service
    2. Calls the request function with the token
    3. If 401 is returned, refreshes the token and retries once
    4. Returns the response (either original or from retry)

    Args:
        session: Database session
        user_id: User ID
        service_name: Name of the OAuth service
        request_func: Async function that takes a token and returns a response.
                     The response must have a `status_code` attribute.

    Returns:
        Response from the request function

    Example:
        async def make_drive_request(token: str) -> httpx.Response:
            async with httpx.AsyncClient() as client:
                return await client.get(
                    "https://www.googleapis.com/drive/v3/files",
                    headers={"Authorization": f"Bearer {token}"}
                )

        response = await with_oauth_retry(
            session=session,
            user_id=user.id,
            service_name="google_drive",
            request_func=make_drive_request,
        )
    """
    # Get current token
    integration = get_user_integration(
        session=session,
        user_id=user_id,
        service_name=service_name,
    )

    if integration is None:
        raise ValueError(f"No integration found for {service_name}")

    try:
        tokens = get_decrypted_tokens(integration)
    except InvalidToken:
        logger.error(
            "Failed to decrypt token for %s user %s (encryption key mismatch)",
            service_name,
            user_id,
        )
        raise ValueError(
            f"Cannot decrypt token for {service_name}. "
            "The encryption key may have changed — user should reconnect the service."
        )
    access_token = tokens["access_token"]

    # Make the initial request
    response = await request_func(access_token)

    # If not 401, return the response as-is
    if response.status_code != 401:
        return response

    logger.info(
        "Received 401 from %s, attempting token refresh for user %s",
        service_name,
        user_id,
    )

    # Try to refresh the token
    refresh_success = await refresh_integration_token(
        session=session,
        user_id=user_id,
        service_name=service_name,
    )

    if not refresh_success:
        logger.warning(
            "Token refresh failed for %s user %s, returning 401",
            service_name,
            user_id,
        )
        return response

    # Get the new token
    integration = get_user_integration(
        session=session,
        user_id=user_id,
        service_name=service_name,
    )
    try:
        tokens = get_decrypted_tokens(integration)
    except InvalidToken:
        logger.error(
            "Failed to decrypt refreshed token for %s user %s",
            service_name,
            user_id,
        )
        return response
    new_access_token = tokens["access_token"]

    logger.info(
        "Token refreshed for %s user %s, retrying request",
        service_name,
        user_id,
    )

    # Retry with new token (only once)
    return await request_func(new_access_token)


async def make_authorized_request(
    *,
    session: Session,
    user_id: int,
    service_name: str,
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    **kwargs: Any,
) -> httpx.Response | None:
    """
    Make an authenticated HTTP request with automatic retry on 401.

    This is a convenience wrapper around with_oauth_retry that handles
    the httpx request creation.

    Args:
        session: Database session
        user_id: User ID
        service_name: Name of the OAuth service
        method: HTTP method (GET, POST, etc.)
        url: URL to request
        headers: Additional headers (Authorization will be added)
        **kwargs: Additional arguments passed to httpx.request()

    Returns:
        httpx.Response, or None if no integration exists

    Example:
        response = await make_authorized_request(
            session=session,
            user_id=user.id,
            service_name="google_drive",
            method="GET",
            url="https://www.googleapis.com/drive/v3/files",
        )
    """
    # Check if integration exists first
    integration = get_user_integration(
        session=session,
        user_id=user_id,
        service_name=service_name,
    )

    if integration is None:
        logger.warning(
            "No integration found for %s user %s",
            service_name,
            user_id,
        )
        return None

    async def request_with_token(token: str) -> httpx.Response:
        request_headers = headers.copy() if headers else {}
        request_headers["Authorization"] = f"Bearer {token}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            return await client.request(
                method=method,
                url=url,
                headers=request_headers,
                **kwargs,
            )

    return await with_oauth_retry(
        session=session,
        user_id=user_id,
        service_name=service_name,
        request_func=request_with_token,
    )
