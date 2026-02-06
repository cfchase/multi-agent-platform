"""
CRUD operations module.
"""

from app.crud.user import (
    create_user,
    get_or_create_user,
    get_user_by_username,
    update_user_last_login,
)

from app.crud.integration import (
    create_or_update_integration,
    delete_integration,
    get_decrypted_tokens,
    get_missing_integrations,
    get_user_integration,
    get_user_integrations,
)

__all__ = [
    # User
    "create_user",
    "get_or_create_user",
    "get_user_by_username",
    "update_user_last_login",
    # Integration
    "create_or_update_integration",
    "delete_integration",
    "get_decrypted_tokens",
    "get_missing_integrations",
    "get_user_integration",
    "get_user_integrations",
]
