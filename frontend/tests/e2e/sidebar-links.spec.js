/**
 * End-to-end test for sidebar links (backlinks) navigation.
 *
 * This test verifies that:
 * 1. Creating a link between pages generates a backlink
 * 2. Backlinks appear in the Ref sidebar
 * 3. Clicking backlinks navigates correctly without breaking the app
 *
 * Run with:
 *   npx playwright test sidebar-links.spec.js --headed
 *
 * To test with a different account:
 *   TEST_EMAIL=you@example.com TEST_PASSWORD=yourpass npx playwright test sidebar-links.spec.js --headed
 */

import { test, expect } from "@playwright/test";

const BASE_URL = process.env.TEST_BASE_URL || "http://localhost:9800";
const TEST_EMAIL = process.env.TEST_EMAIL || "dev@localhost";
const TEST_PASSWORD = process.env.TEST_PASSWORD || "dev";

test.describe("Sidebar Links Navigation", () => {
  test.setTimeout(120000);

  test("backlinks should appear and be clickable after creating internal link", async ({
    page,
  }) => {
    console.log(`\n🔧 Logging in as: ${TEST_EMAIL}`);
    await page.goto(`${BASE_URL}/login`);
    await page.waitForSelector("#login-email", { timeout: 10000 });
    await page.fill("#login-email", TEST_EMAIL);
    await page.fill("#login-password", TEST_PASSWORD);
    await page.click('button[type="submit"]');

    await page.waitForSelector("#editor", { timeout: 20000 });
    await page.waitForSelector(".cm-content", { timeout: 10000 });
    console.log("✅ Logged in");

    // Step 1: Create target page
    const targetPageTitle = `Target ${Date.now()}`;
    const newPageBtn = page.locator(".sidebar-new-page-btn").first();
    await newPageBtn.click();

    const modalInput = page.locator("#prompt-input, .modal-input");
    const createBtn = page.locator('.modal button.primary-btn, button:has-text("Create")');

    try {
      await modalInput.waitFor({ timeout: 2000 });
      await modalInput.fill(targetPageTitle);
      await createBtn.click();
    } catch {
      // Modal might not appear in some UI states
    }

    await page.waitForSelector(".sidebar-item.active", { timeout: 10000 });
    await page.waitForSelector(".cm-content", { timeout: 10000 });

    // Wait for currentPage to be set with the correct title
    const targetPageId = await page.evaluate(async (expectedTitle) => {
      for (let i = 0; i < 20; i++) {
        if (
          window.currentPage?.title === expectedTitle ||
          window.currentPage?.details?.title === expectedTitle
        ) {
          return window.currentPage.external_id;
        }
        await new Promise((r) => setTimeout(r, 250));
      }
      // Fallback to URL
      const match = window.location.pathname.match(/\/pages\/([^/]+)/);
      return match ? match[1] : window.currentPage?.external_id || "";
    }, targetPageTitle);
    console.log(`✅ Created target page: ${targetPageTitle}`);
    console.log(`   Target page ID: ${targetPageId}`);

    // Step 2: Create source page with link to target
    const sourcePageTitle = `Source ${Date.now()}`;
    await newPageBtn.click();

    try {
      await modalInput.waitFor({ timeout: 2000 });
      await modalInput.fill(sourcePageTitle);
      await createBtn.click();
    } catch {
      // Modal might not appear
    }

    await page.waitForSelector(".sidebar-item.active", { timeout: 10000 });
    await page.waitForSelector(".cm-content", { timeout: 10000 });

    // Wait for currentPage to be set with the correct title
    await page.evaluate(async (expectedTitle) => {
      for (let i = 0; i < 20; i++) {
        if (
          window.currentPage?.title === expectedTitle ||
          window.currentPage?.details?.title === expectedTitle
        ) {
          return;
        }
        await new Promise((r) => setTimeout(r, 250));
      }
    }, sourcePageTitle);
    console.log(`✅ Created source page: ${sourcePageTitle}`);

    // Type a link to the target page
    await page.click(".cm-content");
    await page.keyboard.type(`Link to target: [${targetPageTitle}](/pages/${targetPageId}/)`);
    await page.waitForTimeout(1000);

    // Get source page ID and trigger sync API directly
    const sourcePageId = await page.evaluate(() => {
      const match = window.location.pathname.match(/\/pages\/([^/]+)/);
      return match ? match[1] : window.currentPage?.external_id || "";
    });

    // Call sync API to save links immediately
    const syncResult = await page.evaluate(async (pageId) => {
      const content = window.editorView?.state?.doc?.toString() || "";
      const csrfToken =
        document.querySelector("[name=csrfmiddlewaretoken]")?.value ||
        document.cookie.match(/csrftoken=([^;]+)/)?.[1] ||
        "";

      const response = await fetch(`/api/pages/${pageId}/links/sync/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        credentials: "same-origin",
        body: JSON.stringify({ content }),
      });
      const data = response.ok ? await response.json() : null;
      return { ok: response.ok, status: response.status, data, content };
    }, sourcePageId);

    console.log(`✅ Sync result: ${JSON.stringify(syncResult)}`);

    // Step 3: Navigate to target page and check for backlink
    const targetLink = page.locator(".sidebar-item").filter({ hasText: targetPageTitle }).first();
    await targetLink.click();
    await page.waitForSelector(".cm-content", { timeout: 10000 });
    await page.waitForTimeout(2000);
    console.log("✅ Navigated to target page");

    // Open Ref sidebar - click another tab first, then Ref, to force a fresh fetch
    const refTabButton = page.locator('button:has-text("Ref"), .sidebar-tab:has-text("Ref")');
    const askTabButton = page.locator('button:has-text("Ask"), .sidebar-tab:has-text("Ask")');

    // First click Ask tab (if exists), then Ref tab to force LinksTab remount
    try {
      await askTabButton.click({ timeout: 1000 });
      await page.waitForTimeout(500);
    } catch {
      // Ask tab might not exist, that's ok
    }

    await refTabButton.click();
    await page.waitForTimeout(2000);
    console.log("✅ Opened Ref sidebar");

    // Wait for backlinks to appear - the link-item button contains the source page title
    const backlinkTitle = page
      .locator(".link-item-title")
      .filter({ hasText: sourcePageTitle })
      .first();

    console.log(`⏳ Waiting for backlink "${sourcePageTitle}" to appear...`);
    await expect(backlinkTitle).toBeVisible({ timeout: 30000 });
    console.log("✅ Backlink is visible in Ref sidebar");

    // Step 4: Click the parent button to navigate
    const backlinkButton = page.locator(".link-item").filter({ hasText: sourcePageTitle }).first();
    await backlinkButton.click();
    await page.waitForTimeout(1500);
    console.log("✅ Clicked backlink");

    // Verify we navigated to source page
    const editor = page.locator("#editor");
    await expect(editor).toBeVisible({ timeout: 5000 });
    console.log("✅ Editor is visible after navigation");

    const cmContent = page.locator(".cm-content");
    await expect(cmContent).toBeVisible({ timeout: 5000 });
    const contentText = await cmContent.textContent();
    expect(contentText).toContain(targetPageTitle);
    console.log("✅ Source page content loaded correctly (contains link to target)");

    // Verify sidebar is functional
    const sidenav = page.locator(".sidenav, #note-sidebar");
    await expect(sidenav).toBeVisible({ timeout: 5000 });
    console.log("✅ Sidenav is visible");

    console.log("\n✅ TEST PASSED: Backlinks work correctly");
  });
});
