"""
OAuthState model for storing OAuth flow state in the database.

This replaces in-memory state storage to support multi-replica deployments
where any instance can handle the OAuth callback.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel


# OAuth state expiration time (10 minutes)
STATE_EXPIRATION_MINUTES = 10


class OAuthState(SQLModel, table=True):
    """
    Stores OAuth state data for validation during OAuth callback.

    This enables multi-replica support where any application instance
    can handle the OAuth callback by looking up state in the database.

    Attributes:
        state: Cryptographically secure random string (primary key)
        user_id: ID of the user who initiated the OAuth flow
        service_name: Name of the OAuth service (google_drive, dataverse)
        code_verifier: PKCE code verifier for services that require it
        redirect_uri: The redirect URI used in the authorization request
        created_at: When this state was created (for expiration check)
    """

    __tablename__ = "oauth_states"

    state: str = Field(primary_key=True, max_length=64)
    user_id: int = Field(index=True)
    service_name: str = Field(max_length=50)
    code_verifier: str | None = Field(default=None, max_length=128)
    redirect_uri: str = Field(max_length=500)
    provider_client_id: str | None = Field(default=None, max_length=255)  # RFC 7591 dynamic client_id
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )

    def is_expired(self) -> bool:
        """
        Check if this OAuth state has expired.

        Returns:
            True if state is older than STATE_EXPIRATION_MINUTES.
        """
        now = datetime.now(timezone.utc)
        created = self.created_at

        # Handle naive datetime (e.g., from SQLite in tests)
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)

        age = now - created
        return age > timedelta(minutes=STATE_EXPIRATION_MINUTES)
