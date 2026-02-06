"""
OAuth configuration service for external service integrations.

Provides configuration for OAuth flows with Google Drive and Dataverse,
including PKCE support and secure state management.

This module supports two storage modes for OAuth state:
1. In-memory (for single-instance or testing)
2. Database (for multi-replica production deployments)

The database-backed functions require a SQLModel Session and are
suffixed with _db (e.g., build_authorization_url_db).
"""

import base64
import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from sqlmodel import Session

from app.core.config import settings
from app.crud.oauth_state import (
    consume_oauth_state_db as _consume_oauth_state_db,
    get_oauth_state_db as _get_oauth_state_db,
    store_oauth_state_db as _store_oauth_state_db,
    cleanup_expired_states_db as _cleanup_expired_states_db,
)
from app.models import OAuthState

# Re-export the expiration constant from the model
from app.models.oauth_state import STATE_EXPIRATION_MINUTES


@dataclass
class OAuthProviderConfig:
    """Configuration for an OAuth provider."""

    authorize_url: str
    token_url: str
    scopes: list[str]
    client_id: str | None = None
    client_secret: str | None = None
    use_pkce: bool = False
    uses_dynamic_registration: bool = False
    is_public_client: bool = False  # Public clients don't use client_secret
    extra_params: dict | None = None


@dataclass
class OAuthStateData:
    """Data stored with OAuth state for validation on callback."""

    service_name: str
    redirect_uri: str
    user_id: int
    code_verifier: str | None = None
    provider_client_id: str | None = None  # Dynamic client_id for RFC 7591 providers
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# In-memory state storage with expiration
# LIMITATION: This works for single-instance deployments only.
# For multi-replica deployments, replace with Redis or database-backed storage
# to ensure OAuth callbacks can be processed by any replica.
_oauth_states: dict[str, OAuthStateData] = {}


def _build_google_drive_config() -> OAuthProviderConfig | None:
    """Build OAuth config for Google Drive."""
    client_id = settings.GOOGLE_CLIENT_ID
    client_secret = settings.GOOGLE_CLIENT_SECRET

    if not client_id or not client_secret:
        return None

    return OAuthProviderConfig(
        client_id=client_id,
        client_secret=client_secret,
        authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
        use_pkce=False,
        extra_params={"access_type": "offline", "prompt": "consent"},
    )


def _build_dataverse_config() -> OAuthProviderConfig | None:
    """
    Build OAuth config for Dataverse.

    Dataverse uses dynamic client registration (RFC 7591), so no pre-configured
    client_id or client_secret is required. The client_id is obtained dynamically
    when starting the OAuth flow.

    Dataverse uses public clients (no client_secret) with PKCE for security.

    OAuth endpoints follow the pattern from agents-python:
    - {auth_url}/authorize
    - {auth_url}/token
    - {auth_url}/register
    """
    auth_url = settings.DATAVERSE_AUTH_URL

    if not auth_url:
        return None

    # Remove trailing slash for consistent URL building
    auth_url = auth_url.rstrip("/")

    return OAuthProviderConfig(
        authorize_url=f"{auth_url}/authorize",
        token_url=f"{auth_url}/token",
        scopes=["openid", "offline_access"],  # offline_access needed for refresh tokens
        use_pkce=True,
        uses_dynamic_registration=True,
        is_public_client=True,  # Dataverse uses public clients with PKCE
        client_id=None,  # Set dynamically during OAuth flow
        client_secret=None,  # Not used for public clients
    )


# Provider configuration builders, keyed by service name
_PROVIDER_BUILDERS = {
    "google_drive": _build_google_drive_config,
    "dataverse": _build_dataverse_config,
}


def get_provider_config(service_name: str) -> OAuthProviderConfig | None:
    """
    Get OAuth configuration for a service.

    Args:
        service_name: Name of the service (e.g., "google_drive", "dataverse")

    Returns:
        OAuthProviderConfig or None if service is unknown
    """
    builder = _PROVIDER_BUILDERS.get(service_name)
    if builder is None:
        return None
    return builder()


def get_supported_services() -> list[str]:
    """
    Get list of supported OAuth services.

    Returns:
        List of service names that can be configured
    """
    return list(_PROVIDER_BUILDERS.keys())


def generate_oauth_state() -> str:
    """
    Generate a cryptographically secure OAuth state parameter.

    Returns:
        URL-safe random string with sufficient entropy
    """
    return secrets.token_urlsafe(32)


def generate_pkce_pair() -> tuple[str, str]:
    """
    Generate PKCE code verifier and challenge pair.

    Following RFC 7636:
    - Code verifier: 43-128 character random string
    - Code challenge: Base64url(SHA256(code_verifier))

    Returns:
        Tuple of (code_verifier, code_challenge)
    """
    # Generate code verifier (43-128 chars, we use 64)
    code_verifier = secrets.token_urlsafe(48)  # 64 chars

    # Generate code challenge using S256
    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()

    return code_verifier, code_challenge


def store_oauth_state(state: str, state_data: OAuthStateData) -> None:
    """
    Store OAuth state data for later validation.

    Args:
        state: The state parameter to use as key
        state_data: Data to store (service name, redirect URI, PKCE verifier)
    """
    _oauth_states[state] = state_data


def get_oauth_state(state: str) -> OAuthStateData | None:
    """
    Retrieve OAuth state data without removing it.

    Args:
        state: The state parameter

    Returns:
        OAuthStateData or None if not found
    """
    return _oauth_states.get(state)


def consume_oauth_state(state: str, user_id: int | None = None) -> OAuthStateData | None:
    """
    Retrieve and remove OAuth state data with expiration and user validation.

    Args:
        state: The state parameter
        user_id: If provided, validates that the state belongs to this user

    Returns:
        OAuthStateData or None if not found, expired, or user mismatch
    """
    state_data = _oauth_states.pop(state, None)
    if state_data is None:
        return None

    # Check expiration
    age = datetime.now(timezone.utc) - state_data.created_at
    if age > timedelta(minutes=STATE_EXPIRATION_MINUTES):
        return None

    # Validate user if provided
    if user_id is not None and state_data.user_id != user_id:
        return None

    return state_data


def cleanup_expired_states() -> int:
    """
    Remove expired OAuth states from memory.

    Call this periodically to prevent memory leaks from abandoned OAuth flows.

    Returns:
        Number of expired states removed
    """
    now = datetime.now(timezone.utc)
    expired_threshold = timedelta(minutes=STATE_EXPIRATION_MINUTES)
    expired_states = [
        state
        for state, data in _oauth_states.items()
        if now - data.created_at > expired_threshold
    ]
    for state in expired_states:
        _oauth_states.pop(state, None)
    return len(expired_states)


def build_authorization_url(
    service_name: str,
    redirect_uri: str,
    user_id: int,
    provider_client_id: str | None = None,
) -> tuple[str, str]:
    """
    Build OAuth authorization URL for a service.

    Args:
        service_name: Name of the service
        redirect_uri: URL to redirect to after authorization
        user_id: ID of the user initiating the OAuth flow
        provider_client_id: Dynamic client_id for RFC 7591 providers (e.g., Dataverse).
            Required for providers with uses_dynamic_registration=True.

    Returns:
        Tuple of (authorization_url, state)

    Raises:
        ValueError: If service is unknown or not configured
    """
    config = get_provider_config(service_name)
    if config is None:
        raise ValueError(f"Unknown service or missing configuration: {service_name}")

    # For dynamic registration providers, use the provided client_id
    # Otherwise use the static client_id from config
    client_id = provider_client_id if config.uses_dynamic_registration else config.client_id

    if not client_id:
        raise ValueError(
            f"No client_id available for {service_name}. "
            f"Dynamic registration providers require provider_client_id parameter."
        )

    state = generate_oauth_state()
    code_verifier = None

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(config.scopes),
        "state": state,
    }

    # Add PKCE parameters if required
    if config.use_pkce:
        code_verifier, code_challenge = generate_pkce_pair()
        params["code_challenge"] = code_challenge
        params["code_challenge_method"] = "S256"

    # Add any extra parameters (like access_type=offline for Google)
    if config.extra_params:
        params.update(config.extra_params)

    # Store state for validation on callback (bound to user for security)
    # Include provider_client_id for dynamic registration providers
    state_data = OAuthStateData(
        service_name=service_name,
        redirect_uri=redirect_uri,
        user_id=user_id,
        code_verifier=code_verifier,
        provider_client_id=provider_client_id if config.uses_dynamic_registration else None,
    )
    store_oauth_state(state, state_data)

    url = f"{config.authorize_url}?{urlencode(params)}"
    return url, state


# =============================================================================
# Database-backed state management functions (for multi-replica deployments)
# =============================================================================


def store_oauth_state_db(
    session: Session,
    state: str,
    state_data: OAuthStateData,
) -> OAuthState:
    """
    Store OAuth state data in the database for later validation.

    Use this for multi-replica deployments where any instance
    can handle the OAuth callback.

    Args:
        session: Database session
        state: The state parameter to use as key
        state_data: Data to store (service name, redirect URI, PKCE verifier, provider_client_id)

    Returns:
        Created OAuthState object
    """
    return _store_oauth_state_db(
        session=session,
        state=state,
        user_id=state_data.user_id,
        service_name=state_data.service_name,
        redirect_uri=state_data.redirect_uri,
        code_verifier=state_data.code_verifier,
        provider_client_id=state_data.provider_client_id,
    )


def get_oauth_state_db(session: Session, state: str) -> OAuthStateData | None:
    """
    Retrieve OAuth state data from database without removing it.

    Args:
        session: Database session
        state: The state parameter

    Returns:
        OAuthStateData or None if not found
    """
    oauth_state = _get_oauth_state_db(session=session, state=state)
    if oauth_state is None:
        return None

    return OAuthStateData(
        service_name=oauth_state.service_name,
        redirect_uri=oauth_state.redirect_uri,
        user_id=oauth_state.user_id,
        code_verifier=oauth_state.code_verifier,
        provider_client_id=oauth_state.provider_client_id,
        created_at=oauth_state.created_at,
    )


def consume_oauth_state_db(
    session: Session,
    state: str,
    user_id: int | None = None,
) -> OAuthStateData | None:
    """
    Retrieve and remove OAuth state data from database with validation.

    Args:
        session: Database session
        state: The state parameter
        user_id: If provided, validates that the state belongs to this user

    Returns:
        OAuthStateData or None if not found, expired, or user mismatch
    """
    oauth_state = _consume_oauth_state_db(
        session=session,
        state=state,
        user_id=user_id,
    )
    if oauth_state is None:
        return None

    return OAuthStateData(
        service_name=oauth_state.service_name,
        redirect_uri=oauth_state.redirect_uri,
        user_id=oauth_state.user_id,
        code_verifier=oauth_state.code_verifier,
        provider_client_id=oauth_state.provider_client_id,
        created_at=oauth_state.created_at,
    )


def cleanup_expired_states_db(session: Session) -> int:
    """
    Remove expired OAuth states from the database.

    Call this periodically to prevent database bloat from abandoned OAuth flows.

    Args:
        session: Database session

    Returns:
        Number of expired states removed
    """
    return _cleanup_expired_states_db(session=session)


def build_authorization_url_db(
    session: Session,
    service_name: str,
    redirect_uri: str,
    user_id: int,
    provider_client_id: str | None = None,
) -> tuple[str, str]:
    """
    Build OAuth authorization URL for a service with database-backed state.

    Use this for multi-replica deployments where any instance
    can handle the OAuth callback.

    Args:
        session: Database session
        service_name: Name of the service
        redirect_uri: URL to redirect to after authorization
        user_id: ID of the user initiating the OAuth flow
        provider_client_id: Dynamic client_id for RFC 7591 providers (e.g., Dataverse).
            Required for providers with uses_dynamic_registration=True.

    Returns:
        Tuple of (authorization_url, state)

    Raises:
        ValueError: If service is unknown or not configured
    """
    config = get_provider_config(service_name)
    if config is None:
        raise ValueError(f"Unknown service or missing configuration: {service_name}")

    # For dynamic registration providers, use the provided client_id
    # Otherwise use the static client_id from config
    client_id = provider_client_id if config.uses_dynamic_registration else config.client_id

    if not client_id:
        raise ValueError(
            f"No client_id available for {service_name}. "
            f"Dynamic registration providers require provider_client_id parameter."
        )

    state = generate_oauth_state()
    code_verifier = None

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(config.scopes),
        "state": state,
    }

    # Add PKCE parameters if required
    if config.use_pkce:
        code_verifier, code_challenge = generate_pkce_pair()
        params["code_challenge"] = code_challenge
        params["code_challenge_method"] = "S256"

    # Add any extra parameters (like access_type=offline for Google)
    if config.extra_params:
        params.update(config.extra_params)

    # Store state in database for validation on callback
    # Include provider_client_id for dynamic registration providers
    _store_oauth_state_db(
        session=session,
        state=state,
        user_id=user_id,
        service_name=service_name,
        redirect_uri=redirect_uri,
        code_verifier=code_verifier,
        provider_client_id=provider_client_id if config.uses_dynamic_registration else None,
    )

    url = f"{config.authorize_url}?{urlencode(params)}"
    return url, state
