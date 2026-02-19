"""
Application configuration with environment-based settings.

This module uses Pydantic Settings for automatic environment variable loading
and validation following FastAPI best practices.
"""

import os
import secrets
import tomllib
from base64 import urlsafe_b64encode
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import (
    AnyUrl,
    BeforeValidator,
    PostgresDsn,
    computed_field,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_cors(v: Any) -> list[str] | str:
    """Parse CORS origins from string or list"""
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",") if i.strip()]
    elif isinstance(v, list | str):
        return v
    raise ValueError(v)


def _load_app_version_from_pyproject() -> str:
    """Load application version from pyproject.toml"""
    try:
        pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"

        if not pyproject_path.exists():
            # Fallback for when running from different directories
            return "0.0.0"

        with open(pyproject_path, "rb") as f:
            config = tomllib.load(f)
            version = config.get("project", {}).get("version")

            if not version:
                return "0.0.0"

            return version

    except Exception:
        return "0.0.0"


class Settings(BaseSettings):
    """
    Application settings with validation.

    Uses Pydantic Settings for automatic environment variable loading
    and validation following FastAPI best practices.

    All settings have sensible defaults for local development,
    allowing zero-config startup.
    """

    model_config = SettingsConfigDict(
        # Disable .env loading when TESTING=1 (set by conftest.py)
        # This ensures tests use only explicitly set env vars
        env_file=None if os.getenv("TESTING") else ".env",
        env_ignore_empty=True,
        extra="ignore",
        case_sensitive=True,
    )

    # API Configuration
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Multi-Agent Platform"
    APP_VERSION: str = _load_app_version_from_pyproject()
    PORT: int = 8000

    # Security
    SECRET_KEY: str = secrets.token_urlsafe(32)

    # Environment
    ENVIRONMENT: Literal["local", "development", "staging", "production"] = "local"

    # Frontend Configuration
    # Set to the frontend URL to ensure OAuth redirects go to the frontend.
    # In local dev: http://localhost:4180 (via OAuth proxy). In cluster: auto-detected from route.
    FRONTEND_HOST: str | None = None

    # CORS Configuration
    BACKEND_CORS_ORIGINS: Annotated[
        list[AnyUrl] | str, BeforeValidator(parse_cors)
    ] = []

    @computed_field  # type: ignore[prop-decorator]
    @property
    def all_cors_origins(self) -> list[str]:
        """Get all CORS origins including frontend host"""
        origins = [str(origin).rstrip("/") for origin in self.BACKEND_CORS_ORIGINS]
        if self.FRONTEND_HOST:
            origins.append(self.FRONTEND_HOST)
        return origins

    # Database Configuration (PostgreSQL)
    # All fields have defaults for zero-config local development
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "app"
    POSTGRES_PASSWORD: str = "changethis"
    POSTGRES_DB: str = "app"

    # Langflow Configuration
    # Used for chat AI backend integration
    #
    # In Kubernetes, these are typically populated from secrets:
    #   - LANGFLOW_API_KEY from a Secret (e.g., langflow-credentials)
    #   - Other values from ConfigMap or environment
    #
    # Set LANGFLOW_URL="mock" to use MockLangflowClient for testing
    LANGFLOW_URL: str = "http://localhost:7860"
    LANGFLOW_API_KEY: str | None = None  # Bearer token for auth (from K8s secret)
    LANGFLOW_ID: str | None = None  # Langflow Cloud project ID (optional)
    LANGFLOW_DEFAULT_FLOW: str | None = None  # Default flow name to execute

    # OAuth Integration Configuration
    # Token encryption key for secure storage of OAuth tokens
    # Auto-generated for local/dev (tokens won't survive key changes across restarts).
    # For production, set explicitly and persist:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    TOKEN_ENCRYPTION_KEY: str = urlsafe_b64encode(secrets.token_bytes(32)).decode()

    # LLM API Keys
    # Used by the backend to inject application-level API keys into flows via tweaks.
    # Also available as LangFlow global variables (via config/langflow.env) for direct UI testing.
    OPENAI_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # Google Drive OAuth
    # Register at: https://console.cloud.google.com/apis/credentials
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None

    # Dataverse OAuth
    # Dataverse uses dynamic client registration (RFC 7591), so no pre-configured
    # client credentials are required. Only DATAVERSE_AUTH_URL is needed.
    # The client_id is obtained dynamically when starting the OAuth flow.
    # Endpoints: {auth_url}/authorize, {auth_url}/token, {auth_url}/register
    DATAVERSE_CLIENT_ID: str | None = None  # NOT USED - dynamic registration
    DATAVERSE_CLIENT_SECRET: str | None = None  # NOT USED - public client (PKCE)
    DATAVERSE_AUTH_URL: str | None = "https://mcp.dataverse.redhat.com/auth"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> PostgresDsn:
        """Build PostgreSQL connection string"""
        return PostgresDsn.build(
            scheme="postgresql+psycopg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_SERVER,
            port=self.POSTGRES_PORT,
            path=self.POSTGRES_DB,
        )


# Create settings instance
settings = Settings()
