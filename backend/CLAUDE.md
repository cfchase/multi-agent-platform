# Backend Development Guide (FastAPI + Python)

**IMPORTANT**: This file contains backend-specific guidance. Claude automatically pulls this when working in the `backend/` directory.

## Tech Stack

- **Framework**: FastAPI (async Python web framework)
- **Server**: Uvicorn (ASGI server)
- **Package Manager**: UV (fast, reliable Python dependency management)
- **Database**: PostgreSQL 15 with SQLModel ORM
- **Migrations**: Alembic
- **Testing**: pytest with async support
- **Python Version**: 3.11+

## File Organization

**Directory Structure:**
```
backend/
├── app/
│   ├── main.py             # FastAPI application entry point
│   ├── api/
│   │   ├── router.py       # Main API router
│   │   ├── deps.py         # Dependency injection
│   │   └── routes/v1/      # Versioned routes
│   │       └── <feature>/  # Feature-specific routes
│   ├── models/             # SQLModel database models (package)
│   │   ├── __init__.py     # Model exports
│   │   ├── base.py         # Shared base models
│   │   ├── user.py         # User model
│   │   └── item.py         # Item model
│   ├── core/
│   │   ├── config.py       # Settings and configuration
│   │   ├── db.py           # Database connection
│   │   ├── logging.py      # Logging configuration
│   │   ├── metadata.py     # SQLModel schema configuration
│   │   └── middleware.py   # Request logging middleware
│   ├── graphql_api/        # GraphQL schema and types
│   └── alembic/            # Database migrations
│       └── versions/       # Migration files
└── tests/                  # Test files
```

**Naming Conventions:**
- **Model classes**: Singular PascalCase (e.g., `User`, `Item`)
- **Route paths**: Plural lowercase (e.g., `/items/`, `/users/`)
- **Python files**: Snake case (e.g., `item_service.py`)
- **Test files**: Mirror app structure with `test_` prefix

**When to Create New Files:**
- **New database table** → Model file in `models/` + Update `models/__init__.py` + Migration + API route
- **New API endpoint** → Route file in `api/routes/v1/<feature>/`
- **Complex business logic** → Service file in `services/`

## Development Commands

```bash
# Backend-only development
uv run uvicorn app.main:app --reload  # Start FastAPI server (port 8000)

# Dependency management
uv add <package>           # Add runtime dependency
uv add --dev <package>     # Add development dependency
uv sync                    # Sync dependencies from pyproject.toml

# Database migrations
uv run alembic revision --autogenerate -m "Description"  # Create migration
uv run alembic upgrade head                               # Apply migrations
uv run alembic downgrade -1                               # Rollback one migration
uv run alembic history                                     # View migration history
uv run alembic current                                     # Show current revision

# Testing
pytest                     # Run all tests
pytest tests/api/          # Run specific test directory
pytest -v                  # Verbose output
pytest --cov               # Generate coverage report
```

**IMPORTANT**: Always review auto-generated Alembic migrations before applying them. They can drop data!

## Database Patterns (SQLModel + Alembic)

### Model Definition

```python
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime
import uuid

class Item(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=1000)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Foreign key
    owner_id: uuid.UUID = Field(foreign_key="user.id")

    # Relationship
    owner: Optional["User"] = Relationship(back_populates="items")
```

### Cascade Delete Patterns (CRITICAL)

**NEVER use `cascade="all, delete"` on many-to-many relationships!**

This will delete related entities, not just join table entries.

**Correct Patterns:**

```python
# One-to-Many (CASCADE to owned children)
class User(SQLModel, table=True):
    items: List["Item"] = Relationship(
        back_populates="owner",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
# Deleting User DELETES all their items

# Many-to-Many (NO cascade to entities)
class Item(SQLModel, table=True):
    tags: List["Tag"] = Relationship(
        back_populates="items",
        link_model=ItemTag,
        # NO cascade here!
    )
# Deleting Item removes ItemTag entries, but NOT Tag entities
```

**Cascade Rules:**
- **Many-to-Many**: NO cascade to entities, only join table cleanup
- **One-to-Many**: CASCADE to owned children (`cascade="all, delete-orphan"`)
- **Join Tables**: Use `ondelete="CASCADE"` on foreign keys

### Alembic Migrations

**Workflow:**
1. Modify SQLModel models in `app/models.py`
2. Create migration:
   ```bash
   uv run alembic revision --autogenerate -m "Add user table"
   ```
3. **CRITICAL**: Review migration file for:
   - `DROP TABLE` or `DROP COLUMN` (data loss!)
   - Correct foreign key constraints
   - Expected cascade behavior
4. Apply migration:
   ```bash
   uv run alembic upgrade head
   ```

## API Development (FastAPI)

### Route Structure

```python
# app/api/routes/v1/items/items.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.core.db import get_session
from app.models import Item

router = APIRouter()

@router.get("/")
async def list_items(
    skip: int = 0,
    limit: int = 100,
    session: Session = Depends(get_session),
):
    """List items with pagination."""
    statement = select(Item).offset(skip).limit(limit)
    items = session.exec(statement).all()
    return {"data": items, "count": len(items)}

@router.get("/{id}")
async def get_item(
    id: uuid.UUID,
    session: Session = Depends(get_session),
):
    """Get single item by ID."""
    item = session.get(Item, id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item {id} not found"
        )
    return item
```

### HTTP Exception Patterns

```python
from fastapi import HTTPException, status

# 400 Bad Request - Invalid input
raise HTTPException(
    status_code=status.HTTP_400_BAD_REQUEST,
    detail="Invalid item data"
)

# 404 Not Found - Resource doesn't exist
raise HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail=f"Item {id} not found"
)

# 409 Conflict - Duplicate entry
raise HTTPException(
    status_code=status.HTTP_409_CONFLICT,
    detail=f"Item with title '{title}' already exists"
)

# 422 Unprocessable Entity - Pydantic validation (automatic)
```

### Validation with Pydantic

```python
from pydantic import BaseModel, Field

class ItemCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)

class ItemUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None

# FastAPI automatically returns 422 with validation errors
```

### Database Error Handling

```python
from sqlalchemy.exc import IntegrityError

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_item(
    item_in: ItemCreate,
    session: Session = Depends(get_session),
):
    item = Item.model_validate(item_in)

    try:
        session.add(item)
        session.commit()
        session.refresh(item)
        return item
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Item with this title already exists"
        )
```

## Testing Patterns

### Test Structure

```python
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

def test_get_item_not_found(client: TestClient):
    """Test 404 error when item doesn't exist."""
    response = client.get("/api/v1/items/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

def test_create_item_success(client: TestClient):
    """Test successful item creation."""
    response = client.post("/api/v1/items/", json={
        "title": "Test Item",
        "description": "A test item"
    })

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Item"
    assert "id" in data
```

### Test Fixtures

```python
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine, SQLModel
from sqlmodel.pool import StaticPool

from app.main import app
from app.core.db import get_session

@pytest.fixture(name="session")
def session_fixture():
    """Create a new database session for a test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session

@pytest.fixture(name="client")
def client_fixture(session: Session):
    """Create test client with database session."""
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
```

### TDD Bug Fix Workflow

**CRITICAL**: When fixing bugs, ALWAYS use Test-Driven Development:

1. **Write a failing test** that reproduces the bug
2. **Implement the fix** - minimum code to pass the test
3. **Verify** - run all tests to confirm fix and no regressions

```python
def test_delete_item_with_tags_preserves_tags(client, session):
    """
    Bug: Deleting an item was also deleting all associated tags.
    Expected: Tags should remain after item deletion.
    """
    # Setup: Create item with tags
    tag = Tag(name="test-tag")
    item = Item(title="Test", tags=[tag])
    session.add_all([tag, item])
    session.commit()

    tag_id = tag.id

    # Act: Delete the item
    response = client.delete(f"/api/v1/items/{item.id}")
    assert response.status_code == 204

    # Assert: Tag still exists
    remaining_tag = session.get(Tag, tag_id)
    assert remaining_tag is not None  # This was failing before the fix
```

## Authentication (OAuth2 Proxy)

The backend uses OAuth2 Proxy for authentication. See [../docs/AUTHENTICATION.md](../docs/AUTHENTICATION.md) for full details.

### How It Works

1. OAuth2 Proxy sits in front of the backend
2. Authenticated requests include headers:
   - `X-Forwarded-Preferred-Username`: Username
   - `X-Forwarded-Email`: User's email
3. Backend reads headers and auto-creates users

### Using Authentication in Routes

```python
from app.api.deps import CurrentUser, CurrentAdminUser

# Require any authenticated user
@router.get("/my-items")
async def get_my_items(current_user: CurrentUser, session: SessionDep):
    items = session.exec(
        select(Item).where(Item.owner_id == current_user.id)
    ).all()
    return items

# Require admin user
@router.delete("/users/{id}")
async def delete_user(id: int, admin: CurrentAdminUser, session: SessionDep):
    # Only admins can delete users
    ...
```

### Local Development Mode

When `ENVIRONMENT=local` in `.env`:
- No OAuth headers required
- Default "dev-user" is used
- Allows testing without OAuth2 Proxy

```python
# In deps.py
if settings.ENVIRONMENT == "local" and not username:
    username = "dev-user"
    email = "dev-user@example.com"
```

## Import Organization

```python
# 1. Standard library
import logging
from typing import Optional, List
from datetime import datetime

# 2. Third-party libraries
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from pydantic import BaseModel

# 3. Internal modules
from app.core.db import get_session
from app.core.config import get_settings
from app.models import Item, User
```

## Common Pitfalls (Backend-Specific)

### Database/SQLModel
- ❌ Modifying models without creating migration → Always run `alembic revision --autogenerate`
- ❌ Not reviewing migrations → Check SQL before applying
- ❌ Using `cascade="all, delete"` on many-to-many → Deletes entities!
- ❌ Not handling IntegrityError → Returns 500 instead of 409

### API Development
- ❌ Missing CORS configuration → Add origins to config
- ❌ Not using Pydantic validation → Always define schemas
- ❌ Hardcoding values → Use environment variables
- ❌ Wrong HTTP status codes → Know 400 vs 404 vs 409

### Testing
- ❌ Not using test database → Use in-memory SQLite
- ❌ Not cleaning up test data → Use fixtures
- ❌ Testing only happy path → Always test errors

### Performance
- ❌ N+1 query problem → Use `joinedload()` or `selectinload()`
- ❌ Missing indexes → Add to frequently queried columns
- ❌ Not using async → FastAPI supports async for I/O

## GraphQL API (Strawberry)

The backend includes a GraphQL API at `/api/graphql` for complex queries with relationships.

### Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    GraphQL Layer                          │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │    Schema    │  │   Loaders    │  │   Security    │  │
│  │  (schema.py) │  │ (loaders.py) │  │  Extensions   │  │
│  │              │  │              │  │               │  │
│  │  Query type  │  │  DataLoader  │  │  Depth Limit  │  │
│  │  resolvers   │  │  for N+1     │  │  Token Limit  │  │
│  └──────────────┘  └──────────────┘  └───────────────┘  │
└──────────────────────────────────────────────────────────┘
```

### When to Use GraphQL vs REST

| Use Case | API | Reason |
|----------|-----|--------|
| List items with owner | GraphQL | Avoids N+1, returns related data |
| Create/Update/Delete | REST | Simple mutations, clear semantics |
| Get single item | Either | Both work well |
| Admin operations | REST | Clearer audit trail |

### Adding a New GraphQL Type

1. **Create type in `graphql_api/types/`:**
   ```python
   # app/graphql_api/types/project.py
   import strawberry
   from app.models import Project

   @strawberry.type
   class ProjectType:
       id: int
       name: str
       description: str | None

       @classmethod
       def from_orm(cls, project: Project) -> "ProjectType":
           return cls(
               id=project.id,
               name=project.name,
               description=project.description,
           )
   ```

2. **Add resolver in `graphql_api/schema.py`:**
   ```python
   @strawberry.field
   def projects(self, info: Info, skip: int = 0, limit: int = 100) -> list[ProjectType]:
       session: Session = info.context["session"]
       statement = select(Project).offset(skip).limit(limit)
       projects = session.exec(statement).all()
       return [ProjectType.from_orm(p) for p in projects]
   ```

3. **Export type in `graphql_api/types/__init__.py`**

### DataLoaders for N+1 Prevention

```python
# app/graphql_api/loaders.py
from strawberry.dataloader import DataLoader

async def load_users_by_ids(keys: list[int]) -> list[User]:
    session = get_current_session()
    users = session.exec(select(User).where(User.id.in_(keys))).all()
    user_map = {u.id: u for u in users}
    return [user_map.get(key) for key in keys]

user_loader = DataLoader(load_fn=load_users_by_ids)
```

### Security Extensions

The schema includes built-in security:

```python
schema = strawberry.Schema(
    query=Query,
    extensions=[
        QueryDepthLimiter(max_depth=10),    # Prevents deeply nested attacks
        MaxTokensLimiter(max_token_count=2000),  # Prevents DoS
    ],
)
```

## Configuration Management

```python
# app/core/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "app"
    POSTGRES_PASSWORD: str = "changethis"
    POSTGRES_DB: str = "app"
    POSTGRES_PORT: int = 5432

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
```

**IMPORTANT**: Never commit `.env` files with secrets! Use `.env.example` template.

## Additional Resources

- [../docs/DATABASE.md](../docs/DATABASE.md) - Schema, migrations, relationships
- [../docs/TESTING.md](../docs/TESTING.md) - Testing patterns, fixtures
- **Root CLAUDE.md** for project-wide guidelines
