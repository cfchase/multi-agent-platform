"""
Application configuration with environment-based settings.

This module uses Pydantic Settings for automatic environment variable loading
and validation following FastAPI best practices.
"""

import os
import secrets
import tomllib
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
    PROJECT_NAME: str = "PatternFly FastAPI Template"
    APP_VERSION: str = _load_app_version_from_pyproject()
    PORT: int = 8000

    # Security
    SECRET_KEY: str = secrets.token_urlsafe(32)

    # Environment
    ENVIRONMENT: Literal["local", "development", "staging", "production"] = "local"

    # Frontend Configuration
    FRONTEND_HOST: str = "http://localhost:8080"

    # CORS Configuration
    BACKEND_CORS_ORIGINS: Annotated[
        list[AnyUrl] | str, BeforeValidator(parse_cors)
    ] = []

    @computed_field  # type: ignore[prop-decorator]
    @property
    def all_cors_origins(self) -> list[str]:
        """Get all CORS origins including frontend host"""
        return [str(origin).rstrip("/") for origin in self.BACKEND_CORS_ORIGINS] + [
            self.FRONTEND_HOST
        ]

    # Database Configuration (PostgreSQL)
    # All fields have defaults for zero-config local development
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "app"
    POSTGRES_PASSWORD: str = "changethis"
    POSTGRES_DB: str = "app"

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
