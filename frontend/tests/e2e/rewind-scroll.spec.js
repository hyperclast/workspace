/**
 * E2E test for scroll-to-first-diff behavior in rewind viewer.
 *
 * Creates a page with enough content that the first diff line is below the fold,
 * then verifies that both formatted and plain diff modes auto-scroll to it.
 *
 * Strategy: page.reload() forces a WebSocket disconnect, which triggers
 * is_session_end=True and bypasses the 60-second minimum rewind interval.
 * This reliably creates separate rewind entries.
 *
 * Run with:
 *   npx playwright test rewind-scroll.spec.js --headed
 */

import { test, expect } from "@playwright/test";
import { dismissSocratesPanel } from "./helpers.js";

const BASE_URL = process.env.TEST_BASE_URL || "http://localhost:9800";
const TEST_EMAIL = process.env.TEST_EMAIL || "dev@localhost";
const TEST_PASSWORD = process.env.TEST_PASSWORD || "dev";

/** Generate N lines of filler text. */
function makeLines(n) {
  return Array.from(
    { length: n },
    (_, i) => `Line ${i + 1}: Lorem ipsum dolor sit amet, consectetur adipiscing elit.`
  ).join("\n");
}

/** Wait for editor + collab to be ready after a page load or reload. */
async function waitForEditorReady(page) {
  await page.waitForSelector("#editor", { timeout: 20000 });
  await page.waitForSelector(".cm-content", { timeout: 10000 });
  await dismissSocratesPanel(page);
  await page.waitForFunction(() => window.isCollabSynced?.() === true, { timeout: 15000 });
}

test.describe("Rewind Scroll to First Diff", () => {
  test.setTimeout(180000);

  test("scrolls to first changed line when diff starts below the fold", async ({ page }) => {
    // ---- Login ----
    await page.goto(`${BASE_URL}/login`);
    await page.waitForSelector("#login-email", { timeout: 10000 });
    await page.fill("#login-email", TEST_EMAIL);
    await page.fill("#login-password", TEST_PASSWORD);
    await page.click('button[type="submit"]');
    await waitForEditorReady(page);

    // ---- Create a fresh page ----
    const pageTitle = `Scroll Test ${Date.now()}`;
    const newPageBtn = page.locator(".sidebar-new-page-btn").first();
    await newPageBtn.click();

    const modal = page.locator(".modal");
    await modal.waitFor({ state: "visible", timeout: 5000 });
    await page.locator("#page-title-input").fill(pageTitle);
    await page.locator(".modal-btn-primary").click();
    await page.waitForSelector(".sidebar-item.active", { timeout: 10000 });
    await page.waitForSelector(".cm-content", { timeout: 10000 });

    await page.evaluate(async (title) => {
      for (let i = 0; i < 20; i++) {
        if (window.currentPage?.title === title) return;
        await new Promise((r) => setTimeout(r, 250));
      }
    }, pageTitle);
    await page.waitForFunction(() => window.isCollabSynced?.() === true, { timeout: 15000 });

    // ---- Insert 50 lines of initial content (fast, via dispatch) ----
    const initialContent = makeLines(50);
    await page.evaluate((content) => {
      const view = window.editorView;
      if (view) {
        view.dispatch({
          changes: { from: 0, to: view.state.doc.length, insert: content },
        });
      }
    }, initialContent);
    await page.waitForFunction(() => window.isCollabSynced?.() === true, { timeout: 15000 });

    // ---- Force rewind v1: reload triggers disconnect → is_session_end=True ----
    await page.reload();
    await waitForEditorReady(page);
    // Give the background task time to create the rewind (0.5s delay + processing)
    await page.waitForTimeout(5000);

    // Verify v1 exists
    const rewindTab = page.locator('button:has-text("Rewind"), .sidebar-tab:has-text("Rewind")');
    await rewindTab.click();
    await expect(page.locator(".rewind-entry").first()).toBeVisible({ timeout: 30000 });

    const v1Count = await page.locator(".rewind-entry").count();
    console.log(`[Setup] After v1 reload: ${v1Count} rewind entries`);

    // ---- Exit rewind, add 5 lines at the bottom ----
    const exitBtn = page.locator("#rewind-exit-btn");
    if (await exitBtn.isVisible().catch(() => false)) {
      await exitBtn.click();
    }
    // Wait for editor to be visible again
    await page.waitForSelector(".cm-content", { timeout: 10000 });

    await page.evaluate(() => {
      const view = window.editorView;
      if (view) {
        const end = view.state.doc.length;
        const added = "\nAdded line A\nAdded line B\nAdded line C\nAdded line D\nAdded line E";
        view.dispatch({ changes: { from: end, insert: added } });
      }
    });
    await page.waitForFunction(() => window.isCollabSynced?.() === true, { timeout: 15000 });

    // ---- Force rewind v2: reload again ----
    // Retry loop: sometimes the backend needs an extra cycle to create the entry
    let v2Count = 0;
    for (let attempt = 0; attempt < 3; attempt++) {
      await page.reload();
      await waitForEditorReady(page);
      await page.waitForTimeout(5000);

      // Open Rewind tab and check entry count
      await rewindTab.click();
      try {
        await page.waitForFunction(() => document.querySelectorAll(".rewind-entry").length >= 2, {
          timeout: 15000,
        });
        v2Count = await page.locator(".rewind-entry").count();
        console.log(`[Setup] Attempt ${attempt + 1}: ${v2Count} rewind entries — success`);
        break;
      } catch {
        v2Count = await page.locator(".rewind-entry").count();
        console.log(`[Setup] Attempt ${attempt + 1}: only ${v2Count} entries, retrying...`);
        // Exit rewind before retry so we can add more content
        const retryExit = page.locator("#rewind-exit-btn");
        if (await retryExit.isVisible().catch(() => false)) {
          await retryExit.click();
        }
        await page.waitForSelector(".cm-content", { timeout: 10000 });
        // Add a small edit to ensure content changed
        await page.evaluate((n) => {
          const view = window.editorView;
          if (view) {
            const end = view.state.doc.length;
            view.dispatch({ changes: { from: end, insert: `\nRetry line ${n}` } });
          }
        }, attempt);
        await page.waitForFunction(() => window.isCollabSynced?.() === true, { timeout: 15000 });
      }
    }
    expect(v2Count, "Should have at least 2 rewind entries").toBeGreaterThanOrEqual(2);

    // ---- Click the NEWEST entry (first in list) ----
    // Diffs v2 (55 lines) against v1 (50 lines):
    // 50 unchanged lines + 5 added at bottom. First change is ~line 51.
    // Small settle delay so Svelte event handlers are fully attached
    await page.waitForTimeout(500);
    const firstEntry = page.locator(".rewind-entry").first();
    await firstEntry.click();
    console.log("[Click] Clicked first rewind entry");

    // Wait for the rewind viewer to become visible (enterRewindMode hides editor)
    await page.waitForFunction(
      () => {
        const viewer = document.getElementById("rewind-viewer");
        return viewer && viewer.style.display === "flex";
      },
      { timeout: 15000 }
    );
    console.log("[Click] Rewind viewer is visible");

    // Wait for the formatted diff CM editor to appear
    await page.waitForSelector(".rewind-diff-cm .cm-editor", { timeout: 30000 });

    // ---- ASSERT: formatted mode scrolled to first diff ----
    // Wait for scroll animation to fully complete (~500ms), then check final position.
    await page.waitForFunction(
      () => {
        const container = document.querySelector(".rewind-diff");
        if (!container || container.scrollTop === 0) return false;
        // Wait until scroll has settled (no change over 200ms)
        if (!window._lastScrollTop) window._lastScrollTop = -1;
        if (!window._lastScrollTime) window._lastScrollTime = 0;
        if (container.scrollTop !== window._lastScrollTop) {
          window._lastScrollTop = container.scrollTop;
          window._lastScrollTime = Date.now();
          return false;
        }
        return Date.now() - window._lastScrollTime > 200;
      },
      { timeout: 10000, polling: 100 }
    );

    const formattedDebug = await page.evaluate(() => {
      const container = document.querySelector(".rewind-diff");
      const line = container?.querySelector(".rewind-cm-line-added");
      const cRect = container?.getBoundingClientRect();
      const lRect = line?.getBoundingClientRect();
      return {
        scrollTop: container?.scrollTop ?? -1,
        scrollHeight: container?.scrollHeight ?? -1,
        clientHeight: container?.clientHeight ?? -1,
        lineFound: !!line,
        lineTop: lRect?.top ?? -1,
        lineBottom: lRect?.bottom ?? -1,
        containerTop: cRect?.top ?? -1,
        containerBottom: cRect?.bottom ?? -1,
        lineVisible: lRect && cRect ? lRect.top < cRect.bottom && lRect.bottom > cRect.top : false,
      };
    });

    console.log("[Formatted mode — after scroll settled]", JSON.stringify(formattedDebug));
    expect(
      formattedDebug.scrollTop,
      "Formatted: scroll container should have scrolled down"
    ).toBeGreaterThan(0);
    expect(
      formattedDebug.lineVisible,
      "Formatted: first added line should be visible in viewport"
    ).toBe(true);

    // ---- Switch to plain mode ----
    await page.locator("#rewind-plain-btn").click();
    await page.waitForSelector(".rewind-diff-line.added", { timeout: 10000 });

    // ---- ASSERT: plain mode scrolled to first diff ----
    // Wait for scroll to settle
    await page.evaluate(() => {
      window._lastScrollTop = -1;
      window._lastScrollTime = 0;
    });
    await page.waitForFunction(
      () => {
        const container = document.querySelector(".rewind-diff");
        if (!container || container.scrollTop === 0) return false;
        if (container.scrollTop !== window._lastScrollTop) {
          window._lastScrollTop = container.scrollTop;
          window._lastScrollTime = Date.now();
          return false;
        }
        return Date.now() - window._lastScrollTime > 200;
      },
      { timeout: 10000, polling: 100 }
    );

    const plainDebug = await page.evaluate(() => {
      const container = document.querySelector(".rewind-diff");
      const line = container?.querySelector(".rewind-diff-line.added");
      const cRect = container?.getBoundingClientRect();
      const lRect = line?.getBoundingClientRect();
      return {
        scrollTop: container?.scrollTop ?? -1,
        scrollHeight: container?.scrollHeight ?? -1,
        clientHeight: container?.clientHeight ?? -1,
        lineFound: !!line,
        lineTop: lRect?.top ?? -1,
        lineBottom: lRect?.bottom ?? -1,
        containerTop: cRect?.top ?? -1,
        containerBottom: cRect?.bottom ?? -1,
        lineVisible: lRect && cRect ? lRect.top < cRect.bottom && lRect.bottom > cRect.top : false,
      };
    });

    console.log("[Plain mode — after scroll settled]", JSON.stringify(plainDebug));
    expect(
      plainDebug.scrollTop,
      "Plain: scroll container should have scrolled down"
    ).toBeGreaterThan(0);
    expect(plainDebug.lineVisible, "Plain: first added line should be visible in viewport").toBe(
      true
    );

    // ---- Cleanup: exit rewind ----
    const exitButton = page.locator("#rewind-exit-btn");
    if (await exitButton.isVisible().catch(() => false)) {
      await exitButton.click();
    }
    await page.waitForSelector(".cm-content", { timeout: 5000 });
  });
});
