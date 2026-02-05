"""
Tests for OAuth state cleanup background task.

Validates the periodic cleanup of expired OAuth states from the database.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import Session

from app.models import OAuthState, STATE_EXPIRATION_MINUTES
from app.services.oauth_state_cleanup import cleanup_expired_oauth_states


class TestCleanupExpiredOAuthStates:
    """Tests for cleanup_expired_oauth_states function."""

    @pytest.mark.asyncio
    async def test_cleans_up_expired_states(self, session: Session):
        """Removes expired states from database."""
        old_time = datetime.now(timezone.utc) - timedelta(
            minutes=STATE_EXPIRATION_MINUTES + 5
        )

        # Create expired states
        for i in range(3):
            oauth_state = OAuthState(
                state=f"expired-cleanup-task-{i}",
                user_id=1,
                service_name="google_drive",
                redirect_uri="http://localhost:8000/callback",
                created_at=old_time,
            )
            session.add(oauth_state)
        session.commit()

        # Run cleanup
        count = await cleanup_expired_oauth_states(session=session)
        assert count == 3

        # States should be gone
        for i in range(3):
            result = session.get(OAuthState, f"expired-cleanup-task-{i}")
            assert result is None

    @pytest.mark.asyncio
    async def test_does_not_remove_fresh_states(self, session: Session):
        """Cleanup does not remove fresh states."""
        fresh_state = OAuthState(
            state="fresh-state-cleanup-test",
            user_id=1,
            service_name="google_drive",
            redirect_uri="http://localhost:8000/callback",
        )
        session.add(fresh_state)
        session.commit()

        count = await cleanup_expired_oauth_states(session=session)
        assert count == 0

        # Fresh state should still exist
        result = session.get(OAuthState, "fresh-state-cleanup-test")
        assert result is not None

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_states(self, session: Session):
        """Cleanup returns 0 when no states exist."""
        count = await cleanup_expired_oauth_states(session=session)
        assert count == 0
