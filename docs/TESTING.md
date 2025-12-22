# Testing Guide

## Quick Reference

```bash
# Unit Tests
make test             # Run all tests
make test-frontend    # Run frontend Vitest tests
make test-backend     # Run backend pytest tests
make lint             # Run linting

# Test Options
make test-backend-verbose    # Verbose output
make test-backend-coverage   # Coverage report
make test-backend-watch      # Watch mode

# E2E Tests (Playwright)
# Prerequisites: database + backend running
make db-start && make db-init && make db-seed  # Setup database
make dev-backend                                 # Start backend
make test-e2e                                    # Run E2E tests
make test-e2e-ui                                 # Interactive UI
make test-e2e-headed                             # Visible browser
```

## Frontend Testing (Vitest)

### Overview
- **Test Runner**: Vitest (fast, Vite-native)
- **Test Environment**: jsdom
- **Test Location**: `frontend/src/**/*.test.tsx`
- **Testing Library**: React Testing Library with jest-dom matchers

### Configuration
Tests are configured in `frontend/vitest.config.ts`.

### Writing Tests

```tsx
import { render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import userEvent from '@testing-library/user-event';
import ItemList from './ItemList';

// Mock API calls
vi.mock('@/services/itemService', () => ({
  itemService: {
    getItems: vi.fn(),
  },
}));

describe('ItemList', () => {
  it('renders loading state initially', () => {
    render(<ItemList />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it('displays items when loaded', async () => {
    const mockItems = [
      { id: '1', title: 'Item 1' },
      { id: '2', title: 'Item 2' },
    ];
    vi.mocked(itemService.getItems).mockResolvedValue({ data: mockItems });

    render(<ItemList />);

    await waitFor(() => {
      expect(screen.getByText('Item 1')).toBeInTheDocument();
      expect(screen.getByText('Item 2')).toBeInTheDocument();
    });
  });

  it('displays error when API fails', async () => {
    vi.mocked(itemService.getItems).mockRejectedValue(new Error('Network error'));

    render(<ItemList />);

    await waitFor(() => {
      expect(screen.getByText(/error/i)).toBeInTheDocument();
    });
  });

  it('handles user interaction', async () => {
    const user = userEvent.setup();
    render(<ItemList />);

    await user.click(screen.getByRole('button', { name: /create/i }));

    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });
});
```

### Common Patterns

**Testing async operations:**
```tsx
await waitFor(() => {
  expect(screen.getByText('Expected text')).toBeInTheDocument();
});

// Or use findBy* which has built-in waiting
const element = await screen.findByText('Expected text');
```

**Testing user interactions:**
```tsx
const user = userEvent.setup();
await user.click(button);
await user.type(input, 'text');
await user.selectOptions(select, 'option');
```

**Mocking modules:**
```tsx
vi.mock('@/services/itemService');
vi.mocked(itemService.getItems).mockResolvedValue(data);
```

## Backend Testing (pytest)

### Overview
- **Test Runner**: pytest with async support
- **Test Location**: `backend/tests/`
- **Test Client**: FastAPI TestClient
- **Database**: In-memory SQLite for tests

### Writing Tests

```python
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

def test_list_items_empty(client: TestClient):
    """Test listing items when none exist."""
    response = client.get("/api/v1/items/")

    assert response.status_code == 200
    data = response.json()
    assert data["data"] == []
    assert data["count"] == 0

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

def test_get_item_not_found(client: TestClient):
    """Test 404 when item doesn't exist."""
    response = client.get("/api/v1/items/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

def test_create_item_validation_error(client: TestClient):
    """Test validation error on invalid input."""
    response = client.post("/api/v1/items/", json={
        "title": "",  # Empty title should fail
    })

    assert response.status_code == 422
```

### Test Fixtures

```python
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine, SQLModel
from sqlmodel.pool import StaticPool

from app.main import app
from app.core.db import get_session
from app.models import User, Item

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

@pytest.fixture
def sample_user(session: Session) -> User:
    """Create a sample user for testing."""
    user = User(email="test@example.com", full_name="Test User")
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

@pytest.fixture
def sample_items(session: Session, sample_user: User) -> list[Item]:
    """Create sample items for testing."""
    items = [
        Item(title="Item 1", owner_id=sample_user.id),
        Item(title="Item 2", owner_id=sample_user.id),
    ]
    for item in items:
        session.add(item)
    session.commit()
    return items
```

## E2E Testing (Playwright)

### Setup

E2E tests require running services:
```bash
# Terminal 1: Database
make db-start && make db-init && make db-seed

# Terminal 2: Backend
make dev-backend

# Terminal 3: Run tests (frontend started automatically)
make test-e2e
```

### Writing Tests

```typescript
import { test, expect } from '@playwright/test';

test.describe('Items', () => {
  test('can view item list', async ({ page }) => {
    await page.goto('/items');

    await expect(page.getByRole('heading', { name: 'Items' })).toBeVisible();
    await expect(page.getByRole('table')).toBeVisible();
  });

  test('can create new item', async ({ page }) => {
    await page.goto('/items');

    await page.getByRole('button', { name: 'Create Item' }).click();
    await page.getByLabel('Title').fill('E2E Test Item');
    await page.getByRole('button', { name: 'Save' }).click();

    await expect(page.getByText('E2E Test Item')).toBeVisible();
  });

  test('can delete item', async ({ page }) => {
    await page.goto('/items');

    // Click delete on first item
    await page.getByRole('row').first().getByRole('button', { name: 'Delete' }).click();
    await page.getByRole('button', { name: 'Confirm' }).click();

    await expect(page.getByText('Item deleted')).toBeVisible();
  });
});
```

## TDD Bug Fix Workflow

**CRITICAL**: When fixing bugs, ALWAYS use Test-Driven Development:

### Workflow
1. **Write a failing test** that reproduces the bug
2. **Implement the fix** - minimum code to pass
3. **Verify** - run all tests to confirm fix

### Example

```python
def test_delete_item_with_tags_preserves_tags(client, session):
    """
    Bug: Deleting an item also deleted all its tags.
    Expected: Tags should remain after item deletion.
    """
    # Setup
    tag = Tag(name="test-tag")
    item = Item(title="Test", tags=[tag])
    session.add_all([tag, item])
    session.commit()
    tag_id = tag.id

    # Act
    response = client.delete(f"/api/v1/items/{item.id}")
    assert response.status_code == 204

    # Assert - this was failing before the fix
    remaining_tag = session.get(Tag, tag_id)
    assert remaining_tag is not None
```

### Why TDD for Bug Fixes?
- Proves the bug exists before fixing
- Prevents regression (bug won't return)
- Documents the bug and expected behavior
- Builds confidence that fix works

## Coverage Goals

| Area | Target | Focus |
|------|--------|-------|
| Backend API | >80% | Routes, validation, error handling |
| Backend Models | >80% | Business logic, relationships |
| Frontend Components | >70% | User interactions, data fetching |
| E2E | Critical paths | Auth, CRUD operations |

## What to Test

### Always Test
- API endpoints (success, validation, errors)
- User interactions (clicks, form submissions)
- Error states and edge cases
- Loading states

### Don't Test
- Framework internals
- Simple presentational components
- Third-party library functionality

## See Also

- [DEVELOPMENT.md](DEVELOPMENT.md) - Development setup
- [INCREMENTAL-WORKFLOW.md](INCREMENTAL-WORKFLOW.md) - Testing in workflow
- [../backend/CLAUDE.md](../backend/CLAUDE.md) - Backend testing details
- [../frontend/CLAUDE.md](../frontend/CLAUDE.md) - Frontend testing details
