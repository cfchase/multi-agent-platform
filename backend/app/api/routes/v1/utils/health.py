import logging

from fastapi import APIRouter
from sqlmodel import select

from app.api.deps import SessionDep

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health-check")
async def health_check(session: SessionDep):
    """
    Health check endpoint that verifies backend and database connectivity.
    """
    # Check database connectivity by executing a simple query
    try:
        # Execute a simple query to verify database connection
        session.exec(select(1)).first()
        db_status = "healthy"
        db_message = "Database connection successful"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "unhealthy"
        db_message = "Database connection failed"

    # Overall status is healthy only if database is healthy
    overall_status = "healthy" if db_status == "healthy" else "unhealthy"

    return {
        "status": overall_status,
        "message": "Backend is running",
        "database": {"status": db_status, "message": db_message},
    }