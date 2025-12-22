/**
 * Test Utilities for PatternFly Components
 *
 * This module provides helper functions for testing PatternFly-based
 * components. Use these helpers to avoid repetitive DOM queries and
 * improve test readability.
 *
 * Example usage:
 * ```typescript
 * import { render, screen } from '@testing-library/react';
 * import userEvent from '@testing-library/user-event';
 * import { tableHelpers, paginationHelpers, modalHelpers } from './test-utils';
 *
 * it('should select all rows', async () => {
 *   const user = userEvent.setup();
 *   render(<MyTable />);
 *
 *   const checkbox = tableHelpers.getSelectAllCheckbox();
 *   await user.click(checkbox);
 *
 *   tableHelpers.expectAllRowCheckboxes(true);
 * });
 * ```
 */

import { screen, within } from '@testing-library/react';
import { UserEvent } from '@testing-library/user-event';

/**
 * Helpers for PatternFly Table components
 */
export const tableHelpers = {
  /**
   * Get all data from a specific column by its header text
   */
  getColumnData(columnLabel: string): string[] {
    const table = screen.getByRole('table');
    const headers = within(table).getAllByRole('columnheader');
    const columnIndex = headers.findIndex(
      (header) => header.textContent?.includes(columnLabel)
    );

    if (columnIndex === -1) {
      throw new Error(`Column "${columnLabel}" not found`);
    }

    const rows = within(table).getAllByRole('row').slice(1); // Skip header row
    return rows.map((row) => {
      const cells = within(row).getAllByRole('cell');
      return cells[columnIndex]?.textContent || '';
    });
  },

  /**
   * Get the number of data rows (excluding header)
   */
  getRowCount(): number {
    const table = screen.getByRole('table');
    const rows = within(table).getAllByRole('row');
    return Math.max(0, rows.length - 1); // Subtract header row
  },

  /**
   * Get all row checkboxes
   */
  getRowCheckboxes(): HTMLInputElement[] {
    const table = screen.getByRole('table');
    return within(table)
      .getAllByRole('checkbox')
      .filter((cb) => !cb.getAttribute('aria-label')?.includes('Select all'))
      .map((cb) => cb as HTMLInputElement);
  },

  /**
   * Get the "Select All" checkbox
   */
  getSelectAllCheckbox(): HTMLInputElement {
    return screen.getByRole('checkbox', {
      name: /select all/i,
    }) as HTMLInputElement;
  },

  /**
   * Click a row by text content
   */
  async clickRowByText(user: UserEvent, text: string): Promise<void> {
    const row = screen.getByRole('row', { name: new RegExp(text) });
    await user.click(row);
  },

  /**
   * Assert all row checkboxes match expected state
   */
  expectAllRowCheckboxes(expectedChecked: boolean): void {
    const checkboxes = tableHelpers.getRowCheckboxes();
    checkboxes.forEach((checkbox) => {
      if (expectedChecked) {
        expect(checkbox).toBeChecked();
      } else {
        expect(checkbox).not.toBeChecked();
      }
    });
  },

  /**
   * Get a specific row by index (0-based, excludes header)
   */
  getRow(index: number): HTMLElement {
    const table = screen.getByRole('table');
    const rows = within(table).getAllByRole('row').slice(1);
    if (index >= rows.length) {
      throw new Error(`Row ${index} not found. Table has ${rows.length} rows.`);
    }
    return rows[index];
  },
};

/**
 * Helpers for PatternFly Pagination components
 */
export const paginationHelpers = {
  /**
   * Get pagination info: start, end, and total items
   */
  getPaginationInfo(): { start: number; end: number; total: number } | null {
    try {
      // PatternFly pagination typically shows "1 - 10 of 100"
      const paginationText = screen.getByText(/\d+ - \d+ of \d+/);
      const match = paginationText.textContent?.match(/(\d+) - (\d+) of (\d+)/);
      if (match) {
        return {
          start: parseInt(match[1], 10),
          end: parseInt(match[2], 10),
          total: parseInt(match[3], 10),
        };
      }
    } catch {
      // Pagination not found
    }
    return null;
  },

  /**
   * Click "Next" page button
   */
  async goToNextPage(user: UserEvent, index = 0): Promise<void> {
    const buttons = screen.getAllByRole('button', { name: /go to next page/i });
    await user.click(buttons[index]);
  },

  /**
   * Click "Previous" page button
   */
  async goToPreviousPage(user: UserEvent, index = 0): Promise<void> {
    const buttons = screen.getAllByRole('button', { name: /go to previous page/i });
    await user.click(buttons[index]);
  },

  /**
   * Get current page number
   */
  getCurrentPage(): number | null {
    try {
      // PatternFly pagination shows current page in an input
      const pageInput = screen.getByRole('spinbutton', {
        name: /current page/i,
      }) as HTMLInputElement;
      return parseInt(pageInput.value, 10);
    } catch {
      // Try alternative - look for active page button
      try {
        const activeButton = screen.getByRole('button', {
          pressed: true,
        });
        return parseInt(activeButton.textContent || '1', 10);
      } catch {
        return null;
      }
    }
  },

  /**
   * Go to a specific page number
   */
  async goToPage(user: UserEvent, pageNumber: number): Promise<void> {
    const pageInput = screen.getByRole('spinbutton', {
      name: /current page/i,
    }) as HTMLInputElement;
    await user.clear(pageInput);
    await user.type(pageInput, pageNumber.toString());
    await user.keyboard('{Enter}');
  },
};

/**
 * Helpers for PatternFly Modal and Drawer components
 */
export const modalHelpers = {
  /**
   * Assert a modal is open with the given title
   */
  expectModalOpen(titleText: string): void {
    const modal = screen.getByRole('dialog');
    expect(modal).toBeInTheDocument();
    expect(within(modal).getByText(titleText)).toBeInTheDocument();
  },

  /**
   * Close an open modal by clicking the X button
   */
  async closeModal(user: UserEvent): Promise<void> {
    const modal = screen.getByRole('dialog');
    const closeButton = within(modal).getByRole('button', { name: /close/i });
    await user.click(closeButton);
  },

  /**
   * Assert a drawer is open
   */
  expectDrawerOpen(): void {
    // PatternFly drawers have specific classes and structure
    const drawer = document.querySelector('.pf-v6-c-drawer__panel');
    expect(drawer).toBeInTheDocument();
  },

  /**
   * Close a drawer by clicking the X button
   */
  async closeDrawer(user: UserEvent): Promise<void> {
    const drawer = document.querySelector('.pf-v6-c-drawer__panel');
    if (!drawer) {
      throw new Error('Drawer not found');
    }
    const closeButton = within(drawer as HTMLElement).getByRole('button', {
      name: /close/i,
    });
    await user.click(closeButton);
  },

  /**
   * Get modal content area
   */
  getModalContent(): HTMLElement {
    const modal = screen.getByRole('dialog');
    return within(modal).getByRole('document') || modal;
  },

  /**
   * Click a button inside the modal by name
   */
  async clickModalButton(user: UserEvent, buttonName: RegExp | string): Promise<void> {
    const modal = screen.getByRole('dialog');
    const button = within(modal).getByRole('button', { name: buttonName });
    await user.click(button);
  },
};

/**
 * Helpers for PatternFly form components
 */
export const formHelpers = {
  /**
   * Fill a text input by label
   */
  async fillInput(user: UserEvent, label: string, value: string): Promise<void> {
    const input = screen.getByLabelText(label);
    await user.clear(input);
    await user.type(input, value);
  },

  /**
   * Select an option from a PatternFly Select component
   */
  async selectOption(user: UserEvent, selectLabel: string, optionText: string): Promise<void> {
    const select = screen.getByLabelText(selectLabel);
    await user.click(select);
    const option = screen.getByRole('option', { name: optionText });
    await user.click(option);
  },

  /**
   * Toggle a checkbox by label
   */
  async toggleCheckbox(user: UserEvent, label: string): Promise<void> {
    const checkbox = screen.getByLabelText(label);
    await user.click(checkbox);
  },

  /**
   * Submit a form
   */
  async submitForm(user: UserEvent): Promise<void> {
    const submitButton = screen.getByRole('button', { name: /submit|save|create/i });
    await user.click(submitButton);
  },
};

/**
 * Helpers for common async patterns
 */
export const asyncHelpers = {
  /**
   * Wait for loading to complete (loading spinner to disappear)
   */
  async waitForLoadingToComplete(): Promise<void> {
    await screen.findByRole('progressbar', {}, { timeout: 100 }).catch(() => {
      // Loading may have already completed
    });
    // Wait for spinner to disappear
    await new Promise((resolve) => setTimeout(resolve, 50));
  },

  /**
   * Wait for a specific text to appear
   */
  async waitForText(text: string | RegExp): Promise<HTMLElement> {
    return screen.findByText(text);
  },
};

/**
 * Re-export commonly used testing-library utilities for convenience
 */
export { screen, within } from '@testing-library/react';
