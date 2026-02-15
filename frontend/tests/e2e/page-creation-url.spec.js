/**
 * End-to-end test for page creation URL update.
 *
 * This test verifies that when a new page is created, the URL updates
 * to reflect the new page's ID.
 *
 * Run with:
 *   npx playwright test page-creation-url.spec.js --headed
 *
 * To test with a different account:
 *   TEST_EMAIL=you@example.com TEST_PASSWORD=yourpass npx playwright test page-creation-url.spec.js --headed
 */

import { test, expect } from "@playwright/test";

const BASE_URL = process.env.TEST_BASE_URL || "http://localhost:9800";
const TEST_EMAIL = process.env.TEST_EMAIL || "dev@localhost";
const TEST_PASSWORD = process.env.TEST_PASSWORD || "dev";

test.describe("Page Creation URL Update", () => {
  test("URL should update when creating a new page", async ({ page }) => {
    console.log(`\n🔧 Logging in as: ${TEST_EMAIL}`);
    await page.goto(`${BASE_URL}/login`);
    await page.waitForSelector("#login-email", { timeout: 10000 });
    await page.fill("#login-email", TEST_EMAIL);
    await page.fill("#login-password", TEST_PASSWORD);
    await page.click('button[type="submit"]');

    await page.waitForSelector("#editor", { timeout: 20000 });
    await page.waitForSelector(".cm-content", { timeout: 10000 });
    console.log("✅ Logged in");

    const initialUrl = page.url();
    const initialMatch = initialUrl.match(/\/pages\/([^/]+)/);
    const initialPageId = initialMatch ? initialMatch[1] : null;
    console.log(`📍 Initial page ID: ${initialPageId}`);

    const newPageBtn = page.locator(".sidebar-new-page-btn").first();
    await newPageBtn.click();

    const newPageTitle = `URL Test Page ${Date.now()}`;
    const modal = page.locator(".modal");
    await modal.waitFor({ state: "visible", timeout: 5000 });
    console.log("📝 Filling in page title...");
    await page.locator("#page-title-input").fill(newPageTitle);
    await page.locator(".modal-btn-primary").click();

    await page.waitForSelector(".sidebar-item.active", { timeout: 10000 });
    await page.waitForSelector(".cm-content", { timeout: 10000 });
    await page.waitForTimeout(2000);
    console.log(`✅ Created page: ${newPageTitle}`);

    const newUrl = page.url();
    const newMatch = newUrl.match(/\/pages\/([^/]+)/);
    const newPageId = newMatch ? newMatch[1] : null;
    console.log(`📍 New URL page ID: ${newPageId}`);
    console.log(`📍 Initial: ${initialPageId}, New: ${newPageId}`);

    expect(newPageId).not.toBeNull();
    expect(newPageId).not.toBe(initialPageId);
    console.log("✅ URL updated correctly to new page ID");
  });
});
