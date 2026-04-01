/**
 * E2E test: clicking a second page in the sidenav while the first is still
 * loading should abort the first fetch and load the second.
 *
 * Tests both network-level delays (slow API) and heavy page rendering
 * (large documents that block the main thread during CodeMirror init).
 *
 * Run with:
 *   cd frontend && npx playwright test non-blocking-navigation.spec.js --headed
 */

import { test, expect } from "@playwright/test";

const BASE_URL = process.env.TEST_BASE_URL || "http://localhost:9800";
const TEST_EMAIL = process.env.TEST_EMAIL || "dev@localhost";
const TEST_PASSWORD = process.env.TEST_PASSWORD || "dev";

async function login(page) {
  await page.goto(`${BASE_URL}/login`);
  await page.waitForSelector("#login-email", { timeout: 10000 });
  await page.fill("#login-email", TEST_EMAIL);
  await page.fill("#login-password", TEST_PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForSelector("#editor", { timeout: 20000 });
  await page.waitForSelector(".cm-content", { timeout: 10000 });
}

function getPageIdFromUrl(url) {
  const match = url.match(/\/pages\/([^/]+)/);
  return match ? match[1] : null;
}

/**
 * Ensure at least `needed` non-active sidebar items exist, creating pages
 * if necessary. Returns an array of { id, title, locator } for each
 * non-active item, snapshotted *before* any clicks so positions are stable.
 */
async function ensureOtherPages(page, needed) {
  const otherItems = page.locator(`.sidebar-item:not(.active)`);
  const otherCount = await otherItems.count();

  if (otherCount < needed) {
    for (let i = otherCount; i < needed; i++) {
      const newPageBtn = page.locator(".sidebar-new-page-btn").first();
      await newPageBtn.click();
      const modal = page.locator(".modal");
      await modal.waitFor({ state: "visible", timeout: 5000 });
      await page.locator("#page-title-input").fill(`Nav Test ${Date.now()}-${i}`);
      await page.locator(".modal-btn-primary").click();
      await page.waitForSelector(".cm-content", { timeout: 10000 });
    }
  }

  // Snapshot page IDs and titles from the non-active items *now*, before any
  // clicks change the active state and shift positional locators.
  const items = page.locator(`.sidebar-item:not(.active)`);
  const count = await items.count();
  expect(count).toBeGreaterThanOrEqual(needed);

  const result = [];
  for (let i = 0; i < needed; i++) {
    const item = items.nth(i);
    const id = await item.getAttribute("data-page-id");
    const title = await item.locator(".page-title").textContent();
    // Build a locator by data-page-id — this selector is stable across re-renders
    result.push({
      id,
      title,
      locator: page.locator(`.sidebar-item[data-page-id="${id}"]`),
    });
  }
  return result;
}

test.describe("Non-blocking page navigation", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!TEST_EMAIL || !TEST_PASSWORD, "TEST_EMAIL and TEST_PASSWORD required");
  });

  test("clicking a second page while the first fetch is slow aborts and loads the second", async ({
    page,
  }) => {
    await login(page);

    const initialPageId = getPageIdFromUrl(page.url());

    const others = await ensureOtherPages(page, 2);
    const first = others[0];
    const second = others[1];

    // Intercept page fetch API to make the FIRST click slow
    let interceptCount = 0;

    await page.route("**/api/v1/pages/*/", async (route) => {
      interceptCount++;
      if (interceptCount === 1) {
        // First page fetch: delay 5 seconds to simulate slow load
        try {
          await new Promise((resolve) => setTimeout(resolve, 5000));
          await route.continue();
        } catch {
          // aborted
        }
      } else {
        await route.continue();
      }
    });

    // Click the first non-active page (this will be slow)
    await first.locator.click();
    await page.waitForTimeout(500);

    // Verify loading state
    const titleInput = page.locator("#note-title-input");
    const titleValue = await titleInput.inputValue();
    console.log(`Title during load: "${titleValue}"`);

    // Click the second page — should abort the first
    await second.locator.click();

    // The second page should load successfully
    await page.waitForSelector(".cm-content", { timeout: 10000 });

    const finalPageId = getPageIdFromUrl(page.url());
    expect(finalPageId).not.toBe(initialPageId);
    expect(finalPageId).toBe(second.id);

    await expect(page.locator(".cm-content")).toBeVisible();

    await page.unroute("**/api/v1/pages/*/");
  });

  test("clicking another page during large document rendering aborts and loads the second", async ({
    page,
  }) => {
    test.setTimeout(120_000); // 2 minute timeout for large doc rendering

    await login(page);

    const others = await ensureOtherPages(page, 2);
    const first = others[0];
    const second = others[1];

    // Generate a large document (5MB of markdown content).
    // This will cause initializeEditor to block the main thread
    // while building the CodeMirror Text rope and rendering.
    const lineContent = "This is a line of text for the large document test. ".repeat(5) + "\n";
    const targetSize = 5 * 1024 * 1024; // 5MB
    const lineCount = Math.ceil(targetSize / lineContent.length);
    const largeContent = lineContent.repeat(lineCount);

    console.log(
      `Generated large content: ${(largeContent.length / 1024 / 1024).toFixed(1)} MB, ` +
        `${largeContent.split("\n").length} lines`
    );

    // Intercept ONLY the first page fetch and return a massive document
    let intercepted = false;

    await page.route("**/api/v1/pages/*/", async (route) => {
      if (!intercepted) {
        intercepted = true;

        // Let the real request go through to get the proper response shape,
        // then inject large content
        const response = await route.fetch();
        const body = await response.json();

        body.details = body.details || {};
        body.details.content = largeContent;
        body.details.filetype = "md";

        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(body),
        });
      } else {
        await route.continue();
      }
    });

    // Add instrumentation to measure editor init time
    await page.evaluate(() => {
      window.__editorInitLog = [];
      const origInitEditor = window.editorView?.constructor && document.getElementById("editor");
      // We'll measure from console logs instead
    });

    console.log("Clicking first page (will render 5MB document)...");
    const clickTime = Date.now();
    await first.locator.click();

    // Wait for the fetch to complete (route.fetch + fulfill is ~instant)
    // then the rAF yield fires, then initializeEditor blocks.
    // Give the blocking init a moment to start, then click the second page.
    // The 500ms wait should be enough for the fetch + yield but before
    // initializeEditor finishes (which should take several seconds for 5MB).
    await page.waitForTimeout(500);

    console.log(
      `Clicking second page after ${Date.now() - clickTime}ms (during large doc init)...`
    );
    await second.locator.click();

    // The second page should eventually load.
    // After the first page's init block ends, the queued click fires,
    // which calls openPage (aborting the signal), and then the post-init
    // yield in loadPage detects the abort and cleans up.
    await page.waitForSelector(".cm-content", { timeout: 60000 });

    // Give the second page time to fully load
    await page.waitForTimeout(2000);

    // Check what page we ended up on
    const loadedTitle = await page.locator("#note-title-input").inputValue();
    const totalTime = Date.now() - clickTime;

    console.log(`Expected: "${second.title}", Got: "${loadedTitle}"`);
    console.log(`Total navigation time: ${totalTime}ms`);

    // The second page should have loaded, not the large first page
    expect(loadedTitle).toBe(second.title);

    await page.unroute("**/api/v1/pages/*/");
  });

  test("clicking another page while a large page is loading end-to-end", async ({ page }) => {
    await login(page);

    const others = await ensureOtherPages(page, 2);
    const first = others[0];
    const second = others[1];

    console.log(`Will click: "${first.title}" then quickly "${second.title}"`);

    // Add instrumentation to track what happens in the browser
    await page.evaluate(() => {
      window.__navLog = [];
      const origOpen = window.openPage;
      if (origOpen) {
        window.openPage = function (...args) {
          window.__navLog.push({ event: "openPage", pageId: args[0], time: Date.now() });
          return origOpen.apply(this, args);
        };
      }
    });

    // Click the first page
    console.log("Clicking first page...");
    await first.locator.click();

    // Wait a short time, then click the second page
    // This simulates the user clicking quickly while the first page is loading
    // (Yjs sync in progress, or collab upgrade happening)
    await page.waitForTimeout(100);
    console.log("Clicking second page...");
    await second.locator.click();

    // Wait for the page to settle
    await page.waitForSelector(".cm-content", { timeout: 30000 });

    // Give collab upgrade time to complete (this is the blocking part)
    await page.waitForTimeout(3000);

    // Check what page we ended up on
    const loadedTitle = await page.locator("#note-title-input").inputValue();
    const navLog = await page.evaluate(() => window.__navLog);
    const currentUrl = page.url();
    const currentPageId = getPageIdFromUrl(currentUrl);

    console.log(`Navigation log:`, JSON.stringify(navLog, null, 2));
    console.log(`Expected: "${second.title}", Got: "${loadedTitle}"`);
    console.log(`Final URL page ID: ${currentPageId}`);

    // Check if the second page ended up loading
    // This is the assertion that may fail — revealing the bug
    expect(loadedTitle).toBe(second.title);
  });

  test("sidenav remains clickable while a page is loading", async ({ page }) => {
    await login(page);

    const others = await ensureOtherPages(page, 1);

    // Set up a very slow page fetch
    await page.route("**/api/v1/pages/*/", async (route) => {
      try {
        await new Promise((resolve) => setTimeout(resolve, 10000));
        await route.continue();
      } catch {
        // aborted
      }
    });

    // Click a page — it will be stuck loading
    await others[0].locator.click();
    await page.waitForTimeout(500);

    // Verify the sidenav items are still clickable (not disabled, no pointer-events: none)
    const sidenavItems = page.locator(".sidebar-item");
    const itemCount = await sidenavItems.count();

    for (let i = 0; i < Math.min(itemCount, 5); i++) {
      const item = sidenavItems.nth(i);
      const isVisible = await item.isVisible();
      const isEnabled = await item.isEnabled();
      const pointerEvents = await item.evaluate((el) => window.getComputedStyle(el).pointerEvents);

      console.log(
        `Item ${i}: visible=${isVisible}, enabled=${isEnabled}, pointer-events=${pointerEvents}`
      );
      expect(isVisible).toBe(true);
      expect(pointerEvents).not.toBe("none");
    }

    // Verify we can actually click another item and it responds
    const clickReceived = await others[0].locator.evaluate((el) => {
      return new Promise((resolve) => {
        el.addEventListener("click", () => resolve(true), { once: true });
        el.click();
      });
    });
    expect(clickReceived).toBe(true);

    await page.unroute("**/api/v1/pages/*/");
  });
});
