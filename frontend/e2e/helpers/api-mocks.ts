/**
 * API Mock Helpers for E2E Tests
 *
 * This module provides utilities for mocking API responses in Playwright
 * E2E tests. Use these helpers to create deterministic tests that don't
 * depend on external services.
 *
 * Usage:
 * ```typescript
 * import { test, expect } from '@playwright/test';
 * import { mockApiResponse, mockGraphQLResponse } from './helpers/api-mocks';
 *
 * test('displays items from API', async ({ page }) => {
 *   await mockApiResponse(page, '/api/v1/items/', {
 *     data: [{ id: 1, title: 'Test Item' }],
 *     count: 1
 *   });
 *
 *   await page.goto('/items');
 *   await expect(page.getByText('Test Item')).toBeVisible();
 * });
 * ```
 */

import { Page, Route } from '@playwright/test';

/**
 * Mock a REST API response
 *
 * @param page - Playwright page
 * @param urlPattern - URL pattern to match (string or regex)
 * @param response - Response data to return
 * @param options - Additional options (status, headers, delay)
 */
export async function mockApiResponse(
  page: Page,
  urlPattern: string | RegExp,
  response: unknown,
  options: {
    status?: number;
    headers?: Record<string, string>;
    delay?: number;
  } = {}
): Promise<void> {
  const { status = 200, headers = {}, delay = 0 } = options;

  await page.route(urlPattern, async (route: Route) => {
    if (delay > 0) {
      await new Promise((resolve) => setTimeout(resolve, delay));
    }

    await route.fulfill({
      status,
      contentType: 'application/json',
      headers: {
        'Content-Type': 'application/json',
        ...headers,
      },
      body: JSON.stringify(response),
    });
  });
}

/**
 * Mock a GraphQL response
 *
 * @param page - Playwright page
 * @param operationName - GraphQL operation name to match
 * @param response - Response data to return
 * @param options - Additional options (errors, delay)
 */
export async function mockGraphQLResponse(
  page: Page,
  operationName: string,
  response: unknown,
  options: {
    errors?: Array<{ message: string }>;
    delay?: number;
  } = {}
): Promise<void> {
  const { errors, delay = 0 } = options;

  await page.route('**/graphql', async (route: Route) => {
    const request = route.request();
    const postData = request.postDataJSON();

    // Check if this is the operation we want to mock
    if (postData?.operationName === operationName) {
      if (delay > 0) {
        await new Promise((resolve) => setTimeout(resolve, delay));
      }

      const body: Record<string, unknown> = { data: response };
      if (errors) {
        body.errors = errors;
      }

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(body),
      });
    } else {
      // Pass through other GraphQL requests
      await route.continue();
    }
  });
}

/**
 * Mock an API error response
 */
export async function mockApiError(
  page: Page,
  urlPattern: string | RegExp,
  statusCode: number,
  errorMessage: string
): Promise<void> {
  await mockApiResponse(
    page,
    urlPattern,
    { detail: errorMessage },
    { status: statusCode }
  );
}

/**
 * Mock a 401 Unauthorized response (authentication required)
 */
export async function mockUnauthorized(
  page: Page,
  urlPattern: string | RegExp
): Promise<void> {
  await mockApiError(page, urlPattern, 401, 'Authentication required');
}

/**
 * Mock a 403 Forbidden response (insufficient permissions)
 */
export async function mockForbidden(
  page: Page,
  urlPattern: string | RegExp
): Promise<void> {
  await mockApiError(page, urlPattern, 403, 'Permission denied');
}

/**
 * Mock a 404 Not Found response
 */
export async function mockNotFound(
  page: Page,
  urlPattern: string | RegExp
): Promise<void> {
  await mockApiError(page, urlPattern, 404, 'Resource not found');
}

/**
 * Mock a 500 Server Error response
 */
export async function mockServerError(
  page: Page,
  urlPattern: string | RegExp
): Promise<void> {
  await mockApiError(page, urlPattern, 500, 'Internal server error');
}

/**
 * Mock a network timeout
 */
export async function mockNetworkTimeout(
  page: Page,
  urlPattern: string | RegExp
): Promise<void> {
  await page.route(urlPattern, (route) => route.abort('timedout'));
}

/**
 * Mock a network failure
 */
export async function mockNetworkFailure(
  page: Page,
  urlPattern: string | RegExp
): Promise<void> {
  await page.route(urlPattern, (route) => route.abort('connectionfailed'));
}

/**
 * Clear all route mocks
 */
export async function clearMocks(page: Page): Promise<void> {
  await page.unrouteAll();
}

/**
 * Sample data factories for consistent test data
 */
export const testDataFactories = {
  /**
   * Create a test user
   */
  createUser(overrides = {}) {
    return {
      id: 1,
      username: 'test-user',
      email: 'test@example.com',
      full_name: 'Test User',
      admin: false,
      active: true,
      created_at: new Date().toISOString(),
      last_login: new Date().toISOString(),
      ...overrides,
    };
  },

  /**
   * Create a test item
   */
  createItem(overrides = {}) {
    return {
      id: 1,
      title: 'Test Item',
      description: 'A test item description',
      owner_id: 1,
      ...overrides,
    };
  },

  /**
   * Create a paginated items response
   */
  createItemsResponse(items: unknown[] = [], count?: number) {
    return {
      data: items,
      count: count ?? items.length,
    };
  },

  /**
   * Create a paginated users response
   */
  createUsersResponse(users: unknown[] = [], count?: number) {
    return {
      data: users,
      count: count ?? users.length,
    };
  },
};
