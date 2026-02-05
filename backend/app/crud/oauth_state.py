"""
CRUD operations for OAuthState model.

Handles creation, retrieval, consumption, and cleanup of OAuth states
stored in the database for multi-replica support.
"""

from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.models import OAuthState, STATE_EXPIRATION_MINUTES


def store_oauth_state_db(
    *,
    session: Session,
    state: str,
    user_id: int,
    service_name: str,
    redirect_uri: str,
    code_verifier: str | None = None,
    provider_client_id: str | None = None,
) -> OAuthState:
    """
    Store OAuth state in the database.

    Args:
        session: Database session
        state: Cryptographically secure state string
        user_id: ID of the user initiating the OAuth flow
        service_name: Name of the OAuth service
        redirect_uri: The redirect URI for the OAuth callback
        code_verifier: PKCE code verifier (optional)
        provider_client_id: Dynamic client_id for RFC 7591 providers (optional)

    Returns:
        Created OAuthState object
    """
    oauth_state = OAuthState(
        state=state,
        user_id=user_id,
        service_name=service_name,
        redirect_uri=redirect_uri,
        code_verifier=code_verifier,
        provider_client_id=provider_client_id,
    )
    session.add(oauth_state)
    session.commit()
    session.refresh(oauth_state)
    return oauth_state


def get_oauth_state_db(
    *,
    session: Session,
    state: str,
) -> OAuthState | None:
    """
    Retrieve OAuth state from the database without removing it.

    Args:
        session: Database session
        state: The state string to look up

    Returns:
        OAuthState if found, None otherwise
    """
    return session.get(OAuthState, state)


def consume_oauth_state_db(
    *,
    session: Session,
    state: str,
    user_id: int | None = None,
) -> OAuthState | None:
    """
    Retrieve and remove OAuth state from the database with validation.

    Performs expiration check and optional user validation.

    Args:
        session: Database session
        state: The state string to look up
        user_id: If provided, validates that the state belongs to this user

    Returns:
        OAuthState if valid, None if not found, expired, or user mismatch
    """
    oauth_state = session.get(OAuthState, state)
    if oauth_state is None:
        return None

    # Check expiration
    if oauth_state.is_expired():
        # Clean up expired state
        session.delete(oauth_state)
        session.commit()
        return None

    # Validate user if provided
    if user_id is not None and oauth_state.user_id != user_id:
        return None

    # Remove the state (consume it)
    session.delete(oauth_state)
    session.commit()

    return oauth_state


def cleanup_expired_states_db(*, session: Session) -> int:
    """
    Remove all expired OAuth states from the database.

    Call this periodically to prevent database bloat from abandoned OAuth flows.

    Args:
        session: Database session

    Returns:
        Number of expired states removed
    """
    expiration_threshold = datetime.now(timezone.utc) - timedelta(
        minutes=STATE_EXPIRATION_MINUTES
    )

    # Find expired states
    statement = select(OAuthState).where(OAuthState.created_at < expiration_threshold)
    expired_states = session.exec(statement).all()

    count = len(expired_states)
    for state in expired_states:
        session.delete(state)

    if count > 0:
        session.commit()

    return count
