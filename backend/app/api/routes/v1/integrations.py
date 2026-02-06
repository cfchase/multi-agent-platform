"""
Integration API routes for managing OAuth connections to external services.

Provides endpoints for:
- Listing user's integrations
- Starting OAuth flows
- Handling OAuth callbacks
- Disconnecting integrations
"""

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.api.deps import CurrentUser, SessionDep
from app.core.config import settings
from app.crud.integration import (
    create_or_update_integration,
    delete_integration,
    get_integration_status,
    get_missing_integrations,
    get_user_integrations,
)
from app.models import UserIntegrationPublic
from app.services.oauth_config import (
    build_authorization_url_db,
    consume_oauth_state_db,
    get_provider_config,
    get_supported_services,
)
from app.services.dataverse_oauth import (
    register_dataverse_client,
    DataverseRegistrationError,
)
from app.services.oauth_token import exchange_code_for_tokens, OAuthTokenError

router = APIRouter(prefix="/integrations", tags=["integrations"])


# Response models
class IntegrationsListResponse(BaseModel):
    """Response for listing integrations."""

    integrations: list[UserIntegrationPublic]
    count: int


class IntegrationStatusResponse(BaseModel):
    """Response for integration status check."""

    connected_services: list[str]
    expired_services: list[str]
    missing_services: list[str]


class OAuthStartResponse(BaseModel):
    """Response for OAuth start endpoint."""

    authorization_url: str
    service: str


class SupportedServicesResponse(BaseModel):
    """Response for supported services list."""

    services: list[str]


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str


def _to_public(integration) -> UserIntegrationPublic:
    """Convert UserIntegration to public schema."""
    return UserIntegrationPublic(
        id=integration.id,
        service_name=integration.service_name,
        expires_at=integration.expires_at,
        scopes=integration.scopes,
        is_connected=True,
        is_expired=integration.is_expired(),
        created_at=integration.created_at,
        updated_at=integration.updated_at,
    )


@router.get("/", response_model=IntegrationsListResponse)
async def list_integrations(
    current_user: CurrentUser,
    session: SessionDep,
) -> IntegrationsListResponse:
    """
    List all integrations for the current user.

    Returns a list of connected services without exposing tokens.
    """
    integrations = get_user_integrations(session=session, user_id=current_user.id)
    public_integrations = [_to_public(i) for i in integrations]

    return IntegrationsListResponse(
        integrations=public_integrations,
        count=len(public_integrations),
    )


@router.get("/status", response_model=IntegrationStatusResponse)
async def get_status(
    current_user: CurrentUser,
    session: SessionDep,
) -> IntegrationStatusResponse:
    """
    Get integration status for the current user.

    Returns lists of connected, expired, and missing services.
    """
    supported = get_supported_services()
    status = get_integration_status(
        session=session,
        user_id=current_user.id,
        available_services=supported,
    )

    return IntegrationStatusResponse(
        connected_services=status["connected"],
        expired_services=status["expired"],
        missing_services=status["missing"],
    )


@router.get("/services", response_model=SupportedServicesResponse)
async def list_supported_services(
    current_user: CurrentUser,
) -> SupportedServicesResponse:
    """
    List all supported OAuth services.
    """
    return SupportedServicesResponse(services=get_supported_services())


@router.post("/oauth/start/{service}", response_model=OAuthStartResponse)
async def start_oauth_flow(
    service: str,
    request: Request,
    current_user: CurrentUser,
    session: SessionDep,
) -> OAuthStartResponse:
    """
    Start OAuth flow for a service.

    Returns the authorization URL to redirect the user to.
    State is stored in the database for multi-replica support.

    For providers that use dynamic client registration (e.g., Dataverse),
    a new client is registered before starting the OAuth flow.
    """
    # Build the callback URL
    base_url = str(request.base_url).rstrip("/")
    redirect_uri = f"{base_url}/api/v1/integrations/oauth/callback/{service}"

    # Check if this provider uses dynamic registration
    config = get_provider_config(service)
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown service or missing configuration: {service}",
        )

    provider_client_id = None

    # For dynamic registration providers, register a client first
    if config.uses_dynamic_registration:
        try:
            provider_client_id = await register_dataverse_client(
                redirect_uri=redirect_uri,
            )
        except DataverseRegistrationError as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to register OAuth client with {service}: {e.message}",
            )

    try:
        authorization_url, state = build_authorization_url_db(
            session=session,
            service_name=service,
            redirect_uri=redirect_uri,
            user_id=current_user.id,
            provider_client_id=provider_client_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return OAuthStartResponse(
        authorization_url=authorization_url,
        service=service,
    )


def _build_settings_redirect(
    success: bool = True,
    service: str | None = None,
    error_message: str | None = None,
) -> RedirectResponse:
    """Build redirect URL to frontend settings page with status."""
    base_url = settings.FRONTEND_HOST.rstrip("/")
    redirect_url = f"{base_url}/settings/integrations"

    # Add query params for status feedback
    params = []
    if success and service:
        params.append(f"connected={service}")
    if error_message:
        # URL-encode the error message
        from urllib.parse import quote

        params.append(f"error={quote(error_message)}")

    if params:
        redirect_url += "?" + "&".join(params)

    return RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)


@router.get("/oauth/callback/{service}")
async def oauth_callback(
    service: str,
    session: SessionDep,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
):
    """
    Handle OAuth callback from provider.

    This endpoint is called by the OAuth provider (e.g., Google) after user
    authorization. It does NOT require CurrentUser authentication because:
    1. The request comes from a provider redirect, not the authenticated user
    2. The user is identified via the state parameter stored during oauth/start
    3. The state is cryptographically secure and bound to the original user

    Exchanges authorization code for tokens and redirects to settings page.
    """
    # Check for OAuth errors from provider
    if error:
        return _build_settings_redirect(
            success=False,
            error_message=f"OAuth error: {error}. {error_description or ''}",
        )

    if not code:
        return _build_settings_redirect(
            success=False,
            error_message="Missing authorization code",
        )

    if not state:
        return _build_settings_redirect(
            success=False,
            error_message="Missing state parameter",
        )

    # Validate and consume state from database - user_id is embedded in state from oauth/start
    # No user_id validation here since this is an unauthenticated callback
    state_data = consume_oauth_state_db(session=session, state=state)
    if state_data is None:
        return _build_settings_redirect(
            success=False,
            error_message="Invalid or expired state parameter",
        )

    # Verify service matches
    if state_data.service_name != service:
        return _build_settings_redirect(
            success=False,
            error_message="Service mismatch in callback",
        )

    # Exchange authorization code for tokens
    # Pass provider_client_id for dynamic registration providers
    try:
        tokens = await exchange_code_for_tokens(
            service_name=service,
            code=code,
            redirect_uri=state_data.redirect_uri,
            code_verifier=state_data.code_verifier,
            provider_client_id=state_data.provider_client_id,
        )
    except OAuthTokenError as e:
        return _build_settings_redirect(
            success=False,
            error_message=f"Token exchange failed: {e.error}",
        )

    # Store the tokens using user_id from the validated state
    # Include provider_client_id for dynamic registration providers (needed for token refresh)
    create_or_update_integration(
        session=session,
        user_id=state_data.user_id,
        service_name=service,
        access_token=tokens["access_token"],
        refresh_token=tokens.get("refresh_token"),
        expires_in=tokens.get("expires_in"),
        scopes=tokens.get("scope"),
        provider_client_id=state_data.provider_client_id,
    )

    # Redirect back to settings page with success indicator
    return _build_settings_redirect(success=True, service=service)


@router.delete("/{service}", response_model=MessageResponse)
async def disconnect_integration(
    service: str,
    current_user: CurrentUser,
    session: SessionDep,
) -> MessageResponse:
    """
    Disconnect an integration.

    Removes the stored tokens for the specified service.
    """
    deleted = delete_integration(
        session=session,
        user_id=current_user.id,
        service_name=service,
    )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Integration not found: {service}",
        )

    return MessageResponse(message="Integration disconnected")
