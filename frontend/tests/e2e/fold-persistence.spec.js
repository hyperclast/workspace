/**
 * End-to-end tests for fold persistence.
 *
 * These tests verify that folded sections are remembered in localStorage
 * and restored when the page is reloaded.
 *
 * Run with:
 *   npx playwright test fold-persistence.spec.js --headed
 */

import { test, expect } from "@playwright/test";

const BASE_URL = process.env.TEST_BASE_URL || "http://localhost:9800";
const TEST_EMAIL = process.env.TEST_EMAIL || "dev@localhost";
const TEST_PASSWORD = process.env.TEST_PASSWORD || "dev";

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

function getPageIdFromUrl(url) {
  const match = url.match(/\/pages\/([^/]+)/);
  return match ? match[1] : null;
}

test.describe("Fold Persistence", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!TEST_EMAIL || !TEST_PASSWORD, "TEST_EMAIL and TEST_PASSWORD required");
  });

  test("fold state is restored after page reload", async ({ page }) => {
    await login(page);

    await page.waitForFunction(() => window.isCollabSynced?.() === true, { timeout: 15000 });

    const pageId = getPageIdFromUrl(page.url());
    console.log(`📍 Page ID: ${pageId}`);

    // Add test content with headings
    await page.click(".cm-content");
    await page.keyboard.press("Meta+a");
    await page.keyboard.type(`# Test Section

This is content that will be folded.
More content here.
And more.

# Another Section

This should remain visible.
`);

    await page.waitForFunction(() => window.isCollabSynced?.() === true, { timeout: 10000 });
    await page.waitForTimeout(500);

    // Use toolbar button to fold all
    const foldAllBtn = page.locator('button[title="Fold all sections"]');
    await foldAllBtn.click();
    console.log("✅ Clicked fold all button");

    await page.waitForTimeout(300);

    // Verify folds exist
    const foldsBefore = await page.locator(".cm-foldPlaceholder").count();
    console.log(`📁 Folds before reload: ${foldsBefore}`);
    expect(foldsBefore).toBeGreaterThan(0);

    // Check localStorage
    const storage = await page.evaluate((pid) => {
      return localStorage.getItem(`page-folds-${pid}`);
    }, pageId);
    console.log(`📦 localStorage: ${storage}`);
    expect(storage).not.toBeNull();

    // Reload the page
    console.log("🔄 Reloading page...");
    await page.reload();

    // Wait for editor to be ready
    await page.waitForSelector(".cm-content", { timeout: 10000 });
    await page.waitForFunction(() => window.isCollabSynced?.() === true, { timeout: 15000 });
    console.log("✅ Page reloaded and synced");

    // Check if folds were restored
    await page.waitForTimeout(500);
    const foldsAfter = await page.locator(".cm-foldPlaceholder").count();
    console.log(`📁 Folds after reload: ${foldsAfter}`);

    expect(foldsAfter).toBe(foldsBefore);
    console.log("✅ Fold state restored after reload");
  });

  test("unfold all clears localStorage", async ({ page }) => {
    await login(page);

    await page.waitForFunction(() => window.isCollabSynced?.() === true, { timeout: 15000 });

    const pageId = getPageIdFromUrl(page.url());

    // Add test content
    await page.click(".cm-content");
    await page.keyboard.press("Meta+a");
    await page.keyboard.type(`# Section One

Content here.

# Section Two

More content.
`);

    await page.waitForFunction(() => window.isCollabSynced?.() === true, { timeout: 10000 });
    await page.waitForTimeout(500);

    // Fold all
    const foldAllBtn = page.locator('button[title="Fold all sections"]');
    await foldAllBtn.click();
    await page.waitForTimeout(300);

    // Verify localStorage has data
    let storage = await page.evaluate((pid) => {
      return localStorage.getItem(`page-folds-${pid}`);
    }, pageId);
    expect(storage).not.toBeNull();
    console.log(`📦 localStorage after fold: ${storage}`);

    // Unfold all
    const unfoldAllBtn = page.locator('button[title="Expand all sections"]');
    await unfoldAllBtn.click();
    await page.waitForTimeout(300);

    // Verify localStorage is cleared
    storage = await page.evaluate((pid) => {
      return localStorage.getItem(`page-folds-${pid}`);
    }, pageId);
    expect(storage).toBeNull();
    console.log("✅ localStorage cleared after unfold all");
  });
});
