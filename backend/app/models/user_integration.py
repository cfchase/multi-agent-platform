"""
UserIntegration model for storing OAuth tokens for external services.

This module contains:
- UserIntegration database model (stores encrypted OAuth tokens)
- UserIntegrationPublic: Output schema (never exposes tokens)
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, LargeBinary
from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint

if TYPE_CHECKING:
    from app.models.user import User


class UserIntegration(SQLModel, table=True):
    """
    Stores OAuth tokens for external service integrations.

    Each user can have one integration per service (e.g., google_drive, dataverse).
    Tokens are encrypted at rest using Fernet encryption.

    Attributes:
        user_id: Foreign key to the user who owns this integration.
        service_name: Name of the external service (e.g., "google_drive", "dataverse").
        access_token_encrypted: Fernet-encrypted OAuth access token.
        refresh_token_encrypted: Fernet-encrypted OAuth refresh token (optional).
        expires_at: When the access token expires (UTC).
        scopes: Space-separated list of OAuth scopes granted.
        token_type: Token type, typically "Bearer".
    """

    __tablename__ = "user_integrations"
    __table_args__ = (
        UniqueConstraint("user_id", "service_name", name="uq_user_integration_service"),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True, ondelete="CASCADE")
    service_name: str = Field(max_length=50, index=True)

    # Encrypted token storage (bytes)
    access_token_encrypted: bytes = Field(sa_column=Column(LargeBinary, nullable=False))
    refresh_token_encrypted: bytes | None = Field(
        default=None, sa_column=Column(LargeBinary, nullable=True)
    )

    # Token metadata
    expires_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True)
    )
    scopes: str | None = Field(default=None, max_length=1000)
    token_type: str = Field(default="Bearer", max_length=50)

    # Dynamic client registration metadata
    # Stores the dynamically registered client_id for providers that use RFC 7591
    # (e.g., Dataverse). This is needed for token refresh with dynamic clients.
    provider_client_id: str | None = Field(default=None, max_length=255)

    # Timestamps
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )

    # Relationship to user
    user: "User" = Relationship(back_populates="integrations")

    def is_expired(self) -> bool:
        """
        Check if the access token has expired.

        Returns:
            True if token is expired, False if valid or no expiry set.
        """
        if self.expires_at is None:
            return False

        now = datetime.now(timezone.utc)
        expires = self.expires_at

        # Handle naive datetime (e.g., from SQLite in tests)
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)

        return now > expires

    def is_expiring_soon(self, minutes: int = 5) -> bool:
        """
        Check if the access token expires within the given minutes.

        Args:
            minutes: Number of minutes to check ahead.

        Returns:
            True if token expires within the time window.
        """
        if self.expires_at is None:
            return False
        from datetime import timedelta

        threshold = datetime.now(timezone.utc) + timedelta(minutes=minutes)
        expires = self.expires_at

        # Handle naive datetime (e.g., from SQLite in tests)
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)

        return expires < threshold


class UserIntegrationPublic(SQLModel):
    """
    Public schema for UserIntegration - NEVER exposes tokens.

    Used for API responses to show integration status without
    revealing sensitive token data.
    """

    id: int
    service_name: str
    expires_at: datetime | None
    scopes: str | None
    is_connected: bool = True
    is_expired: bool
    created_at: datetime
    updated_at: datetime
