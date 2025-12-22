"""
Main FastAPI application entry point.

This module sets up the FastAPI application with:
- CORS middleware
- Request logging middleware
- API routes (REST)
- GraphQL endpoint
- Admin panel (SQLAdmin)
- Lifespan handler with configuration logging
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session
from strawberry.fastapi import GraphQLRouter
import uvicorn

from app.admin import setup_admin
from app.api.router import router as api_router
from app.api.deps import get_db, get_current_user
from app.core.config import settings
from app.core.db import engine
from app.core.logging import setup_logging
from app.core.middleware import RequestLoggingMiddleware
from app.graphql_api.schema import schema
from app.graphql_api.loaders import create_loaders

# Setup logging before anything else
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Handle application startup and shutdown.

    This is the modern way to handle lifecycle events in FastAPI,
    replacing the deprecated @app.on_event decorators.
    """
    # Startup
    logger.info("=" * 60)
    logger.info(f"{settings.PROJECT_NAME} v{settings.APP_VERSION} - Starting Up")
    logger.info("=" * 60)
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Database: {settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}")
    logger.info(f"CORS Origins: {settings.all_cors_origins}")
    logger.info("=" * 60)
    yield
    # Shutdown (if needed)
    logger.info(f"{settings.PROJECT_NAME} - Shutting Down")


# GraphQL context using FastAPI dependency injection
async def get_graphql_context(
    session: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> dict[str, Any]:
    """
    Create GraphQL context with database session, authenticated user, and DataLoaders.

    This function is called for each GraphQL request to provide:
    - Database session for queries
    - Current authenticated user (OAuth)
    - DataLoaders for efficient batching and caching of related data

    DataLoaders prevent N+1 query problems by batching multiple individual
    queries into a single database query.

    All GraphQL requests require OAuth authentication (same as REST API).
    In local dev mode (ENVIRONMENT=local), falls back to dev-user.
    """
    return {
        "session": session,
        "current_user": current_user,
        "loaders": create_loaders(session),
    }


graphql_app = GraphQLRouter(
    schema,
    context_getter=get_graphql_context,
    graphiql=True,  # OAuth authentication protects this endpoint
)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="A full-stack template API built with FastAPI",
    version=settings.APP_VERSION,
    redirect_slashes=False,
    lifespan=lifespan,
)

# Configure CORS using settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.all_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request logging middleware
# Note: Add this last so it's the first to process requests (middleware executes in reverse order)
app.add_middleware(RequestLoggingMiddleware)


# Include API routes
app.include_router(api_router, prefix="/api")

# Include GraphQL endpoint under /api for consistent proxy handling
app.include_router(graphql_app, prefix="/api/graphql")

# Setup Admin panel (available at /admin)
# Note: In production, protect /admin with OAuth2 proxy or network policies
setup_admin(app, engine)


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": f"{settings.PROJECT_NAME} API",
        "version": settings.APP_VERSION,
        "rest_api": "/api/v1/",
        "graphql_api": "/api/graphql",
        "graphql_playground": "/api/graphql (open in browser)",
        "admin": "/admin",
        "docs": "/docs",
    }


if __name__ == "__main__":
    port = int(os.getenv("PORT", settings.PORT))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
