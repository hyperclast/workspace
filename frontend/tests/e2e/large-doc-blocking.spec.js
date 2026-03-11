/**
 * Diagnostic test for main-thread blocking during large page navigation.
 *
 * Run with:
 *   cd frontend && npx playwright test large-doc-blocking.spec.js --headed
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

test.describe("Large document main-thread blocking", () => {
  test("find and diagnose the largest page", async ({ page }) => {
    test.setTimeout(300_000);
    await login(page);

    // First, find all pages and their sizes by fetching projects with details
    const projectsData = await page.evaluate(async () => {
      const resp = await fetch("/api/v1/projects/?details=full", { credentials: "same-origin" });
      return resp.json();
    });

    // Find the largest page
    let largestPage = null;
    let largestSize = 0;
    for (const project of projectsData) {
      for (const pg of project.pages || []) {
        // Fetch each page to get content size
        const pageData = await page.evaluate(async (id) => {
          const resp = await fetch(`/api/v1/pages/${id}/`, { credentials: "same-origin" });
          return resp.json();
        }, pg.external_id);

        const size = pageData.details?.content?.length || 0;
        if (size > largestSize) {
          largestSize = size;
          largestPage = { ...pg, contentSize: size };
        }
      }
    }

    if (!largestPage || largestSize < 100_000) {
      console.log(`Largest page is only ${largestSize} bytes — skipping`);
      test.skip(true, "No large pages found (need > 100KB)");
      return;
    }

    console.log(
      `Largest page: "${largestPage.title}" — ` +
        `${(largestSize / 1024 / 1024).toFixed(2)} MB (${largestSize} bytes)`
    );

    // Now navigate to a different page first so the large page isn't active
    const otherPage = projectsData
      .flatMap((p) => p.pages || [])
      .find((p) => p.external_id !== largestPage.external_id);

    if (otherPage) {
      // Click on a small page first
      const smallItem = page.locator(`.sidebar-item .page-title:text("${otherPage.title}")`);
      if ((await smallItem.count()) > 0) {
        await smallItem.first().click();
        await page.waitForTimeout(2000);
      }
    }

    // Inject rAF tracker
    await page.evaluate(() => {
      window.__rafTimes = [];
      window.__rafRunning = true;
      function track() {
        window.__rafTimes.push(Date.now());
        if (window.__rafRunning) requestAnimationFrame(track);
      }
      requestAnimationFrame(track);
    });

    // Collect console logs
    const logs = [];
    const t0 = Date.now();
    page.on("console", (msg) => {
      const text = msg.text();
      if (
        text.includes("[Nav]") ||
        text.includes("[Collab]") ||
        text.includes("editor_init") ||
        text.includes("page_load") ||
        text.includes("collab_setup") ||
        text.includes("ws_sync") ||
        text.includes("editor_upgrade") ||
        text.includes("superseded")
      ) {
        logs.push({ time: Date.now() - t0, text: text.substring(0, 300) });
      }
    });

    // Click the large page
    console.log(`Clicking "${largestPage.title}"...`);
    const largeSidebarItem = page.locator(`.sidebar-item .page-title:text("${largestPage.title}")`);

    if ((await largeSidebarItem.count()) === 0) {
      // The page might be in a collapsed project — expand all projects
      const projectHeaders = page.locator(".sidebar-project-header");
      const headerCount = await projectHeaders.count();
      for (let i = 0; i < headerCount; i++) {
        await projectHeaders.nth(i).click();
        await page.waitForTimeout(200);
      }
    }

    await largeSidebarItem.first().click();

    // Wait for load
    await page.waitForTimeout(15000);

    // Stop rAF tracker
    await page.evaluate(() => {
      window.__rafRunning = false;
    });

    // Analyze rAF gaps
    const rafTimes = await page.evaluate(() => window.__rafTimes);
    const gaps = [];
    for (let i = 1; i < rafTimes.length; i++) {
      const gap = rafTimes[i] - rafTimes[i - 1];
      if (gap > 100) {
        gaps.push({ at: rafTimes[i] - rafTimes[0], gap });
      }
    }

    const editorDocLen = await page.evaluate(() => window.editorView?.state?.doc?.length || 0);

    console.log(`\n=== BLOCKING ANALYSIS ===`);
    console.log(`Page: "${largestPage.title}" — ${(largestSize / 1024 / 1024).toFixed(2)} MB`);
    console.log(
      `Editor document length: ${editorDocLen} chars (${(editorDocLen / 1024 / 1024).toFixed(
        2
      )} MB)`
    );
    console.log(`\nMain-thread blocks > 100ms:`);
    if (gaps.length === 0) {
      console.log("  (none)");
    }
    for (const g of gaps) {
      console.log(`  at t+${g.at}ms: BLOCKED for ${g.gap}ms`);
    }
    const totalBlocked = gaps.reduce((sum, g) => sum + g.gap, 0);
    console.log(`Total blocked time: ${totalBlocked}ms`);

    console.log(`\nTimeline:`);
    for (const log of logs) {
      console.log(`  [t+${log.time}ms] ${log.text}`);
    }
  });

  test("click second page during large page load", async ({ page }) => {
    test.setTimeout(300_000);
    await login(page);

    // Find the largest page
    const projectsData = await page.evaluate(async () => {
      const resp = await fetch("/api/v1/projects/?details=full", {
        credentials: "same-origin",
      });
      return resp.json();
    });

    let largestPage = null;
    let largestSize = 0;
    const allPages = [];
    for (const project of projectsData) {
      for (const pg of project.pages || []) {
        allPages.push(pg);
        const pageData = await page.evaluate(async (id) => {
          const resp = await fetch(`/api/v1/pages/${id}/`, {
            credentials: "same-origin",
          });
          return resp.json();
        }, pg.external_id);
        const size = pageData.details?.content?.length || 0;
        if (size > largestSize) {
          largestSize = size;
          largestPage = { ...pg, contentSize: size };
        }
      }
    }

    if (!largestPage || largestSize < 100_000) {
      test.skip(true, "No large pages found");
      return;
    }

    // Find a small page that's different from the large page
    const smallPage = allPages.find((p) => p.external_id !== largestPage.external_id);
    if (!smallPage) {
      test.skip(true, "Need at least two pages");
      return;
    }

    console.log(
      `Large page: "${largestPage.title}" (${(largestSize / 1024 / 1024).toFixed(2)} MB)`
    );
    console.log(`Small page: "${smallPage.title}"`);

    // Make sure we're on a page that's neither large nor small target
    await page.waitForTimeout(1000);

    // Collect nav logs
    const navLogs = [];
    const t0 = Date.now();
    page.on("console", (msg) => {
      const text = msg.text();
      if (text.includes("[Nav]") || text.includes("[Collab]") || text.includes("superseded")) {
        navLogs.push({ time: Date.now() - t0, text: text.substring(0, 200) });
      }
    });

    // Expand all projects to make pages visible
    const projectHeaders = page.locator(".sidebar-project-header");
    const headerCount = await projectHeaders.count();
    for (let i = 0; i < headerCount; i++) {
      await projectHeaders.nth(i).click();
      await page.waitForTimeout(200);
    }

    // Click the large page
    console.log(`Step 1: Click large page "${largestPage.title}"...`);
    const largeSidebarItem = page
      .locator(`.sidebar-item .page-title:text("${largestPage.title}")`)
      .first();
    await largeSidebarItem.click();

    // Wait for the blocking to start.  The REST fetch is fast, then
    // initializeEditor runs (fast with fix), then collab sync starts
    // and Y.applyUpdate may block.
    await page.waitForTimeout(3000);

    // Click the small page
    console.log(`Step 2: Click small page "${smallPage.title}" at t+${Date.now() - t0}ms...`);
    const smallSidebarItem = page
      .locator(`.sidebar-item .page-title:text("${smallPage.title}")`)
      .first();
    await smallSidebarItem.click();

    // Wait for the small page to load
    await page.waitForFunction(
      (title) => {
        const input = document.getElementById("note-title-input");
        return input && input.value === title;
      },
      smallPage.title,
      { timeout: 120000 }
    );

    await page.waitForTimeout(3000);

    const loadedTitle = await page.locator("#note-title-input").inputValue();
    const totalTime = Date.now() - t0;

    console.log(`\n=== RESULTS (${totalTime}ms) ===`);
    console.log(`  Expected: "${smallPage.title}"`);
    console.log(`  Got:      "${loadedTitle}"`);
    console.log(`  Nav logs:`);
    for (const log of navLogs) {
      console.log(`    [t+${log.time}ms] ${log.text}`);
    }

    expect(loadedTitle).toBe(smallPage.title);
  });
});
