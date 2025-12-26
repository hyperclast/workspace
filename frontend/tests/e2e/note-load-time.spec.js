/**
 * End-to-end test for measuring page content load time.
 *
 * This test measures how long it takes from page load to content appearing
 * in the editor. The goal is to catch performance regressions where content
 * takes too long to hydrate.
 *
 * Run with:
 *   npm run test:load-time
 *
 * Or for headed mode (to see the browser):
 *   npm run test:load-time -- --headed
 *
 * To test with YOUR account (for debugging real issues):
 *   TEST_EMAIL=you@example.com TEST_PASSWORD=yourpass npm run test:load-time -- --headed
 *
 * To test a specific page:
 *   TEST_EMAIL=you@example.com TEST_PASSWORD=yourpass TEST_PAGE_ID=abc123 npm run test:load-time -- --headed
 */

import { test, expect } from '@playwright/test';

// Configuration
const BASE_URL = process.env.TEST_BASE_URL || 'http://localhost:9800';

// Performance thresholds
const MAX_ACCEPTABLE_LOAD_TIME_MS = 3000; // 3 seconds max
const WARNING_LOAD_TIME_MS = 1000; // Warn if over 1 second

// Check if user provided existing credentials
const EXISTING_EMAIL = process.env.TEST_EMAIL;
const EXISTING_PASSWORD = process.env.TEST_PASSWORD;
const EXISTING_PAGE_ID = process.env.TEST_PAGE_ID;
const USE_EXISTING_ACCOUNT = EXISTING_EMAIL && EXISTING_PASSWORD;

// Generate unique test user credentials (only used if no existing account)
const TEST_USER_EMAIL = USE_EXISTING_ACCOUNT ? EXISTING_EMAIL : `test-${Date.now()}@example.com`;
const TEST_USER_PASSWORD = USE_EXISTING_ACCOUNT ? EXISTING_PASSWORD : 'TestPassword123!';
const TEST_PAGE_CONTENT = 'Performance test content - loaded successfully!';

test.describe('Page Content Load Time', () => {
  let csrfToken = '';
  let testPageId = EXISTING_PAGE_ID || '';
  let shouldCleanup = !USE_EXISTING_ACCOUNT;

  test.beforeAll(async ({ browser }) => {
    if (USE_EXISTING_ACCOUNT) {
      console.log(`\n🔧 Using existing account: ${TEST_USER_EMAIL}`);
      if (EXISTING_PAGE_ID) {
        console.log(`   Testing page: ${EXISTING_PAGE_ID}`);
      }
      return;
    }

    console.log(`\n🔧 Setting up test user: ${TEST_USER_EMAIL}`);

    // Create a new browser context for setup
    const context = await browser.newContext();
    const page = await context.newPage();

    // Step 1: Sign up via the UI
    await page.goto(`${BASE_URL}/signup`);
    await page.waitForSelector('#signup-email', { timeout: 10000 });

    await page.fill('#signup-email', TEST_USER_EMAIL);
    await page.fill('#signup-password', TEST_USER_PASSWORD);
    await page.click('button[type="submit"]');

    // Wait for redirect to editor after signup
    await page.waitForSelector('#editor', { timeout: 15000 });
    await page.waitForSelector('.cm-content', { timeout: 10000 });
    console.log('✅ Test user created and logged in');

    // Step 2: Type content into the editor (this creates CRDT data)
    await page.click('.cm-content');
    await page.keyboard.type(TEST_PAGE_CONTENT);

    // Wait a moment for CRDT to sync
    await page.waitForTimeout(1000);
    console.log('✅ Test content typed into editor');

    // Step 3: Get the current page ID
    const url = page.url();
    const pageMatch = url.match(/[?&]page=([^&]+)/);
    if (pageMatch) {
      testPageId = pageMatch[1];
    } else {
      const activePage = await page.$('.sidenav-item.active');
      if (activePage) {
        const href = await activePage.getAttribute('href');
        const match = href?.match(/page=([^&]+)/);
        if (match) testPageId = match[1];
      }
    }

    if (!testPageId) {
      testPageId = await page.evaluate(() => {
        return window.currentPage?.external_id || '';
      });
    }

    console.log(`✅ Test page ID: ${testPageId}`);

    // Get CSRF token for cleanup later
    csrfToken = await page.evaluate(() => window._csrfToken || '');

    await context.close();
  });

  test('content should appear within acceptable time (hard reload)', async ({ page }) => {
    // Login first
    await page.goto(`${BASE_URL}/login`);
    await page.waitForSelector('#login-email', { timeout: 10000 });
    await page.fill('#login-email', TEST_USER_EMAIL);
    await page.fill('#login-password', TEST_USER_PASSWORD);
    await page.click('button[type="submit"]');
    await page.waitForSelector('#editor', { timeout: 15000 });

    // Navigate to the test page first
    const targetUrl = testPageId
      ? `${BASE_URL}/pages/${testPageId}/`
      : `${BASE_URL}/`;
    await page.goto(targetUrl);
    await page.waitForSelector('.cm-content', { timeout: 30000 });

    // Wait for initial content to load (for existing accounts)
    if (USE_EXISTING_ACCOUNT) {
      await page.waitForFunction(() => {
        const content = document.querySelector('.cm-content');
        return content && content.textContent.trim().length > 0;
      }, { timeout: 30000 });
    }

    // Clear browser cache (but keep cookies/session)
    const client = await page.context().newCDPSession(page);
    await client.send('Network.clearBrowserCache');

    // Clear service worker caches
    await page.evaluate(async () => {
      if ('caches' in window) {
        const names = await caches.keys();
        await Promise.all(names.map(name => caches.delete(name)));
      }
    });

    console.log('\n🔄 Performing HARD RELOAD (browser cache cleared)...');

    // Now do a HARD RELOAD and measure
    const startTime = Date.now();
    await page.reload({ waitUntil: 'commit' });

    // Wait for the editor content to appear
    const editorContent = page.locator('.cm-content');
    await expect(editorContent).toBeVisible({ timeout: 60000 });

    // Wait for content to appear
    const expectedContent = USE_EXISTING_ACCOUNT ? null : TEST_PAGE_CONTENT;
    await page.waitForFunction(
      (expected) => {
        const content = document.querySelector('.cm-content');
        if (!content) return false;
        const text = content.textContent || '';
        // For existing accounts, just check there's some content
        // For test accounts, check for specific content
        return expected ? text.includes(expected) : text.trim().length > 0;
      },
      expectedContent,
      { timeout: 60000 }
    );

    const endTime = Date.now();
    const loadTimeMs = endTime - startTime;

    console.log(`\n📊 HARD RELOAD Load Time: ${loadTimeMs}ms (${(loadTimeMs / 1000).toFixed(2)}s)`);

    if (loadTimeMs > MAX_ACCEPTABLE_LOAD_TIME_MS) {
      console.error(`❌ Load time exceeds ${MAX_ACCEPTABLE_LOAD_TIME_MS}ms threshold!`);
      if (USE_EXISTING_ACCOUNT) {
        console.log(`\n💡 This confirms the performance issue is NOT browser caching.`);
        console.log(`   Check: WebSocket connection time, CRDT data size, backend response time.`);
      }
    } else if (loadTimeMs > WARNING_LOAD_TIME_MS) {
      console.warn(`⚠️  Load time exceeds warning threshold of ${WARNING_LOAD_TIME_MS}ms`);
    } else {
      console.log(`✅ Load time is acceptable`);
    }

    expect(loadTimeMs).toBeLessThan(MAX_ACCEPTABLE_LOAD_TIME_MS);
  });

  test('measure detailed timing breakdown', async ({ page }) => {
    // Login first
    await page.goto(`${BASE_URL}/login`);
    await page.waitForSelector('#login-email', { timeout: 10000 });
    await page.fill('#login-email', TEST_USER_EMAIL);
    await page.fill('#login-password', TEST_USER_PASSWORD);
    await page.click('button[type="submit"]');
    await page.waitForSelector('#editor', { timeout: 15000 });

    // Navigate to the test page
    const targetUrl = testPageId ? `${BASE_URL}/pages/${testPageId}/` : `${BASE_URL}/`;

    // Clear cache first
    const client = await page.context().newCDPSession(page);
    await client.send('Network.clearBrowserCache');

    console.log('\n🔄 Navigating with cleared cache...');

    const startTime = Date.now();
    await page.goto(targetUrl);

    // Measure various milestones
    let editorVisibleTime = null;
    let contentVisibleTime = null;

    // Poll for milestones
    while (Date.now() - startTime < 60000) {
      const state = await page.evaluate((expected) => {
        const editor = document.querySelector('.cm-editor');
        const content = document.querySelector('.cm-content');
        const text = content?.textContent || '';
        return {
          editorExists: !!editor,
          contentExists: !!content,
          hasContent: expected ? text.includes(expected) : text.trim().length > 0,
        };
      }, USE_EXISTING_ACCOUNT ? null : TEST_PAGE_CONTENT);

      if (state.editorExists && !editorVisibleTime) {
        editorVisibleTime = Date.now() - startTime;
      }

      if (state.hasContent && !contentVisibleTime) {
        contentVisibleTime = Date.now() - startTime;
        break;
      }

      await page.waitForTimeout(50);
    }

    console.log('\n📊 Detailed Timing Breakdown:');
    console.log(`   Page navigation started: 0ms`);
    if (editorVisibleTime) {
      console.log(`   Editor visible: ${editorVisibleTime}ms`);
    }
    if (contentVisibleTime) {
      console.log(`   Content visible: ${contentVisibleTime}ms`);

      if (editorVisibleTime && contentVisibleTime > editorVisibleTime) {
        const wsTime = contentVisibleTime - editorVisibleTime;
        console.log(`   ⏱️  Time waiting for WebSocket/CRDT: ~${wsTime}ms`);
      }
    } else {
      console.error('   ❌ Content never appeared!');
    }

    expect(contentVisibleTime).not.toBeNull();
    expect(contentVisibleTime).toBeLessThan(MAX_ACCEPTABLE_LOAD_TIME_MS);
  });

  test.afterAll(async ({ request }) => {
    if (!shouldCleanup || !testPageId) {
      if (USE_EXISTING_ACCOUNT) {
        console.log(`\nℹ️  Existing account used - no cleanup needed`);
      }
      return;
    }

    // Cleanup: Delete the test page
    console.log(`\n🧹 Cleaning up test page: ${testPageId}`);
    try {
      const response = await request.delete(`${BASE_URL}/api/pages/${testPageId}/`, {
        headers: {
          'X-CSRFToken': csrfToken,
        },
      });
      if (response.ok()) {
        console.log('✅ Test page deleted');
      } else {
        console.warn(`⚠️  Could not delete test page: ${response.status()}`);
      }
    } catch (e) {
      console.warn('⚠️  Could not delete test page:', e.message);
    }

    console.log(`ℹ️  Test user ${TEST_USER_EMAIL} left in database (no delete API)`);
  });
});
