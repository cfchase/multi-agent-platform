"""
OAuth state cleanup service for removing expired states.

Provides both a synchronous cleanup function and an async background task
that can be scheduled during application lifespan.
"""

import asyncio
import logging

from sqlmodel import Session

from app.crud.oauth_state import cleanup_expired_states_db

logger = logging.getLogger(__name__)

# Default cleanup interval in seconds (5 minutes)
DEFAULT_CLEANUP_INTERVAL_SECONDS = 300


async def cleanup_expired_oauth_states(*, session: Session) -> int:
    """
    Clean up expired OAuth states from the database.

    This is the async wrapper for the synchronous cleanup function.

    Args:
        session: Database session

    Returns:
        Number of expired states removed
    """
    return cleanup_expired_states_db(session=session)


async def run_cleanup_task(
    *,
    get_session,
    interval_seconds: int = DEFAULT_CLEANUP_INTERVAL_SECONDS,
    stop_event: asyncio.Event | None = None,
) -> None:
    """
    Background task that periodically cleans up expired OAuth states.

    This task runs indefinitely until cancelled or stop_event is set.

    Args:
        get_session: Callable that returns a database session context manager
        interval_seconds: Time between cleanup runs
        stop_event: Optional event to signal task shutdown
    """
    logger.info(
        "OAuth state cleanup task started (interval: %d seconds)",
        interval_seconds,
    )

    while True:
        try:
            # Check if we should stop
            if stop_event is not None and stop_event.is_set():
                logger.info("OAuth state cleanup task stopping (stop event set)")
                break

            # Wait for the interval (or until stop_event is set)
            if stop_event is not None:
                try:
                    await asyncio.wait_for(
                        stop_event.wait(),
                        timeout=interval_seconds,
                    )
                    # If we get here, stop_event was set
                    logger.info("OAuth state cleanup task stopping (stop event set)")
                    break
                except asyncio.TimeoutError:
                    # Timeout means interval elapsed, continue to cleanup
                    pass
            else:
                await asyncio.sleep(interval_seconds)

            # Perform cleanup
            with get_session() as session:
                count = cleanup_expired_states_db(session=session)
                if count > 0:
                    logger.info("Cleaned up %d expired OAuth states", count)
                else:
                    logger.debug("No expired OAuth states to clean up")

        except asyncio.CancelledError:
            logger.info("OAuth state cleanup task cancelled")
            raise
        except Exception:
            logger.exception("Error in OAuth state cleanup task")
            # Continue running despite errors
            await asyncio.sleep(interval_seconds)

    logger.info("OAuth state cleanup task stopped")
