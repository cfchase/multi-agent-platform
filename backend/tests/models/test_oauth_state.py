"""
Tests for OAuthState model.

Validates database-backed OAuth state storage for multi-replica support.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import Session

from app.models import OAuthState, STATE_EXPIRATION_MINUTES


class TestOAuthStateModel:
    """Tests for OAuthState database model."""

    def test_create_oauth_state(self, session: Session):
        """Can create and retrieve an OAuth state."""
        state = OAuthState(
            state="test-state-abc123",
            user_id=1,
            service_name="google_drive",
            redirect_uri="http://localhost:8000/callback",
        )
        session.add(state)
        session.commit()

        retrieved = session.get(OAuthState, "test-state-abc123")
        assert retrieved is not None
        assert retrieved.user_id == 1
        assert retrieved.service_name == "google_drive"
        assert retrieved.redirect_uri == "http://localhost:8000/callback"
        assert retrieved.code_verifier is None

    def test_create_oauth_state_with_pkce(self, session: Session):
        """Can create OAuth state with PKCE code verifier."""
        state = OAuthState(
            state="test-state-pkce",
            user_id=1,
            service_name="dataverse",
            redirect_uri="http://localhost:8000/callback",
            code_verifier="test-code-verifier-abc123",
        )
        session.add(state)
        session.commit()

        retrieved = session.get(OAuthState, "test-state-pkce")
        assert retrieved is not None
        assert retrieved.code_verifier == "test-code-verifier-abc123"

    def test_oauth_state_is_expired_false_when_fresh(self, session: Session):
        """is_expired returns False for fresh state."""
        state = OAuthState(
            state="test-fresh-state",
            user_id=1,
            service_name="google_drive",
            redirect_uri="http://localhost:8000/callback",
        )
        session.add(state)
        session.commit()

        retrieved = session.get(OAuthState, "test-fresh-state")
        assert retrieved.is_expired() is False

    def test_oauth_state_is_expired_true_when_old(self, session: Session):
        """is_expired returns True for state older than expiration threshold."""
        old_time = datetime.now(timezone.utc) - timedelta(
            minutes=STATE_EXPIRATION_MINUTES + 1
        )
        state = OAuthState(
            state="test-expired-state",
            user_id=1,
            service_name="google_drive",
            redirect_uri="http://localhost:8000/callback",
            created_at=old_time,
        )
        session.add(state)
        session.commit()

        retrieved = session.get(OAuthState, "test-expired-state")
        assert retrieved.is_expired() is True

    def test_oauth_state_is_not_expired_at_boundary(self, session: Session):
        """is_expired returns False at exactly the expiration threshold."""
        # Just under the threshold
        boundary_time = datetime.now(timezone.utc) - timedelta(
            minutes=STATE_EXPIRATION_MINUTES - 1
        )
        state = OAuthState(
            state="test-boundary-state",
            user_id=1,
            service_name="google_drive",
            redirect_uri="http://localhost:8000/callback",
            created_at=boundary_time,
        )
        session.add(state)
        session.commit()

        retrieved = session.get(OAuthState, "test-boundary-state")
        assert retrieved.is_expired() is False

    def test_oauth_state_primary_key_is_state(self, session: Session):
        """State string is the primary key."""
        state = OAuthState(
            state="unique-state-key",
            user_id=1,
            service_name="google_drive",
            redirect_uri="http://localhost:8000/callback",
        )
        session.add(state)
        session.commit()

        # Can retrieve by state key
        retrieved = session.get(OAuthState, "unique-state-key")
        assert retrieved is not None

    def test_delete_oauth_state(self, session: Session):
        """Can delete an OAuth state."""
        state = OAuthState(
            state="state-to-delete",
            user_id=1,
            service_name="google_drive",
            redirect_uri="http://localhost:8000/callback",
        )
        session.add(state)
        session.commit()

        # Delete it
        session.delete(state)
        session.commit()

        # Should be gone
        retrieved = session.get(OAuthState, "state-to-delete")
        assert retrieved is None
