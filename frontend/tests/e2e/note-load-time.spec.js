/**
 * End-to-end test for measuring page content load time.
 *
 * This test measures how long it takes from page load to content appearing
 * in the editor. The goal is to catch performance regressions.
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

// Performance thresholds — configurable via env vars for slow environments.
// Override in .env-e2e or export directly before running tests.
const MAX_ACCEPTABLE_LOAD_TIME_MS = parseInt(process.env.E2E_MAX_LOAD_TIME_MS || "3000");
const WARNING_LOAD_TIME_MS = parseInt(process.env.E2E_WARNING_LOAD_TIME_MS || "1000");

const TEST_EMAIL = process.env.TEST_EMAIL || "dev@localhost";
const TEST_PASSWORD = process.env.TEST_PASSWORD || "dev";

/**
 * Helper: Login and wait for editor
 */
async function loginAndWait(page) {
  await page.goto(`${BASE_URL}/login`);
  await page.waitForSelector("#login-email", { timeout: 10000 });
  await page.fill("#login-email", TEST_EMAIL);
  await page.fill("#login-password", TEST_PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForSelector("#editor", { timeout: 15000 });
  await page.waitForSelector(".cm-content", { timeout: 10000 });
}

/**
 * Helper: Create a page with content via the REST API.
 * This is more reliable than typing into the editor and waiting for CRDT sync.
 */
async function createPageWithContent(page, title, content) {
  return await page.evaluate(
    async ({ title, content }) => {
      const csrfToken = document.cookie
        .split("; ")
        .find((row) => row.startsWith("csrftoken="))
        ?.split("=")[1];

      const projectsRes = await fetch("/api/v1/projects/");
      const projects = await projectsRes.json();
      if (!projects.length) throw new Error("No projects available");

      const res = await fetch("/api/v1/pages/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify({
          project_id: projects[0].external_id,
          title,
          details: { content, filetype: "txt", schema_version: 1 },
        }),
      });

      if (!res.ok) {
        const err = await res.text();
        throw new Error(`Failed to create page: ${err}`);
      }

      return await res.json();
    },
    { title, content }
  );
}

test.describe("Page Content Load Time", () => {
  const TEST_CONTENT = `Load time test content ${Date.now()}`;
  let testPageId = "";

  test.beforeAll(async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();

    await loginAndWait(page);

    // Create a test page with content via the API (guarantees persistence)
    const created = await createPageWithContent(page, `Load Time Test ${Date.now()}`, TEST_CONTENT);
    testPageId = created.external_id;

    console.log(`\n🔧 Setup: Created test content on page ${testPageId}`);
    await context.close();
  });

  test("content should appear within acceptable time (hard reload)", async ({ page }) => {
    console.log(`\n🔧 Logging in as: ${TEST_EMAIL}`);

    await loginAndWait(page);
    console.log("✅ Logged in");

    // Navigate to the test page and verify content is present
    await page.goto(`${BASE_URL}/pages/${testPageId}/`);
    await page.waitForSelector(".cm-content", { timeout: 10000 });

    await page.waitForFunction(
      (expected) => {
        const content = document.querySelector(".cm-content");
        return content && content.textContent.includes(expected);
      },
      TEST_CONTENT,
      { timeout: 15000 }
    );
    console.log("✅ Initial content loaded");

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

    // Wait for editor to render after reload (session may need to re-establish)
    await page.waitForSelector(".cm-content", { timeout: 15000 });

    // Verify we're still on the correct page (not redirected to login)
    const currentUrl = page.url();
    expect(currentUrl).toContain(testPageId);

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
    await loginAndWait(page);

    await page.goto(`${BASE_URL}/pages/${testPageId}/`);
    await page.waitForSelector(".cm-content", { timeout: 10000 });

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
      console.log(`   Content loaded: ${contentVisibleTime}ms`);
      if (editorVisibleTime) {
        console.log(
          `   ⏱️  Time from editor visible to content: ~${contentVisibleTime - editorVisibleTime}ms`
        );
      }
    } else {
      console.error("   ❌ Content never appeared!");
    }

    expect(contentVisibleTime).not.toBeNull();
    expect(contentVisibleTime).toBeLessThan(MAX_ACCEPTABLE_LOAD_TIME_MS);
  });
});
