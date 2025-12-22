"""Configure SQLModel metadata with application schema.

IMPORTANT: This module MUST be imported before any models to ensure
the schema is set on SQLModel.metadata before table definitions.

The schema name can be configured via the APP_SCHEMA constant.
Set to None to use the default 'public' schema.

For production applications, consider using a custom schema for:
- Better database organization
- Easier multi-tenant support
- Simpler backups/restores
"""

from sqlmodel import SQLModel

# Application schema - all tables will be created here
# Set to None to use default 'public' schema
# Change this to your app name for production (e.g., "my_app")
APP_SCHEMA: str | None = None  # Uses 'public' schema by default

# Configure SQLModel metadata to use application schema
# This must happen before any Table/model definitions
if APP_SCHEMA:
    SQLModel.metadata.schema = APP_SCHEMA
