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
import { clickToolbarButton } from "./helpers.js";

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

test.describe("Fold Persistence", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!TEST_EMAIL || !TEST_PASSWORD, "TEST_EMAIL and TEST_PASSWORD required");
  });

  test("fold state is restored after page reload", async ({ page }) => {
    await login(page);

    // Create a fresh page via API with known content.
    // A new page has no prior Yjs state, so collab sync will use details.content
    // as the initial document — REST and CRDT content will be identical.
    const testContent = [
      "# Section One",
      "",
      "First section content.",
      "More lines here.",
      "",
      "# Section Two",
      "",
      "Second section content.",
      "Additional lines.",
      "",
      "# Section Three",
      "",
      "Third section content.",
    ].join("\n");

    const newPage = await page.evaluate(
      async ({ content }) => {
        const csrfToken = document.cookie
          .split("; ")
          .find((c) => c.startsWith("csrftoken="))
          ?.split("=")[1];
        const projects = await (await fetch("/api/projects/")).json();
        const res = await fetch("/api/pages/", {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
          body: JSON.stringify({
            project_id: projects[0].external_id,
            title: `Fold Test ${Date.now()}`,
            details: { content, filetype: "md", schema_version: 1 },
          }),
        });
        return await res.json();
      },
      { content: testContent }
    );
    const pageId = newPage.external_id;
    console.log(`📍 Created test page: ${pageId}`);

    // Navigate to the new page and wait for collab sync
    await page.goto(`${BASE_URL}/pages/${pageId}/`);
    await page.waitForSelector(".cm-content", { timeout: 10000 });
    await page.waitForFunction(() => window.isCollabSynced?.() === true, { timeout: 15000 });
    await page.waitForFunction(
      () => document.querySelector(".cm-content")?.textContent.includes("Section One"),
      { timeout: 5000 }
    );

    // Fold all sections
    await clickToolbarButton(page, "Fold all sections", "Fold all");
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

    // Wait for editor to be ready and collab to sync
    await page.waitForSelector(".cm-content", { timeout: 10000 });
    await page.waitForFunction(() => window.isCollabSynced?.() === true, { timeout: 15000 });
    console.log("✅ Page reloaded and synced");

    // Wait for fold restoration (happens after collab upgrade)
    await page.waitForTimeout(1000);
    const foldsAfter = await page.locator(".cm-foldPlaceholder").count();
    console.log(`📁 Folds after reload: ${foldsAfter}`);

    expect(foldsAfter).toBe(foldsBefore);
    console.log("✅ Fold state restored after reload");
  });

  test("unfold all clears localStorage", async ({ page }) => {
    await login(page);

    // Create a fresh page with known content
    const newPage = await page.evaluate(async () => {
      const csrfToken = document.cookie
        .split("; ")
        .find((c) => c.startsWith("csrftoken="))
        ?.split("=")[1];
      const projects = await (await fetch("/api/projects/")).json();
      const res = await fetch("/api/pages/", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
        body: JSON.stringify({
          project_id: projects[0].external_id,
          title: `Unfold Test ${Date.now()}`,
          details: {
            content: "# Section One\n\nContent here.\n\n# Section Two\n\nMore content.",
            filetype: "md",
            schema_version: 1,
          },
        }),
      });
      return await res.json();
    });
    const pageId = newPage.external_id;

    // Navigate to the new page and wait for collab sync
    await page.goto(`${BASE_URL}/pages/${pageId}/`);
    await page.waitForSelector(".cm-content", { timeout: 10000 });
    await page.waitForFunction(() => window.isCollabSynced?.() === true, { timeout: 15000 });
    await page.waitForFunction(
      () => document.querySelector(".cm-content")?.textContent.includes("Section One"),
      { timeout: 5000 }
    );

    // Fold all (handles overflow menu)
    await clickToolbarButton(page, "Fold all sections", "Fold all");
    await page.waitForTimeout(300);

    // Verify localStorage has data
    let storage = await page.evaluate((pid) => {
      return localStorage.getItem(`page-folds-${pid}`);
    }, pageId);
    expect(storage).not.toBeNull();
    console.log(`📦 localStorage after fold: ${storage}`);

    // Unfold all (handles overflow menu)
    await clickToolbarButton(page, "Expand all sections", "Expand all");
    await page.waitForTimeout(300);

    // Verify localStorage is cleared
    storage = await page.evaluate((pid) => {
      return localStorage.getItem(`page-folds-${pid}`);
    }, pageId);
    expect(storage).toBeNull();
    console.log("✅ localStorage cleared after unfold all");
  });
});
