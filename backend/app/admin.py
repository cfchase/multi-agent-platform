"""
SQLAdmin configuration for administrative interface.

This module provides a web-based admin panel for managing database models.
The admin panel is mounted at /admin and provides CRUD operations for:
- Users: View and manage OAuth-authenticated users
- Items: View and manage user-created items

Access Control:
- In production, protect /admin with OAuth2 proxy or network policies
- The admin uses the same database connection as the main app
"""

from sqladmin import Admin, ModelView
from sqlalchemy import Engine

from app.models import Item, User


class UserAdmin(ModelView, model=User):
    """Admin view for User model with OAuth context."""

    name = "User"
    name_plural = "Users"
    icon = "fa-solid fa-user"

    # List view configuration
    column_list = [
        User.id,
        User.username,
        User.email,
        User.full_name,
        User.admin,
        User.active,
        User.last_login,
    ]

    # Search configuration
    column_searchable_list = [User.username, User.email, User.full_name]

    # Filter configuration
    column_sortable_list = [
        User.id,
        User.username,
        User.email,
        User.admin,
        User.active,
        User.last_login,
        User.created_at,
    ]

    # Form configuration - exclude auto-generated fields
    form_excluded_columns = [
        User.items,  # Relationship managed separately
        User.created_at,
        User.updated_at,
    ]

    # Detail view columns
    column_details_list = [
        User.id,
        User.username,
        User.email,
        User.full_name,
        User.admin,
        User.active,
        User.created_at,
        User.last_login,
        User.updated_at,
    ]

    # Export configuration
    can_export = True
    column_export_list = [
        User.id,
        User.username,
        User.email,
        User.full_name,
        User.admin,
        User.active,
        User.created_at,
        User.last_login,
    ]


class ItemAdmin(ModelView, model=Item):
    """Admin view for Item model."""

    name = "Item"
    name_plural = "Items"
    icon = "fa-solid fa-box"

    # List view configuration
    column_list = [
        Item.id,
        Item.title,
        Item.description,
        Item.owner,
    ]

    # Search configuration
    column_searchable_list = [Item.title, Item.description]

    # Filter configuration
    column_sortable_list = [Item.id, Item.title]

    # Detail view columns
    column_details_list = [
        Item.id,
        Item.title,
        Item.description,
        Item.owner,
        Item.owner_id,
    ]

    # Export configuration
    can_export = True


def setup_admin(app, engine: Engine) -> Admin:
    """
    Set up SQLAdmin with the FastAPI application.

    Args:
        app: FastAPI application instance
        engine: SQLAlchemy engine for database connection

    Returns:
        Admin instance configured with all model views
    """
    admin = Admin(
        app,
        engine,
        title="Template Admin",
        logo_url=None,  # Optional: Add logo URL
    )

    # Register model views
    admin.add_view(UserAdmin)
    admin.add_view(ItemAdmin)

    return admin
