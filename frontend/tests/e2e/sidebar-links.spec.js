/**
 * End-to-end test for sidebar links navigation.
 *
 * This test verifies that clicking links in the Ref sidebar properly
 * navigates to the linked page without breaking the app.
 *
 * Run with:
 *   npx playwright test sidebar-links.spec.js
 *
 * Or for headed mode (to see the browser):
 *   npx playwright test sidebar-links.spec.js --headed
 *
 * To test with an existing account (recommended):
 *   TEST_EMAIL=you@example.com TEST_PASSWORD=yourpass npx playwright test sidebar-links.spec.js --headed
 */

import { test, expect } from '@playwright/test';

// Configuration
const BASE_URL = process.env.TEST_BASE_URL || 'http://localhost:9800';

// Use existing account if provided, otherwise create new user
const EXISTING_EMAIL = process.env.TEST_EMAIL;
const EXISTING_PASSWORD = process.env.TEST_PASSWORD;
const USE_EXISTING_ACCOUNT = EXISTING_EMAIL && EXISTING_PASSWORD;

const TEST_USER_EMAIL = USE_EXISTING_ACCOUNT ? EXISTING_EMAIL : `test-links-${Date.now()}@example.com`;
const TEST_USER_PASSWORD = USE_EXISTING_ACCOUNT ? EXISTING_PASSWORD : 'TestPassword123!';

test.describe('Sidebar Links Navigation', () => {
  let page1Id = '';

  test('clicking a link in the Ref sidebar should navigate without breaking the app', async ({ page }) => {
    if (USE_EXISTING_ACCOUNT) {
      // Login with existing account
      console.log(`\n🔧 Logging in with existing account: ${TEST_USER_EMAIL}`);
      await page.goto(`${BASE_URL}/login`);
      await page.waitForSelector('#login-email', { timeout: 10000 });
      await page.fill('#login-email', TEST_USER_EMAIL);
      await page.fill('#login-password', TEST_USER_PASSWORD);
      await page.click('button[type="submit"]');
    } else {
      // Sign up a new test user
      console.log(`\n🔧 Creating test user: ${TEST_USER_EMAIL}`);
      await page.goto(`${BASE_URL}/signup`);
      await page.waitForSelector('#signup-email', { timeout: 10000 });
      await page.fill('#signup-email', TEST_USER_EMAIL);
      await page.fill('#signup-password', TEST_USER_PASSWORD);
      await page.click('button[type="submit"]');
    }

    // Wait for redirect to editor
    await page.waitForSelector('#editor', { timeout: 20000 });
    await page.waitForSelector('.cm-content', { timeout: 10000 });
    console.log('✅ Logged in');

    // Step 2: Get the first page ID (use current page as target)
    page1Id = await page.evaluate(() => {
      const match = window.location.pathname.match(/\/pages\/([^/]+)/);
      return match ? match[1] : window.currentPage?.external_id || '';
    });
    console.log(`✅ First page (target): ${page1Id}`);

    // Type a title for page 1 (target page) - use unique timestamp
    const targetPageTitle = `Target Page ${Date.now()}`;
    await page.click('.cm-content');
    await page.keyboard.type(targetPageTitle);
    await page.waitForTimeout(1000);

    // Step 3: Create a second page (source page with link)
    const newPageBtn = page.locator('.sidebar-new-page-btn').first();
    await newPageBtn.click();

    // Handle the "New Page" modal if it appears
    const modalInput = page.locator('#prompt-input, .modal-input');
    const createBtn = page.locator('.modal button.primary-btn, button:has-text("Create")');

    const sourcePageTitle = `Source Page ${Date.now()}`;
    try {
      await modalInput.waitFor({ timeout: 2000 });
      console.log('📝 New Page modal detected, filling in title...');
      await modalInput.fill(sourcePageTitle);
      await createBtn.click();
    } catch {
      // No modal, continue
      console.log('ℹ️  No modal detected, continuing...');
    }

    // Wait for the new page to appear in sidebar (it's selected/active)
    await page.waitForSelector('.sidebar-item.active', { timeout: 10000 });
    await page.waitForSelector('.cm-content', { timeout: 10000 });
    await page.waitForTimeout(1500); // Let everything settle
    console.log(`✅ Created source page: ${sourcePageTitle}`);

    // Type content with a link to page 1 (target page)
    await page.click('.cm-content');
    await page.keyboard.type(`\n\nThis links to [${targetPageTitle}](/pages/${page1Id}/)`);
    await page.waitForTimeout(2000); // Wait for link to be saved and synced
    console.log('✅ Added link to target page');

    // Step 4: Navigate to the target page (page 1) via full page load
    await page.goto(`${BASE_URL}/pages/${page1Id}/`);
    await page.waitForSelector('.cm-content', { timeout: 10000 });
    await page.waitForTimeout(1500);
    console.log('✅ Navigated to target page');

    // Step 5: Open the Ref sidebar tab
    const refTab = page.locator('button:has-text("Ref"), [data-tab="links"], .sidebar-tab:has-text("Ref")');
    await refTab.click();
    await page.waitForTimeout(1000);
    console.log('✅ Opened Ref sidebar');

    // Step 6: Wait for backlinks to load and verify the backlink appears
    const backlinksSection = page.locator('.links-section:has-text("BACKLINKS")');
    await expect(backlinksSection).toBeVisible({ timeout: 5000 });

    // Wait for the backlink item to appear (source page should show up)
    const backlinkItem = page.locator('.link-item-internal').first();
    await expect(backlinkItem).toBeVisible({ timeout: 10000 });
    console.log('✅ Backlink is visible in sidebar');

    // Step 7: Click the backlink to navigate - THIS IS THE BUG WE'RE TESTING
    await backlinkItem.click();
    console.log('✅ Clicked backlink');

    // Step 8: Verify the app didn't break - check critical elements are still visible
    // Wait a moment for navigation
    await page.waitForTimeout(2000);

    // The main editor container should still be visible
    const editor = page.locator('#editor');
    await expect(editor).toBeVisible({ timeout: 5000 });
    console.log('✅ Editor is still visible');

    // The right sidebar (chat sidebar) should still be visible (not disappeared)
    const sidebar = page.locator('#chat-sidebar, .chat-sidebar').first();
    await expect(sidebar).toBeVisible({ timeout: 5000 });
    console.log('✅ Sidebar is still visible');

    // The sidenav (left navigation) should still be visible
    const sidenav = page.locator('#note-sidebar');
    await expect(sidenav).toBeVisible({ timeout: 5000 });
    console.log('✅ Sidenav is still visible');

    // Verify content loaded in the editor - check for the source page content (link text)
    await page.waitForFunction(
      (targetTitle) => {
        const content = document.querySelector('.cm-content');
        return content && content.textContent.includes(targetTitle);
      },
      targetPageTitle,
      { timeout: 10000 }
    );
    console.log('✅ Content loaded correctly');

    console.log('\n✅ TEST PASSED: Sidebar link navigation works correctly');
  });
});
