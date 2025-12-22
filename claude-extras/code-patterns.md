# Code Patterns Reference

Quick reference for common code patterns used in this codebase.

## Backend Patterns (FastAPI + SQLModel)

### Create a New Model

```python
# backend/app/models/new_model.py
from typing import TYPE_CHECKING, Optional
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.user import User

class NewModelBase(SQLModel):
    """Shared properties for NewModel."""
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)

class NewModelCreate(NewModelBase):
    """Properties to receive on creation."""
    pass

class NewModelUpdate(NewModelBase):
    """Properties to receive on update."""
    name: str | None = Field(default=None, min_length=1, max_length=255)

class NewModel(NewModelBase, table=True):
    """Database model."""
    id: int | None = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="user.id", nullable=False, ondelete="CASCADE")
    owner: Optional["User"] = Relationship(back_populates="new_models")

class NewModelPublic(NewModelBase):
    """Properties to return via API."""
    id: int
    owner_id: int
```

**Don't forget**:
1. Add to `backend/app/models/__init__.py`
2. Create migration: `uv run alembic revision --autogenerate -m "Add new_model"`
3. Review migration file before applying

### Create a New API Route

```python
# backend/app/api/routes/v1/new_model.py
from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from app.api.deps import SessionDep, CurrentUser
from app.models import NewModel, NewModelCreate, NewModelPublic

router = APIRouter()

@router.get("/", response_model=list[NewModelPublic])
async def list_items(session: SessionDep, skip: int = 0, limit: int = 100):
    """List all items with pagination."""
    items = session.exec(select(NewModel).offset(skip).limit(limit)).all()
    return items

@router.post("/", response_model=NewModelPublic, status_code=status.HTTP_201_CREATED)
async def create_item(session: SessionDep, current_user: CurrentUser, item_in: NewModelCreate):
    """Create a new item."""
    item = NewModel.model_validate(item_in, update={"owner_id": current_user.id})
    session.add(item)
    session.commit()
    session.refresh(item)
    return item
```

### Handle Database Errors

```python
from sqlalchemy.exc import IntegrityError

try:
    session.add(item)
    session.commit()
except IntegrityError:
    session.rollback()
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Item with this name already exists"
    )
```

## Frontend Patterns (React + PatternFly)

### Create a New Page

```tsx
// frontend/src/app/NewPage/NewPage.tsx
import React, { useState, useEffect } from 'react';
import {
  PageSection,
  Title,
  Card,
  CardBody,
  EmptyState,
  Spinner,
  Button,
} from '@patternfly/react-core';
import { ExclamationCircleIcon } from '@patternfly/react-icons';

interface NewPageProps {}

const NewPage: React.FC<NewPageProps> = () => {
  const [data, setData] = useState<Item[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const result = await itemService.getItems();
        setData(result);
      } catch (err) {
        setError('Failed to load data');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (loading) {
    return (
      <EmptyState>
        <Spinner size="xl" />
        <Title headingLevel="h2">Loading...</Title>
      </EmptyState>
    );
  }

  if (error) {
    return (
      <EmptyState>
        <ExclamationCircleIcon color="var(--pf-v6-global--danger-color--100)" />
        <Title headingLevel="h2">Error</Title>
        <p>{error}</p>
        <Button variant="primary" onClick={() => window.location.reload()}>
          Retry
        </Button>
      </EmptyState>
    );
  }

  return (
    <PageSection>
      <Title headingLevel="h1">New Page</Title>
      <Card>
        <CardBody>
          {/* Content here */}
        </CardBody>
      </Card>
    </PageSection>
  );
};

export default NewPage;
```

### Add Route

```tsx
// Add to frontend/src/app/routes.tsx
import NewPage from './NewPage/NewPage';

// In routes array:
{
  path: '/new-page',
  element: <NewPage />,
}
```

### GraphQL Query with React Query

```tsx
import { useQuery } from '@tanstack/react-query';
import { executeGraphQLQuery } from '../graphql/client';
import { ITEMS_QUERY, ItemsQueryResult } from '../graphql/queries';

const useItems = (skip = 0, limit = 10) => {
  return useQuery({
    queryKey: ['items', skip, limit],
    queryFn: () => executeGraphQLQuery<ItemsQueryResult>(ITEMS_QUERY, { skip, limit }),
  });
};
```

## GraphQL Patterns

### Add a New Query

```python
# backend/app/graphql_api/schema.py
@strawberry.field
def new_items(
    self,
    info: Info,
    skip: int = 0,
    limit: int = 100,
) -> list[NewItemType]:
    """Get new items with pagination."""
    session: Session = info.context["session"]
    statement = select(NewItem).offset(skip).limit(limit)
    items = session.exec(statement).all()
    return [NewItemType.from_orm(item) for item in items]
```

### Frontend GraphQL Query

```typescript
// frontend/src/app/graphql/queries.ts
export const NEW_ITEMS_QUERY = `
  query NewItems($skip: Int, $limit: Int) {
    newItems(skip: $skip, limit: $limit) {
      id
      name
      description
      owner {
        id
        username
      }
    }
  }
`;
```

## Testing Patterns

### Backend Test

```python
# backend/tests/test_new_feature.py
def test_create_new_item(client: TestClient, session: Session):
    """Test creating a new item."""
    response = client.post("/api/v1/items/", json={
        "title": "Test Item",
        "description": "Test description"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Item"
```

### Frontend Test

```tsx
// frontend/src/app/NewPage/NewPage.test.tsx
import { render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import NewPage from './NewPage';

vi.mock('../api/itemService');

test('displays items when loaded', async () => {
  vi.mocked(itemService.getItems).mockResolvedValue([
    { id: 1, title: 'Test Item' }
  ]);

  render(<NewPage />);

  await waitFor(() => {
    expect(screen.getByText('Test Item')).toBeInTheDocument();
  });
});
```
