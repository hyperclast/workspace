/**
 * End-to-end test for measuring page content load time.
 *
 * This test measures how long it takes from page load to content appearing
 * in the editor via CRDT sync. The goal is to catch performance regressions.
 *
 * Run with:
 *   npm run test:load-time
 *
 * Or for headed mode (to see the browser):
 *   npm run test:load-time -- --headed
 *
 * To test with a different account:
 *   TEST_EMAIL=you@example.com TEST_PASSWORD=yourpass npm run test:load-time -- --headed
 */

import { test, expect } from "@playwright/test";

const BASE_URL = process.env.TEST_BASE_URL || "http://localhost:9800";

const MAX_ACCEPTABLE_LOAD_TIME_MS = 3000;
const WARNING_LOAD_TIME_MS = 1000;

const TEST_EMAIL = process.env.TEST_EMAIL || "dev@localhost";
const TEST_PASSWORD = process.env.TEST_PASSWORD || "dev";

test.describe("Page Content Load Time", () => {
  const TEST_CONTENT = `Load time test content ${Date.now()}`;
  let testPageId = "";

  test.beforeAll(async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();

    await page.goto(`${BASE_URL}/login`);
    await page.waitForSelector("#login-email", { timeout: 10000 });
    await page.fill("#login-email", TEST_EMAIL);
    await page.fill("#login-password", TEST_PASSWORD);
    await page.click('button[type="submit"]');
    await page.waitForSelector("#editor", { timeout: 15000 });
    await page.waitForSelector(".cm-content", { timeout: 10000 });

    testPageId = await page.evaluate(() => {
      const match = window.location.pathname.match(/\/pages\/([^/]+)/);
      return match ? match[1] : window.currentPage?.external_id || "";
    });

    await page.click(".cm-content");
    await page.keyboard.type(TEST_CONTENT);
    await page.waitForTimeout(1500);

    console.log(`\n🔧 Setup: Created test content on page ${testPageId}`);
    await context.close();
  });

  test("content should appear within acceptable time (hard reload)", async ({ page }) => {
    console.log(`\n🔧 Logging in as: ${TEST_EMAIL}`);

    await page.goto(`${BASE_URL}/login`);
    await page.waitForSelector("#login-email", { timeout: 10000 });
    await page.fill("#login-email", TEST_EMAIL);
    await page.fill("#login-password", TEST_PASSWORD);
    await page.click('button[type="submit"]');
    await page.waitForSelector("#editor", { timeout: 15000 });
    await page.waitForSelector(".cm-content", { timeout: 10000 });
    console.log("✅ Logged in");

    if (testPageId) {
      await page.goto(`${BASE_URL}/pages/${testPageId}/`);
      await page.waitForSelector(".cm-content", { timeout: 10000 });
    }

    await page.waitForFunction(
      (expected) => {
        const content = document.querySelector(".cm-content");
        return content && content.textContent.includes(expected);
      },
      TEST_CONTENT,
      { timeout: 30000 }
    );
    console.log("✅ Initial content loaded via CRDT");

    const client = await page.context().newCDPSession(page);
    await client.send("Network.clearBrowserCache");

    await page.evaluate(async () => {
      if ("caches" in window) {
        const names = await caches.keys();
        await Promise.all(names.map((name) => caches.delete(name)));
      }
    });

    console.log("\n🔄 Performing HARD RELOAD (browser cache cleared)...");

    const startTime = Date.now();
    await page.reload({ waitUntil: "commit" });

    await page.waitForFunction(
      (expected) => {
        const content = document.querySelector(".cm-content");
        return content && content.textContent.includes(expected);
      },
      TEST_CONTENT,
      { timeout: 60000 }
    );

    const endTime = Date.now();
    const loadTimeMs = endTime - startTime;

    console.log(`\n📊 HARD RELOAD Load Time: ${loadTimeMs}ms (${(loadTimeMs / 1000).toFixed(2)}s)`);

    if (loadTimeMs > MAX_ACCEPTABLE_LOAD_TIME_MS) {
      console.error(`❌ Load time exceeds ${MAX_ACCEPTABLE_LOAD_TIME_MS}ms threshold!`);
    } else if (loadTimeMs > WARNING_LOAD_TIME_MS) {
      console.warn(`⚠️  Load time exceeds warning threshold of ${WARNING_LOAD_TIME_MS}ms`);
    } else {
      console.log(`✅ Load time is acceptable`);
    }

    expect(loadTimeMs).toBeLessThan(MAX_ACCEPTABLE_LOAD_TIME_MS);
  });

  test("measure detailed timing breakdown", async ({ page }) => {
    await page.goto(`${BASE_URL}/login`);
    await page.waitForSelector("#login-email", { timeout: 10000 });
    await page.fill("#login-email", TEST_EMAIL);
    await page.fill("#login-password", TEST_PASSWORD);
    await page.click('button[type="submit"]');
    await page.waitForSelector("#editor", { timeout: 15000 });

    if (testPageId) {
      await page.goto(`${BASE_URL}/pages/${testPageId}/`);
      await page.waitForSelector(".cm-content", { timeout: 10000 });
    }

    const client = await page.context().newCDPSession(page);
    await client.send("Network.clearBrowserCache");

    console.log("\n🔄 Navigating with cleared cache...");

    const startTime = Date.now();
    await page.reload({ waitUntil: "commit" });

    let editorVisibleTime = null;
    let contentVisibleTime = null;

    while (Date.now() - startTime < 60000) {
      const state = await page.evaluate((expected) => {
        const editor = document.querySelector(".cm-editor");
        const content = document.querySelector(".cm-content");
        const text = content?.textContent || "";
        return {
          editorExists: !!editor,
          contentExists: !!content,
          hasContent: text.includes(expected),
        };
      }, TEST_CONTENT);

      if (state.editorExists && !editorVisibleTime) {
        editorVisibleTime = Date.now() - startTime;
      }

      if (state.hasContent && !contentVisibleTime) {
        contentVisibleTime = Date.now() - startTime;
        break;
      }

      await page.waitForTimeout(50);
    }

    console.log("\n📊 Detailed Timing Breakdown:");
    console.log(`   Page navigation started: 0ms`);
    if (editorVisibleTime) {
      console.log(`   Editor visible: ${editorVisibleTime}ms`);
    }
    if (contentVisibleTime) {
      console.log(`   Content loaded via CRDT: ${contentVisibleTime}ms`);
      if (editorVisibleTime) {
        console.log(
          `   ⏱️  Time waiting for WebSocket/CRDT: ~${contentVisibleTime - editorVisibleTime}ms`
        );
      }
    } else {
      console.error("   ❌ Content never appeared!");
    }

    expect(contentVisibleTime).not.toBeNull();
    expect(contentVisibleTime).toBeLessThan(MAX_ACCEPTABLE_LOAD_TIME_MS);
  });
});
