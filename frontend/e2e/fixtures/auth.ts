/**
 * Authentication fixtures for E2E tests
 *
 * This module provides fixtures to simulate OAuth2-proxy authentication
 * in E2E tests. In production, the OAuth2-proxy sets specific headers
 * that identify the user. These fixtures allow tests to run with
 * simulated authentication.
 *
 * Usage with Playwright:
 * ```typescript
 * import { test as base } from '@playwright/test';
 * import { authFixtures } from './fixtures/auth';
 *
 * const test = base.extend(authFixtures);
 *
 * test('authenticated user can view items', async ({ authenticatedPage }) => {
 *   await authenticatedPage.goto('/items');
 *   await expect(authenticatedPage.getByText('Items')).toBeVisible();
 * });
 * ```
 */

import { test as base, Page, BrowserContext } from '@playwright/test';

/**
 * Default test user configuration
 */
export const DEFAULT_TEST_USER = {
  username: 'test-user',
  email: 'test@example.com',
  fullName: 'Test User',
};

export const ADMIN_TEST_USER = {
  username: 'admin-user',
  email: 'admin@example.com',
  fullName: 'Admin User',
};

/**
 * OAuth2-proxy headers to simulate authentication
 */
export interface AuthHeaders {
  'X-Forwarded-Preferred-Username': string;
  'X-Forwarded-User': string;
  'X-Forwarded-Email': string;
}

/**
 * Create auth headers for a test user
 */
export function createAuthHeaders(user: {
  username: string;
  email: string;
}): AuthHeaders {
  return {
    'X-Forwarded-Preferred-Username': user.username,
    'X-Forwarded-User': user.username,
    'X-Forwarded-Email': user.email,
  };
}

/**
 * Extended fixtures for authenticated testing
 */
export interface AuthFixtures {
  /** Page with default user authentication headers */
  authenticatedPage: Page;
  /** Page with admin user authentication headers */
  adminPage: Page;
  /** Page without authentication (anonymous) */
  anonymousPage: Page;
}

/**
 * Create Playwright fixtures for authenticated testing
 */
export const authFixtures = base.extend<AuthFixtures>({
  /**
   * Authenticated page with default test user
   */
  authenticatedPage: async ({ browser }, use) => {
    const context = await browser.newContext({
      extraHTTPHeaders: createAuthHeaders(DEFAULT_TEST_USER),
    });
    const page = await context.newPage();
    await use(page);
    await context.close();
  },

  /**
   * Authenticated page with admin user
   */
  adminPage: async ({ browser }, use) => {
    const context = await browser.newContext({
      extraHTTPHeaders: createAuthHeaders(ADMIN_TEST_USER),
    });
    const page = await context.newPage();
    await use(page);
    await context.close();
  },

  /**
   * Page without authentication headers (for testing auth requirements)
   */
  anonymousPage: async ({ browser }, use) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    await use(page);
    await context.close();
  },
});

/**
 * Helper to add auth headers to an existing context
 */
export async function addAuthToContext(
  context: BrowserContext,
  user = DEFAULT_TEST_USER
): Promise<void> {
  await context.setExtraHTTPHeaders(createAuthHeaders(user));
}

/**
 * Helper to check if user is authenticated on page
 */
export async function isAuthenticated(page: Page): Promise<boolean> {
  try {
    // Check for user menu or profile element
    await page.waitForSelector('[data-testid="user-menu"]', { timeout: 5000 });
    return true;
  } catch {
    return false;
  }
}

/**
 * Re-export base test with auth fixtures applied
 */
export const test = authFixtures;
