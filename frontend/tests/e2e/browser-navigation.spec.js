/**
 * End-to-end tests for browser back/forward navigation.
 *
 * These tests verify that browser back/forward buttons work correctly
 * across the SPA, especially when navigating between different page types
 * (editor pages, settings, etc.).
 *
 * Run with:
 *   TEST_EMAIL=you@example.com TEST_PASSWORD=yourpass npx playwright test browser-navigation.spec.js --headed
 */

import { test, expect } from "@playwright/test";

const BASE_URL = process.env.TEST_BASE_URL || "http://localhost:9800";
const TEST_EMAIL = process.env.TEST_EMAIL;
const TEST_PASSWORD = process.env.TEST_PASSWORD;

async function login(page) {
  console.log(`\n🔧 Logging in: ${TEST_EMAIL}`);
  await page.goto(`${BASE_URL}/login`);
  await page.waitForSelector("#login-email", { timeout: 10000 });
  await page.fill("#login-email", TEST_EMAIL);
  await page.fill("#login-password", TEST_PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForSelector("#editor", { timeout: 20000 });
  await page.waitForSelector(".cm-content", { timeout: 10000 });
  console.log("✅ Logged in");
}

async function verifyEditorPageIntegrity(page) {
  const editor = page.locator("#editor");
  await expect(editor).toBeVisible({ timeout: 5000 });

  const cmContent = page.locator(".cm-content");
  await expect(cmContent).toBeVisible({ timeout: 5000 });

  const sidenav = page.locator("#note-sidebar");
  await expect(sidenav).toBeVisible({ timeout: 5000 });

  const sidebar = page.locator("#chat-sidebar, .chat-sidebar").first();
  await expect(sidebar).toBeVisible({ timeout: 5000 });

  const breadcrumb = page.locator("#breadcrumb-row");
  await expect(breadcrumb).toBeVisible({ timeout: 5000 });
}

async function verifySettingsPageIntegrity(page) {
  const settingsRoot = page.locator("#settings-page-root").first();
  await expect(settingsRoot).toBeVisible({ timeout: 5000 });

  const settingsContent = page.locator(".settings-content, .settings-container").first();
  await expect(settingsContent).toBeVisible({ timeout: 5000 });
}

function getPageIdFromUrl(url) {
  const match = url.match(/\/pages\/([^/]+)/);
  return match ? match[1] : null;
}

test.describe("Browser Back/Forward Navigation", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!TEST_EMAIL || !TEST_PASSWORD, "TEST_EMAIL and TEST_PASSWORD required");
  });

  test("back/forward between two editor pages", async ({ page }) => {
    await login(page);

    // Get initial page info
    const page1Url = page.url();
    const page1Id = getPageIdFromUrl(page1Url);
    console.log(`📍 Page 1 ID: ${page1Id}`);

    // Create a second page
    const newPageBtn = page.locator(".sidebar-new-page-btn").first();
    await newPageBtn.click();

    // Handle the modal
    const modalInput = page.locator("#prompt-input, .modal-input");
    try {
      await modalInput.waitFor({ timeout: 2000 });
      await modalInput.fill(`Test Page ${Date.now()}`);
      await page.locator('button:has-text("Create")').click();
    } catch {
      console.log("ℹ️  No modal");
    }

    await page.waitForSelector(".cm-content", { timeout: 10000 });
    await page.waitForTimeout(1500);

    const page2Url = page.url();
    const page2Id = getPageIdFromUrl(page2Url);
    console.log(`📍 Page 2 ID: ${page2Id}`);
    expect(page2Id).not.toBe(page1Id);

    // Navigate back to page 1
    console.log("⬅️  Going back...");
    await page.goBack();
    await page.waitForTimeout(1500);

    // Verify we're back on page 1
    const backUrl = page.url();
    expect(getPageIdFromUrl(backUrl)).toBe(page1Id);
    console.log("✅ Back navigation: URL correct");

    // Verify page integrity
    await verifyEditorPageIntegrity(page);
    console.log("✅ Back navigation: Page integrity verified");

    // Navigate forward to page 2
    console.log("➡️  Going forward...");
    await page.goForward();
    await page.waitForTimeout(1500);

    // Verify we're on page 2
    const forwardUrl = page.url();
    expect(getPageIdFromUrl(forwardUrl)).toBe(page2Id);
    console.log("✅ Forward navigation: URL correct");

    // Verify page integrity
    await verifyEditorPageIntegrity(page);
    console.log("✅ Forward navigation: Page integrity verified");

    console.log("\n✅ TEST PASSED: Back/forward between editor pages works");
  });

  test("back from settings to editor page", async ({ page }) => {
    await login(page);

    // Get initial page info
    const pageUrl = page.url();
    const pageId = getPageIdFromUrl(pageUrl);
    console.log(`📍 Editor page ID: ${pageId}`);

    // Navigate to settings
    console.log("🔧 Navigating to settings...");
    await page.goto(`${BASE_URL}/settings/`);
    await page.waitForTimeout(2000);

    // Verify settings page loaded
    await verifySettingsPageIntegrity(page);
    console.log("✅ Settings page loaded");

    // Navigate back to editor page
    console.log("⬅️  Going back to editor...");
    await page.goBack();
    await page.waitForTimeout(2000);

    // Verify URL
    const backUrl = page.url();
    expect(getPageIdFromUrl(backUrl)).toBe(pageId);
    console.log("✅ Back navigation: URL correct");

    // Verify full page integrity - this is the critical test
    await verifyEditorPageIntegrity(page);
    console.log("✅ Back navigation: Editor page integrity verified");

    // Verify sidebar tabs are working
    const refTab = page.locator('button:has-text("Ref"), [data-tab="links"]').first();
    await refTab.click();
    await page.waitForTimeout(500);
    const linksSection = page.locator(".links-section").first();
    await expect(linksSection).toBeVisible({ timeout: 5000 });
    console.log("✅ Sidebar is functional");

    console.log("\n✅ TEST PASSED: Back from settings to editor works");
  });

  test("forward from editor to settings after back", async ({ page }) => {
    await login(page);

    const pageId = getPageIdFromUrl(page.url());
    console.log(`📍 Editor page ID: ${pageId}`);

    // Navigate to settings
    console.log("🔧 Navigating to settings...");
    await page.goto(`${BASE_URL}/settings/`);
    await page.waitForTimeout(2000);
    await verifySettingsPageIntegrity(page);

    // Go back to editor
    console.log("⬅️  Going back...");
    await page.goBack();
    await page.waitForTimeout(2000);
    await verifyEditorPageIntegrity(page);

    // Go forward to settings
    console.log("➡️  Going forward to settings...");
    await page.goForward();
    await page.waitForTimeout(2000);

    // Verify settings page loaded correctly
    expect(page.url()).toContain("/settings/");
    await verifySettingsPageIntegrity(page);
    console.log("✅ Forward navigation: Settings page integrity verified");

    console.log("\n✅ TEST PASSED: Forward to settings works");
  });

  test("multiple back/forward cycles", async ({ page }) => {
    await login(page);

    const page1Id = getPageIdFromUrl(page.url());
    console.log(`📍 Starting on page: ${page1Id}`);

    // Create page 2 - wait for URL to actually change
    const newPageBtn = page.locator(".sidebar-new-page-btn").first();
    await newPageBtn.click();
    const modalInput = page.locator("#prompt-input, .modal-input");
    try {
      await modalInput.waitFor({ timeout: 2000 });
      await modalInput.fill(`Cycle Test ${Date.now()}`);
      await page.locator('button:has-text("Create")').click();
    } catch {
      // no modal
    }

    // Wait for URL to change to a different page
    await page.waitForFunction(
      (oldId) => {
        const match = window.location.pathname.match(/\/pages\/([^/]+)/);
        const newId = match ? match[1] : null;
        return newId && newId !== oldId;
      },
      page1Id,
      { timeout: 10000 }
    );
    await page.waitForSelector(".cm-content", { timeout: 10000 });
    const page2Id = getPageIdFromUrl(page.url());
    console.log(`📍 Created page 2: ${page2Id}`);

    // Go to settings
    await page.goto(`${BASE_URL}/settings/`);
    await page.waitForTimeout(1500);

    console.log(`📍 History: page1(${page1Id}) → page2(${page2Id}) → settings`);

    // Back to page 2
    console.log("⬅️  Back to page 2...");
    await page.goBack();
    await page.waitForTimeout(1500);
    expect(getPageIdFromUrl(page.url())).toBe(page2Id);
    await verifyEditorPageIntegrity(page);
    console.log("✅ Cycle 1: Back to page 2");

    // Back to page 1
    console.log("⬅️  Back to page 1...");
    await page.goBack();
    await page.waitForTimeout(1500);
    expect(getPageIdFromUrl(page.url())).toBe(page1Id);
    await verifyEditorPageIntegrity(page);
    console.log("✅ Cycle 2: Back to page 1");

    // Forward to page 2
    console.log("➡️  Forward to page 2...");
    await page.goForward();
    await page.waitForTimeout(1500);
    expect(getPageIdFromUrl(page.url())).toBe(page2Id);
    await verifyEditorPageIntegrity(page);
    console.log("✅ Cycle 3: Forward to page 2");

    // Forward to settings
    console.log("➡️  Forward to settings...");
    await page.goForward();
    await page.waitForTimeout(1500);
    expect(page.url()).toContain("/settings/");
    await verifySettingsPageIntegrity(page);
    console.log("✅ Cycle 4: Forward to settings");

    // Back all the way to page 1
    console.log("⬅️⬅️  Back twice to page 1...");
    await page.goBack();
    await page.waitForTimeout(1000);
    await page.goBack();
    await page.waitForTimeout(1500);
    expect(getPageIdFromUrl(page.url())).toBe(page1Id);
    await verifyEditorPageIntegrity(page);
    console.log("✅ Cycle 5: Double back to page 1");

    console.log("\n✅ TEST PASSED: Multiple back/forward cycles work");
  });

  test("editor content persists after back/forward", async ({ page }) => {
    await login(page);

    // Wait for editor to be ready
    await page.waitForSelector(".cm-content", { timeout: 10000 });
    await page.waitForTimeout(1000);

    // Wait for initial collaboration sync
    await page.waitForFunction(() => window.isCollabSynced?.() === true, { timeout: 15000 });
    console.log("✅ Collaboration synced");

    // Type some unique content
    const uniqueContent = `Navigation test content ${Date.now()}`;
    await page.click(".cm-content");
    await page.keyboard.type(uniqueContent);
    console.log(`📝 Typed content: ${uniqueContent}`);

    // Wait for content to sync to server (check that it's still synced after typing)
    await page.waitForFunction(() => window.isCollabSynced?.() === true, { timeout: 10000 });
    // Small buffer for the actual network round-trip
    await page.waitForTimeout(1000);
    console.log("✅ Content synced");

    const pageId = getPageIdFromUrl(page.url());

    // Navigate to settings
    await page.goto(`${BASE_URL}/settings/`);
    await page.waitForTimeout(1500);

    // Go back
    console.log("⬅️  Going back...");
    await page.goBack();
    await page.waitForTimeout(2000);

    // Verify page integrity
    await verifyEditorPageIntegrity(page);

    // Wait for collaboration to reconnect and sync
    await page.waitForFunction(() => window.isCollabSynced?.() === true, { timeout: 10000 });
    console.log("✅ Collaboration re-synced after navigation");

    // Now verify content is there
    const contentVisible = await page.waitForFunction(
      (content) => {
        const editor = document.querySelector(".cm-content");
        return editor && editor.textContent.includes(content);
      },
      uniqueContent,
      { timeout: 10000 }
    );
    expect(contentVisible).toBeTruthy();
    console.log("✅ Content persisted after back navigation");

    console.log("\n✅ TEST PASSED: Content persists after back/forward");
  });

  test("clicking internal links and then using back button", async ({ page }) => {
    await login(page);

    // Get current page
    const page1Id = getPageIdFromUrl(page.url());
    console.log(`📍 Initial page: ${page1Id}`);

    // Create a second page to ensure we have something to navigate to
    const newPageBtn = page.locator(".sidebar-new-page-btn").first();
    await newPageBtn.click();

    const modalInput = page.locator("#prompt-input, .modal-input");
    try {
      await modalInput.waitFor({ timeout: 2000 });
      await modalInput.fill(`Link Test Page ${Date.now()}`);
      await page.locator('button:has-text("Create")').click();
    } catch {
      // no modal
    }

    // Wait for URL to change to a different page
    await page.waitForFunction(
      (oldId) => {
        const match = window.location.pathname.match(/\/pages\/([^/]+)/);
        const newId = match ? match[1] : null;
        return newId && newId !== oldId;
      },
      page1Id,
      { timeout: 10000 }
    );
    await page.waitForSelector(".cm-content", { timeout: 10000 });

    const page2Id = getPageIdFromUrl(page.url());
    console.log(`📍 Created second page: ${page2Id}`);
    expect(page2Id).not.toBe(page1Id);

    // Now click on the first page in sidenav to go back
    console.log("🔗 Clicking on first page in sidenav...");
    const firstPageItem = page.locator(`.sidebar-item:not(.active)`).first();
    await firstPageItem.click();
    await page.waitForTimeout(1500);

    const page3Id = getPageIdFromUrl(page.url());
    expect(page3Id).not.toBe(page2Id);
    console.log(`📍 Navigated via sidenav to: ${page3Id}`);

    await verifyEditorPageIntegrity(page);

    // Use back button - should go back to page2
    console.log("⬅️  Going back...");
    await page.goBack();
    await page.waitForTimeout(1500);

    expect(getPageIdFromUrl(page.url())).toBe(page2Id);
    await verifyEditorPageIntegrity(page);
    console.log("✅ Back after sidenav click works");

    console.log("\n✅ TEST PASSED: Internal link navigation with back button");
  });
});
