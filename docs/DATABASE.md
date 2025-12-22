# Database Guide

## Overview

- **Database**: PostgreSQL 15
- **ORM**: SQLModel (SQLAlchemy + Pydantic)
- **Migrations**: Alembic
- **Container**: Docker/Podman for local development

## Quick Reference

```bash
# Database Container
make db-start      # Start PostgreSQL
make db-stop       # Stop PostgreSQL
make db-status     # Check if running
make db-shell      # Open psql shell
make db-logs       # View logs
make db-reset      # Delete all data (DESTRUCTIVE)

# Migrations
cd backend
uv run alembic revision --autogenerate -m "description"  # Create
uv run alembic upgrade head                               # Apply
uv run alembic downgrade -1                               # Rollback
uv run alembic history                                     # View history
uv run alembic current                                     # Current version

# Seeding
make db-seed       # Populate with test data
```

## Configuration

### Local Development

Default configuration in `backend/.env`:
```bash
POSTGRES_SERVER=localhost
POSTGRES_PORT=5432
POSTGRES_USER=app
POSTGRES_PASSWORD=changethis
POSTGRES_DB=app
```

### Container Details
- **Container Name**: `app-postgres-dev`
- **Volume**: `app-db-data` (persistent storage)
- **Port**: 5432 (exposed to host)
- **Image**: `postgres:15-alpine`

## Models

### Defining Models

```python
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime
import uuid

class User(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: str = Field(unique=True, index=True)
    full_name: str
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    items: List["Item"] = Relationship(back_populates="owner")

class Item(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=1000)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Foreign Key
    owner_id: uuid.UUID = Field(foreign_key="user.id")

    # Relationships
    owner: Optional[User] = Relationship(back_populates="items")
```

### Relationship Patterns

**One-to-Many (User → Items):**
```python
class User(SQLModel, table=True):
    items: List["Item"] = Relationship(
        back_populates="owner",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
# Deleting User also deletes their Items
```

**Many-to-Many (Items ↔ Tags):**
```python
class ItemTag(SQLModel, table=True):
    """Join table for Item-Tag relationship."""
    item_id: uuid.UUID = Field(
        foreign_key="item.id",
        primary_key=True,
        ondelete="CASCADE"
    )
    tag_id: uuid.UUID = Field(
        foreign_key="tag.id",
        primary_key=True,
        ondelete="CASCADE"
    )

class Item(SQLModel, table=True):
    tags: List["Tag"] = Relationship(
        back_populates="items",
        link_model=ItemTag
        # NO cascade here - don't delete Tags when Item deleted
    )

class Tag(SQLModel, table=True):
    items: List["Item"] = Relationship(
        back_populates="tags",
        link_model=ItemTag
    )
# Deleting Item removes ItemTag entries, but NOT Tag entities
```

### Cascade Rules

| Relationship | Cascade Pattern | Result |
|--------------|-----------------|--------|
| One-to-Many | `cascade="all, delete-orphan"` | Delete children with parent |
| Many-to-Many | No cascade on relationship | Only delete join table entries |
| Join Tables | `ondelete="CASCADE"` on FKs | Clean up when either side deleted |

**CRITICAL**: Never use `cascade="all, delete"` on many-to-many relationships!

## Migrations

### Creating Migrations

1. Modify models in `backend/app/models.py`
2. Generate migration:
   ```bash
   cd backend
   uv run alembic revision --autogenerate -m "Add user email field"
   ```
3. **CRITICAL**: Review generated file in `backend/alembic/versions/`
4. Apply:
   ```bash
   uv run alembic upgrade head
   ```

### Migration File Structure

```python
"""Add user email field

Revision ID: abc123
Revises: def456
Create Date: 2024-01-15 10:30:00

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers
revision = 'abc123'
down_revision = 'def456'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('user', sa.Column('email', sa.String(), nullable=False))
    op.create_index('ix_user_email', 'user', ['email'], unique=True)

def downgrade() -> None:
    op.drop_index('ix_user_email', table_name='user')
    op.drop_column('user', 'email')
```

### Migration Commands

```bash
# Apply all pending migrations
uv run alembic upgrade head

# Rollback one migration
uv run alembic downgrade -1

# Rollback to specific revision
uv run alembic downgrade abc123

# View migration history
uv run alembic history

# View current revision
uv run alembic current

# View pending migrations
uv run alembic heads
```

### Review Checklist

Before applying any migration, check for:

- [ ] `DROP TABLE` statements (data loss!)
- [ ] `DROP COLUMN` statements (data loss!)
- [ ] Correct foreign key constraints
- [ ] Expected cascade behavior
- [ ] Nullable fields match model
- [ ] Default values are correct

## Querying

### Basic Queries

```python
from sqlmodel import Session, select
from app.models import Item, User

# Get by ID
item = session.get(Item, item_id)

# List all
statement = select(Item)
items = session.exec(statement).all()

# Filter
statement = select(Item).where(Item.owner_id == user_id)
items = session.exec(statement).all()

# Pagination
statement = select(Item).offset(skip).limit(limit)
items = session.exec(statement).all()

# Order by
statement = select(Item).order_by(Item.created_at.desc())
items = session.exec(statement).all()
```

### Relationships

```python
# Get with relationship
statement = select(Item).where(Item.id == item_id)
item = session.exec(statement).first()
owner = item.owner  # Lazy loads User

# Eager loading (prevent N+1)
from sqlalchemy.orm import selectinload

statement = (
    select(Item)
    .options(selectinload(Item.owner))
    .where(Item.id == item_id)
)
item = session.exec(statement).first()
```

### Joins

```python
# Inner join
statement = (
    select(Item, User)
    .join(User)
    .where(User.is_active == True)
)
results = session.exec(statement).all()

# Left join
statement = (
    select(Item, User)
    .outerjoin(User)
)
results = session.exec(statement).all()
```

## Common Operations

### Create

```python
item = Item(
    title="New Item",
    description="Description",
    owner_id=user_id
)
session.add(item)
session.commit()
session.refresh(item)
return item
```

### Update

```python
item = session.get(Item, item_id)
if item:
    item.title = "Updated Title"
    session.add(item)
    session.commit()
    session.refresh(item)
return item
```

### Delete

```python
item = session.get(Item, item_id)
if item:
    session.delete(item)
    session.commit()
```

### Bulk Operations

```python
# Bulk insert
items = [Item(title=f"Item {i}") for i in range(100)]
session.add_all(items)
session.commit()

# Bulk update
statement = (
    update(Item)
    .where(Item.is_active == False)
    .values(is_archived=True)
)
session.exec(statement)
session.commit()
```

## Error Handling

```python
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

try:
    session.add(item)
    session.commit()
except IntegrityError as e:
    session.rollback()
    if "unique constraint" in str(e).lower():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Item with this title already exists"
        )
    raise
```

## Testing with Database

```python
import pytest
from sqlmodel import Session, create_engine, SQLModel
from sqlmodel.pool import StaticPool

@pytest.fixture(name="session")
def session_fixture():
    """In-memory SQLite for tests."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
```

## See Also

- [DEVELOPMENT.md](DEVELOPMENT.md) - Development setup
- [../backend/CLAUDE.md](../backend/CLAUDE.md) - Backend patterns
- [TESTING.md](TESTING.md) - Database testing
