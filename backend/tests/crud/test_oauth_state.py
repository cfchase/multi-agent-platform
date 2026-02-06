"""
Tests for OAuth state CRUD operations.

Validates database-backed OAuth state storage for multi-replica support.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import Session

from app.crud.oauth_state import (
    cleanup_expired_states_db,
    consume_oauth_state_db,
    get_oauth_state_db,
    store_oauth_state_db,
)
from app.models import OAuthState, STATE_EXPIRATION_MINUTES


class TestStoreOAuthStateDb:
    """Tests for store_oauth_state_db."""

    def test_stores_oauth_state(self, session: Session):
        """Can store OAuth state in the database."""
        result = store_oauth_state_db(
            session=session,
            state="test-state-123",
            user_id=1,
            service_name="google_drive",
            redirect_uri="http://localhost:8000/callback",
        )

        assert result.state == "test-state-123"
        assert result.user_id == 1
        assert result.service_name == "google_drive"
        assert result.redirect_uri == "http://localhost:8000/callback"
        assert result.code_verifier is None

    def test_stores_oauth_state_with_code_verifier(self, session: Session):
        """Can store OAuth state with PKCE code verifier."""
        result = store_oauth_state_db(
            session=session,
            state="test-state-pkce",
            user_id=1,
            service_name="dataverse",
            redirect_uri="http://localhost:8000/callback",
            code_verifier="test-verifier-abc123",
        )

        assert result.code_verifier == "test-verifier-abc123"


class TestGetOAuthStateDb:
    """Tests for get_oauth_state_db."""

    def test_retrieves_stored_state(self, session: Session):
        """Can retrieve a stored OAuth state."""
        store_oauth_state_db(
            session=session,
            state="retrieve-test-state",
            user_id=1,
            service_name="google_drive",
            redirect_uri="http://localhost:8000/callback",
        )

        result = get_oauth_state_db(session=session, state="retrieve-test-state")

        assert result is not None
        assert result.user_id == 1

    def test_returns_none_for_unknown_state(self, session: Session):
        """Returns None for unknown state."""
        result = get_oauth_state_db(session=session, state="nonexistent-state")
        assert result is None


class TestConsumeOAuthStateDb:
    """Tests for consume_oauth_state_db."""

    def test_consumes_and_removes_state(self, session: Session):
        """Consume retrieves and removes the state."""
        store_oauth_state_db(
            session=session,
            state="consume-test-state",
            user_id=1,
            service_name="google_drive",
            redirect_uri="http://localhost:8000/callback",
        )

        # Consume the state
        result = consume_oauth_state_db(session=session, state="consume-test-state")
        assert result is not None
        assert result.user_id == 1

        # State should be gone
        second_result = get_oauth_state_db(session=session, state="consume-test-state")
        assert second_result is None

    def test_validates_user_id(self, session: Session):
        """Consume validates user_id when provided."""
        store_oauth_state_db(
            session=session,
            state="user-validation-state",
            user_id=1,
            service_name="google_drive",
            redirect_uri="http://localhost:8000/callback",
        )

        # Wrong user_id should fail
        result = consume_oauth_state_db(
            session=session,
            state="user-validation-state",
            user_id=999,
        )
        assert result is None

        # State should still exist (not consumed on mismatch)
        still_exists = get_oauth_state_db(
            session=session,
            state="user-validation-state",
        )
        assert still_exists is not None

    def test_consumes_without_user_validation(self, session: Session):
        """Consume works without user_id validation (for callback flow)."""
        store_oauth_state_db(
            session=session,
            state="no-user-validation-state",
            user_id=1,
            service_name="google_drive",
            redirect_uri="http://localhost:8000/callback",
        )

        # Should work without user_id
        result = consume_oauth_state_db(
            session=session,
            state="no-user-validation-state",
        )
        assert result is not None
        assert result.user_id == 1

    def test_rejects_expired_state(self, session: Session):
        """Consume rejects expired states."""
        old_time = datetime.now(timezone.utc) - timedelta(
            minutes=STATE_EXPIRATION_MINUTES + 1
        )
        oauth_state = OAuthState(
            state="expired-consume-state",
            user_id=1,
            service_name="google_drive",
            redirect_uri="http://localhost:8000/callback",
            created_at=old_time,
        )
        session.add(oauth_state)
        session.commit()

        # Consume should reject expired state
        result = consume_oauth_state_db(session=session, state="expired-consume-state")
        assert result is None

        # Expired state should be cleaned up
        still_exists = get_oauth_state_db(
            session=session,
            state="expired-consume-state",
        )
        assert still_exists is None

    def test_returns_none_for_unknown_state(self, session: Session):
        """Consume returns None for unknown state."""
        result = consume_oauth_state_db(session=session, state="nonexistent-state")
        assert result is None


class TestCleanupExpiredStatesDb:
    """Tests for cleanup_expired_states_db."""

    def test_cleans_up_expired_states(self, session: Session):
        """Removes expired states from database."""
        old_time = datetime.now(timezone.utc) - timedelta(
            minutes=STATE_EXPIRATION_MINUTES + 5
        )

        # Create expired states
        for i in range(3):
            oauth_state = OAuthState(
                state=f"expired-cleanup-{i}",
                user_id=1,
                service_name="google_drive",
                redirect_uri="http://localhost:8000/callback",
                created_at=old_time,
            )
            session.add(oauth_state)
        session.commit()

        # Clean up
        count = cleanup_expired_states_db(session=session)
        assert count == 3

        # States should be gone
        for i in range(3):
            result = get_oauth_state_db(session=session, state=f"expired-cleanup-{i}")
            assert result is None

    def test_does_not_remove_fresh_states(self, session: Session):
        """Cleanup does not remove fresh states."""
        store_oauth_state_db(
            session=session,
            state="fresh-state-to-keep",
            user_id=1,
            service_name="google_drive",
            redirect_uri="http://localhost:8000/callback",
        )

        count = cleanup_expired_states_db(session=session)
        assert count == 0

        # Fresh state should still exist
        result = get_oauth_state_db(session=session, state="fresh-state-to-keep")
        assert result is not None

    def test_returns_zero_when_no_expired_states(self, session: Session):
        """Cleanup returns 0 when no states are expired."""
        count = cleanup_expired_states_db(session=session)
        assert count == 0
