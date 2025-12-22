# Frontend Development Guide (React + Vite + PatternFly)

**IMPORTANT**: This file contains frontend-specific guidance. Claude automatically pulls this when working in the `frontend/` directory.

## Tech Stack

- **Framework**: React 18 with TypeScript
- **Build Tool**: Vite (fast dev server, hot module replacement)
- **UI Components**: PatternFly v6
- **HTTP Client**: Axios
- **Testing**: Vitest + React Testing Library
- **State Management**: React Context + local component state

## File Organization

**Directory Structure:**
```
frontend/src/
├── app/
│   ├── <PageName>/           # One directory per page (PascalCase)
│   │   ├── <ComponentName>.tsx
│   │   └── <ComponentName>.test.tsx
│   └── routes.tsx            # Route definitions
├── components/               # Reusable cross-page components
├── api/                     # Axios client and TypeScript types
├── contexts/                # React Context providers
└── services/                # API service layers
```

**Naming Conventions:**
- **Components**: PascalCase (e.g., `ItemBrowser.tsx`, `UserCard.tsx`)
- **Utilities/services**: camelCase (e.g., `apiClient.ts`, `itemService.ts`)
- **Test files**: Match component name with `.test.tsx` suffix
- **Page directories**: PascalCase matching route name

**When to Create New Files:**
- **New UI page** → Directory in `src/app/` + add route in `routes.tsx`
- **Reusable component** → Move to `src/components/` if used in 2+ pages
- **New API endpoint integration** → Add to existing service file or create new one
- **Complex UI logic** → Extract to custom hook (`useItemData.tsx`)

## Development Commands

```bash
# Frontend-only development
npm run dev              # Start Vite dev server (port 8080)
npm run build            # Build for production
npm run preview          # Preview production build

# Testing
npm test                 # Run Vitest tests
npm run test:coverage    # Generate coverage report
npm run typecheck        # Run TypeScript type checking

# Linting
npm run lint             # ESLint check
npm run lint:fix         # Auto-fix ESLint issues
```

**IMPORTANT**: Always run `npm run typecheck` before committing to catch TypeScript errors.

## PatternFly v6 Best Practices

### Core Principles (CRITICAL)

**NEVER use inline `style` attributes** - This is the #1 anti-pattern. Always use PatternFly components with their built-in props and variants.

**Use component variants** instead of custom styles:
- Button: `variant="primary"`, `variant="secondary"`, `variant="danger"`, etc.
- Alert: `variant="success"`, `variant="danger"`, `variant="warning"`, `variant="info"`

**Prefer PatternFly layout components** over manual CSS:
- **Stack/StackItem** for vertical layouts
- **Flex/FlexItem** for horizontal layouts
- **Grid/GridItem** for responsive grids

### Common Patterns

**Vertical Spacing with Stack:**
```tsx
// GOOD
<Stack hasGutter>
  <StackItem>
    <Title headingLevel="h2">Section Title</Title>
  </StackItem>
  <StackItem>
    <Content>Section content here</Content>
  </StackItem>
</Stack>

// BAD - Don't use inline styles
<div style={{ marginTop: '16px' }}>
  <Title>Section Title</Title>
</div>
```

**Horizontal Layout with Flex:**
```tsx
// GOOD
<Flex justifyContent={{ default: 'justifyContentSpaceBetween' }}>
  <FlexItem>
    <Title>Left content</Title>
  </FlexItem>
  <FlexItem>
    <Button variant="primary">Action</Button>
  </FlexItem>
</Flex>
```

**Loading/Error/Empty States:**
```tsx
// GOOD - Use EmptyState for all non-data states
{loading && (
  <EmptyState>
    <Spinner size="xl" />
    <Title headingLevel="h2" size="lg">
      Loading...
    </Title>
  </EmptyState>
)}

{error && (
  <EmptyState>
    <EmptyStateIcon icon={ExclamationCircleIcon} color="var(--pf-v6-global--danger-color--100)" />
    <Title headingLevel="h2" size="lg">
      Error loading data
    </Title>
    <p>{error}</p>
    <Button variant="primary" onClick={handleRetry}>
      Try Again
    </Button>
  </EmptyState>
)}
```

**Icons with Status:**
```tsx
// GOOD - Use Icon component with status prop
<Icon status="success">
  <CheckCircleIcon />
</Icon>
<Icon status="danger">
  <ExclamationCircleIcon />
</Icon>

// BAD - Don't use hardcoded colors
<CheckCircleIcon color="green" />
```

**Responsive Design:**
```tsx
// GOOD - Use breakpoint modifiers
<Grid hasGutter>
  <GridItem span={12} md={6} lg={4}>
    <Card>...</Card>
  </GridItem>
</Grid>

<Flex
  direction={{ default: 'column', md: 'row' }}
  gap={{ default: 'gapMd' }}
>
  <FlexItem>...</FlexItem>
</Flex>
```

## State Management

**Decision Tree:**
- **Single component needs it?** → `useState` in that component
- **2-3 components need it?** → Lift state to common parent
- **3+ components across different tree levels?** → Consider Context
- **Don't overuse Context** - causes unnecessary re-renders

**Local Component State:**
```tsx
const [data, setData] = useState<Item[]>([]);
const [loading, setLoading] = useState(false);
const [error, setError] = useState<string | null>(null);
```

**Server State (API Data):**
```tsx
// Using useState + useEffect pattern
useEffect(() => {
  const fetchData = async () => {
    setLoading(true);
    try {
      const result = await itemService.getItems();
      setData(result);
    } catch (err) {
      setError('Failed to load data');
    } finally {
      setLoading(false);
    }
  };
  fetchData();
}, []);

// CONSIDER: React Query for advanced caching
```

## Error Handling

**API Calls with Error Handling:**
```tsx
import axios from 'axios';

const loadItem = async (id: string) => {
  setLoading(true);
  setError(null);

  try {
    const data = await itemService.getItem(id);
    setItem(data);
  } catch (error) {
    console.error('Failed to load item:', error);

    if (axios.isAxiosError(error)) {
      if (error.response) {
        const status = error.response.status;
        const message = error.response.data?.detail || 'Unknown error';

        if (status === 404) {
          setError('Item not found');
        } else if (status === 403) {
          setError('You do not have permission to view this item');
        } else {
          setError(`Error: ${message}`);
        }
      } else if (error.request) {
        setError('Unable to connect to server. Please check your connection.');
      }
    } else {
      setError('An unexpected error occurred');
    }
  } finally {
    setLoading(false);
  }
};
```

**Best Practices:**
- Show user-friendly messages (not raw error objects)
- Log technical details to console for debugging
- Provide retry mechanisms where appropriate
- Clear previous errors when retrying

## Testing Patterns

### Component Testing

```tsx
import { render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import ItemList from './ItemList';

vi.mock('axios');

test('displays error message when API call fails', async () => {
  vi.mocked(axios.get).mockRejectedValue(new Error('Network error'));

  render(<ItemList />);

  await waitFor(() => {
    expect(screen.getByText(/unable to load/i)).toBeInTheDocument();
  });
});

test('handles 404 error gracefully', async () => {
  vi.mocked(axios.get).mockRejectedValue({
    response: { status: 404, data: { detail: 'Not found' } }
  });

  render(<ItemDetail id="123" />);

  await waitFor(() => {
    expect(screen.getByText(/not found/i)).toBeInTheDocument();
  });
});
```

**When to Write Tests:**
- **Always**: Components with user interactions or complex logic
- **Always**: Critical user flows (forms, data operations)
- **Recommended**: API integration with mock data
- **Optional**: Simple presentational components with no logic

**Coverage Goals:**
- **>70%** line coverage for components with logic
- Focus on: User interactions, data fetching, loading/error states

**Test Patterns:**
- Use `render()` from React Testing Library
- Use `vi.mock()` for API mocks
- Test user behavior, not implementation details
- Wait for elements with `waitFor()` or `findBy*` queries

### TDD Bug Fix Workflow

**CRITICAL**: When fixing bugs, ALWAYS use TDD:

1. **Write a failing test first** - reproduces the bug
2. **Implement the fix** - minimum code to pass
3. **Verify** - run all tests

```tsx
it('should display correct status for completed items', () => {
  /**
   * Bug: Completed items show "In Progress" instead of "Complete"
   * Root cause: Missing case for COMPLETED status
   */
  render(<ItemStatus status="COMPLETED" />);
  expect(screen.getByText('Complete')).toBeInTheDocument();
});
```

## Import Organization

```tsx
// 1. External libraries (React, third-party)
import React, { useState, useEffect } from 'react';
import { Button, Card, Stack } from '@patternfly/react-core';
import axios from 'axios';

// 2. Internal utilities/services
import { itemService } from '@/services/itemService';
import { formatDate } from '@/utils/dateUtils';

// 3. Types/interfaces
import type { Item } from '@/api/types';

// 4. Components
import ItemCard from '@/components/ItemCard';

// 5. Styles (if any)
import './ItemList.css';
```

**Group with blank lines** between categories for readability.

## Common Pitfalls (Frontend-Specific)

### UI/PatternFly
- ❌ Using inline styles (`style={{...}}`) → Use PatternFly components
- ❌ Hardcoding colors → Use CSS variables (`var(--pf-v6-global--...)`)
- ❌ Not handling loading/error states → Show EmptyState component
- ❌ Missing responsive breakpoints → Use Grid/Flex with breakpoint modifiers

### State Management
- ❌ Fetching data in every component → Lift state to common parent
- ❌ Overusing Context → Causes unnecessary re-renders
- ❌ Not clearing error states on retry → Reset error to null

### TypeScript
- ❌ Using `any` type → Be specific with types
- ❌ Not defining API response types → Create interfaces in `api/types.ts`
- ❌ Ignoring TypeScript errors → Fix them, don't use `@ts-ignore`

### Testing
- ❌ Testing implementation details → Test user behavior
- ❌ Not waiting for async updates → Use `waitFor()` or `findBy*`
- ❌ Missing error case tests → Always test both success and error

### Performance
- ❌ Creating functions inside render → Move outside or use useCallback
- ❌ Missing key props in lists → Always provide stable unique keys
- ❌ Re-rendering entire lists → Use React.memo for expensive components

## API Integration

**Axios Client Configuration:**
```tsx
// src/api/apiClient.ts
import axios from 'axios';

const apiClient = axios.create({
  baseURL: '/api',
});

// Response interceptor for global error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error);

    if (error.response?.status === 401) {
      window.location.href = '/login';
    }

    return Promise.reject(error);
  }
);

export default apiClient;
```

**Service Layer Pattern:**
```tsx
// src/services/itemService.ts
import apiClient from '@/api/apiClient';
import type { Item } from '@/api/types';

export const itemService = {
  async getItems(params?: { skip?: number; limit?: number }) {
    const { data } = await apiClient.get<{ data: Item[]; count: number }>(
      '/v1/items/',
      { params }
    );
    return data;
  },

  async getItem(id: string) {
    const { data } = await apiClient.get<Item>(`/v1/items/${id}`);
    return data;
  },
};
```

## Development Workflow

**Pre-Commit Checklist:**
1. Run `npm run typecheck` - Fix TypeScript errors
2. Run `npm test` - Ensure tests pass
3. Run `npm run lint` - Fix linting issues
4. Test in browser - Verify UI works
5. Check console for errors/warnings

**Hot Module Replacement (HMR):**
- Vite provides instant HMR for most changes
- React components reload without losing state
- CSS changes apply immediately
- Full page reload if HMR fails

**Proxy Configuration:**
- Vite dev server proxies `/api/` to backend (localhost:8000)
- Configured in `vite.config.ts`
- Production uses Nginx reverse proxy

## Additional Resources

- [../docs/TESTING.md](../docs/TESTING.md) - Testing frameworks, patterns
- [../docs/DEVELOPMENT.md](../docs/DEVELOPMENT.md) - Development workflows
- **Root CLAUDE.md** for project-wide guidelines
