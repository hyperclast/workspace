/**
 * End-to-end test for page creation URL update.
 *
 * This test verifies that when a new page is created, the URL updates
 * to reflect the new page's ID.
 *
 * Run with:
 *   TEST_EMAIL=you@example.com TEST_PASSWORD=yourpass npx playwright test page-creation-url.spec.js --headed
 */

import { test, expect } from "@playwright/test";

const BASE_URL = process.env.TEST_BASE_URL || "http://localhost:9800";
const TEST_EMAIL = process.env.TEST_EMAIL;
const TEST_PASSWORD = process.env.TEST_PASSWORD;

test.describe("Page Creation URL Update", () => {
  test("URL should update when creating a new page", async ({ page }) => {
    // Login
    console.log(`\n🔧 Logging in: ${TEST_EMAIL}`);
    await page.goto(`${BASE_URL}/login`);
    await page.waitForSelector("#login-email", { timeout: 10000 });
    await page.fill("#login-email", TEST_EMAIL);
    await page.fill("#login-password", TEST_PASSWORD);
    await page.click('button[type="submit"]');

    // Wait for editor
    await page.waitForSelector("#editor", { timeout: 20000 });
    await page.waitForSelector(".cm-content", { timeout: 10000 });
    console.log("✅ Logged in");

    // Get initial page ID from URL
    const initialUrl = page.url();
    const initialMatch = initialUrl.match(/\/pages\/([^/]+)/);
    const initialPageId = initialMatch ? initialMatch[1] : null;
    console.log(`📍 Initial page ID: ${initialPageId}`);

    // Create a new page
    const newPageBtn = page.locator(".sidebar-new-page-btn").first();
    await newPageBtn.click();

    // Handle the "New Page" modal
    const modalInput = page.locator("#prompt-input, .modal-input");
    const createBtn = page.locator('.modal button.primary-btn, button:has-text("Create")');

    const newPageTitle = `URL Test Page ${Date.now()}`;
    try {
      await modalInput.waitFor({ timeout: 2000 });
      console.log("📝 Filling in page title...");
      await modalInput.fill(newPageTitle);
      await createBtn.click();
    } catch {
      console.log("ℹ️  No modal, continuing...");
    }

    // Wait for the new page to load
    await page.waitForSelector(".sidebar-item.active", { timeout: 10000 });
    await page.waitForSelector(".cm-content", { timeout: 10000 });
    await page.waitForTimeout(2000); // Give time for URL to update
    console.log(`✅ Created page: ${newPageTitle}`);

    // THE BUG: URL should have changed to the new page ID
    const newUrl = page.url();
    const newMatch = newUrl.match(/\/pages\/([^/]+)/);
    const newPageId = newMatch ? newMatch[1] : null;
    console.log(`📍 New URL page ID: ${newPageId}`);
    console.log(`📍 Initial: ${initialPageId}, New: ${newPageId}`);

    // Verify URL changed to a different page ID
    expect(newPageId).not.toBeNull();
    expect(newPageId).not.toBe(initialPageId);
    console.log("✅ URL updated correctly to new page ID");
  });
});
