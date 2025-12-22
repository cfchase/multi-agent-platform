# End-to-End Tests

This directory contains Playwright-based end-to-end tests for the application.

## Prerequisites

Before running E2E tests, ensure the following services are running:

1. **PostgreSQL Database**
   ```bash
   make db-start
   make db-init
   make db-seed  # Optional: seed with test data
   ```

2. **Backend API Server**
   ```bash
   make dev-backend
   ```
   Backend should be running at http://localhost:8000

3. **Frontend is automatically started by Playwright** (configured in `playwright.config.ts`)

## Running Tests

### Run all tests (headless)
```bash
npm run test:e2e
# or
make test-e2e
```

### Run tests with UI (interactive mode)
```bash
npm run test:e2e:ui
# or
make test-e2e-ui
```

### Run tests in headed mode (visible browser)
```bash
npm run test:e2e:headed
# or
make test-e2e-headed
```

## Test Coverage

Current E2E tests cover:

- **Page Display**: Title, description, toolbar, search input
- **Item Listing**: Table display with proper columns
- **Create Item**: Modal form submission and validation
- **Search/Filter**: Filtering items by title, ID, or description
- **Drawer Navigation**: Opening drawer, navigating between items
- **Edit Item**: Updating item details from table actions
- **Delete Item**: Removing items with confirmation
- **Empty States**: "No items yet" and "No items found" states

## Writing New Tests

Tests are located in `e2e/*.spec.ts` files. Use the Playwright Test API:

```typescript
import { test, expect } from '@playwright/test';

test('my new test', async ({ page }) => {
  await page.goto('/items');
  // Your test code here
});
```

## Debugging Tests

1. Use Playwright UI mode for interactive debugging:
   ```bash
   npm run test:e2e:ui
   ```

2. Use headed mode to see the browser:
   ```bash
   npm run test:e2e:headed
   ```

3. Add `await page.pause()` in your test to pause execution
