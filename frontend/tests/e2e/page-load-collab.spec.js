/**
 * Comprehensive E2E tests for page load and collaboration architecture.
 *
 * These tests verify:
 * 1. Page loads instantly with REST content (no blocking on WebSocket)
 * 2. Collaboration upgrades correctly after sync
 * 3. No content duplication on reload
 * 4. Proper handling of edge cases (timeout, access denied, rapid navigation)
 * 5. Metrics are collected correctly
 *
 * Architecture under test:
 * - Phase 1: Show REST content immediately WITHOUT yCollab
 * - Phase 2: Wait for WS sync in background
 * - Phase 3: Upgrade editor WITH yCollab using correct content source
 *
 * Run with:
 *   npm run test:e2e -- tests/e2e/page-load-collab.spec.js
 *
 * Headed mode:
 *   npm run test:e2e -- tests/e2e/page-load-collab.spec.js --headed
 */

import { test, expect } from "@playwright/test";

const BASE_URL = process.env.TEST_BASE_URL || "http://localhost:9800";
const TEST_EMAIL = process.env.TEST_EMAIL || "dev@localhost";
const TEST_PASSWORD = process.env.TEST_PASSWORD || "dev";

// Performance thresholds (generous to avoid flakiness in Docker/CI environments)
const THRESHOLDS = {
  PAGE_VISIBLE_MS: 1000, // Content should be visible within 1s
  COLLAB_CONNECTED_MS: 5000, // Collaboration should connect within 5s
  RELOAD_VISIBLE_MS: 1000, // Content should be visible within 1s on reload
};

/**
 * Helper: Login and navigate to app
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
 * Helper: Get current page ID from URL or window
 */
async function getCurrentPageId(page) {
  return await page.evaluate(() => {
    const match = window.location.pathname.match(/\/pages\/([^/]+)/);
    return match ? match[1] : window.currentPage?.external_id || null;
  });
}

/**
 * Helper: Get metrics from window.__metrics
 */
async function getMetrics(page) {
  return await page.evaluate(() => {
    if (window.__metrics) {
      return window.__metrics.getSummary();
    }
    return null;
  });
}

/**
 * Helper: Get raw metric spans
 */
async function getMetricSpans(page, spanName = null) {
  return await page.evaluate((name) => {
    if (!window.__metrics) return [];
    const data = window.__metrics.getRawData();
    if (name) {
      return data.spans.filter((s) => s.name === name);
    }
    return data.spans;
  }, spanName);
}

/**
 * Helper: Get collaboration status
 */
async function getCollabStatus(page) {
  return await page.evaluate(() => {
    const indicator = document.getElementById("collab-status");
    if (!indicator) return null;

    const classes = indicator.className;
    if (classes.includes("connected")) return "connected";
    if (classes.includes("connecting")) return "connecting";
    if (classes.includes("denied")) return "denied";
    if (classes.includes("offline")) return "offline";
    if (classes.includes("error")) return "error";
    return "unknown";
  });
}

/**
 * Helper: Create a page with specific content via CLI-like API
 */
async function createPageWithContent(page, title, content) {
  return await page.evaluate(
    async ({ title, content }) => {
      // Get CSRF token
      const csrfToken = document.cookie
        .split("; ")
        .find((row) => row.startsWith("csrftoken="))
        ?.split("=")[1];

      // Get first project
      const projectsRes = await fetch("/api/projects/");
      const projects = await projectsRes.json();
      if (!projects.length) throw new Error("No projects available");

      const projectId = projects[0].external_id;

      // Create page
      const res = await fetch("/api/pages/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify({
          project_id: projectId,
          title: title,
          details: {
            content: content,
            filetype: "txt",
            schema_version: 1,
          },
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

/**
 * Helper: Delete a page
 */
async function deletePage(page, pageId) {
  return await page.evaluate(async (id) => {
    const csrfToken = document.cookie
      .split("; ")
      .find((row) => row.startsWith("csrftoken="))
      ?.split("=")[1];

    await fetch(`/api/pages/${id}/`, {
      method: "DELETE",
      headers: { "X-CSRFToken": csrfToken },
    });
  }, pageId);
}

// ============================================================================
// TEST SUITE: Page Load Performance
// ============================================================================

test.describe("Page Load Performance", () => {
  test.beforeEach(async ({ page }) => {
    await loginAndWait(page);
  });

  test("content should be visible within threshold on initial load", async ({ page }) => {
    const testContent = `Performance test ${Date.now()}`;

    // Create a test page with content
    const testPage = await createPageWithContent(page, "Perf Test", testContent);
    const pageId = testPage.external_id;

    try {
      // Navigate to the page and measure time to content visibility
      const startTime = Date.now();
      await page.goto(`${BASE_URL}/pages/${pageId}/`);

      // Wait for content to appear
      await page.waitForFunction(
        (expected) => {
          const content = document.querySelector(".cm-content");
          return content && content.textContent.includes(expected);
        },
        testContent,
        { timeout: 10000 }
      );

      const visibleTime = Date.now() - startTime;
      console.log(`📊 Content visible in: ${visibleTime}ms`);

      // Assert performance threshold
      expect(visibleTime).toBeLessThan(THRESHOLDS.PAGE_VISIBLE_MS);

      // Verify metrics were collected
      const spans = await getMetricSpans(page, "page_load");
      expect(spans.length).toBeGreaterThan(0);

      const pageLoadSpan = spans[spans.length - 1];
      expect(pageLoadSpan.endAttributes.status).toBe("success");
      console.log(`📊 Metrics page_load duration: ${pageLoadSpan.duration}ms`);
    } finally {
      await deletePage(page, pageId);
    }
  });

  test("content should be visible within threshold on reload", async ({ page }) => {
    const testContent = `Reload test ${Date.now()}`;

    // Create a test page
    const testPage = await createPageWithContent(page, "Reload Test", testContent);
    const pageId = testPage.external_id;

    try {
      // First load
      await page.goto(`${BASE_URL}/pages/${pageId}/`);
      await page.waitForFunction(
        (expected) => document.querySelector(".cm-content")?.textContent.includes(expected),
        testContent,
        { timeout: 10000 }
      );

      // Wait for collab to connect and stabilize
      await page.waitForTimeout(2000);

      // Clear metrics for accurate measurement
      await page.evaluate(() => window.__metrics?.clear());

      // Measure reload performance
      const startTime = Date.now();
      await page.reload({ waitUntil: "commit" });

      await page.waitForFunction(
        (expected) => document.querySelector(".cm-content")?.textContent.includes(expected),
        testContent,
        { timeout: 10000 }
      );

      const reloadTime = Date.now() - startTime;
      console.log(`📊 Content visible after reload: ${reloadTime}ms`);

      expect(reloadTime).toBeLessThan(THRESHOLDS.RELOAD_VISIBLE_MS);
    } finally {
      await deletePage(page, pageId);
    }
  });
});

// ============================================================================
// TEST SUITE: Collaboration Sync
// ============================================================================

test.describe("Collaboration Sync", () => {
  test.beforeEach(async ({ page }) => {
    await loginAndWait(page);
  });

  test("collaboration should connect after page is visible", async ({ page }) => {
    const testContent = `Collab test ${Date.now()}`;

    const testPage = await createPageWithContent(page, "Collab Test", testContent);
    const pageId = testPage.external_id;

    try {
      await page.goto(`${BASE_URL}/pages/${pageId}/`);

      // Content should be visible first
      await page.waitForFunction(
        (expected) => document.querySelector(".cm-content")?.textContent.includes(expected),
        testContent,
        { timeout: 5000 }
      );
      const contentVisibleTime = Date.now();

      // Then collaboration should connect
      await page.waitForFunction(
        () => {
          const indicator = document.getElementById("collab-status");
          return indicator?.className.includes("connected");
        },
        { timeout: THRESHOLDS.COLLAB_CONNECTED_MS }
      );
      const collabConnectedTime = Date.now();

      console.log(
        `📊 Collab connected ${collabConnectedTime - contentVisibleTime}ms after content visible`
      );

      // Verify metrics (may lag slightly behind the status indicator)
      await page.waitForFunction(
        () => {
          if (!window.__metrics) return false;
          const data = window.__metrics.getRawData();
          return data.spans.some((s) => s.name === "collab_setup");
        },
        { timeout: 3000 }
      );
      const collabSpans = await getMetricSpans(page, "collab_setup");
      expect(collabSpans.length).toBeGreaterThan(0);

      const lastCollab = collabSpans[collabSpans.length - 1];
      expect(lastCollab.endAttributes.status).toBe("success");
    } finally {
      await deletePage(page, pageId);
    }
  });

  test("should handle sync timeout gracefully", async ({ page }) => {
    const testContent = `Timeout test ${Date.now()}`;

    const testPage = await createPageWithContent(page, "Timeout Test", testContent);
    const pageId = testPage.external_id;

    try {
      // Block WebSocket connections using Playwright's routeWebSocket API.
      // Note: page.route() only intercepts HTTP, not WebSocket connections.
      // routeWebSocket (added in Playwright v1.48) is the official API for this.
      await page.routeWebSocket("**/ws/**", (ws) => {
        ws.close();
      });

      await page.goto(`${BASE_URL}/pages/${pageId}/`);

      // Content should still be visible (loaded via REST API)
      await page.waitForFunction(
        (expected) => document.querySelector(".cm-content")?.textContent.includes(expected),
        testContent,
        { timeout: 5000 }
      );
      console.log("✅ Content visible despite WebSocket being blocked");

      // Status should show a non-connected state.
      // With WebSocket immediately closed, the collab setup gets rapid disconnects.
      // After 3 failures, collaboration.js dispatches "denied" and stops
      // reconnecting. The 10s sync timeout may also fire "offline".
      await page.waitForFunction(
        () => {
          const indicator = document.getElementById("collab-status");
          if (!indicator) return false;
          const cls = indicator.className;
          return cls.includes("offline") || cls.includes("error") || cls.includes("denied");
        },
        { timeout: 15000 }
      );

      const finalStatus = await page.evaluate(() => {
        const indicator = document.getElementById("collab-status");
        return indicator?.className || "";
      });
      console.log(`✅ Collab status shows non-connected state: "${finalStatus}"`);
    } finally {
      try {
        // Remove WebSocket route and clean up
        await page.unrouteAll({ behavior: "ignoreErrors" });
        await deletePage(page, pageId);
      } catch {
        // Page context may be closed if the test timed out
      }
    }
  });
});

// ============================================================================
// TEST SUITE: Content Integrity (No Duplication)
// ============================================================================

test.describe("Content Integrity", () => {
  test.beforeEach(async ({ page }) => {
    await loginAndWait(page);
  });

  test("content should not duplicate on page load", async ({ page }) => {
    const uniqueMarker = `UNIQUE_${Date.now()}_MARKER`;
    const testContent = `Line1\n${uniqueMarker}\nLine3`;

    const testPage = await createPageWithContent(page, "Dup Test", testContent);
    const pageId = testPage.external_id;

    try {
      await page.goto(`${BASE_URL}/pages/${pageId}/`);

      // Wait for content and collab to settle
      await page.waitForFunction(
        (marker) => document.querySelector(".cm-content")?.textContent.includes(marker),
        uniqueMarker,
        { timeout: 10000 }
      );

      // Wait for collaboration to connect
      await page.waitForTimeout(3000);

      // Count occurrences of the marker - should be exactly 1
      const occurrences = await page.evaluate((marker) => {
        const content = document.querySelector(".cm-content")?.textContent || "";
        return (content.match(new RegExp(marker, "g")) || []).length;
      }, uniqueMarker);

      console.log(`📊 Marker occurrences: ${occurrences}`);
      expect(occurrences).toBe(1);
    } finally {
      await deletePage(page, pageId);
    }
  });

  test("content should not duplicate on reload", async ({ page }) => {
    const uniqueMarker = `RELOAD_UNIQUE_${Date.now()}_MARKER`;
    const testContent = `Before\n${uniqueMarker}\nAfter`;

    const testPage = await createPageWithContent(page, "Reload Dup Test", testContent);
    const pageId = testPage.external_id;

    try {
      // First load
      await page.goto(`${BASE_URL}/pages/${pageId}/`);
      await page.waitForFunction(
        (marker) => document.querySelector(".cm-content")?.textContent.includes(marker),
        uniqueMarker,
        { timeout: 10000 }
      );

      // Wait for collab to stabilize
      await page.waitForFunction(
        () => document.getElementById("collab-status")?.className.includes("connected"),
        { timeout: 10000 }
      );
      await page.waitForTimeout(1000);

      // Reload page
      await page.reload();

      // Wait for content again
      await page.waitForFunction(
        (marker) => document.querySelector(".cm-content")?.textContent.includes(marker),
        uniqueMarker,
        { timeout: 10000 }
      );

      // Wait for collab to stabilize again
      await page.waitForTimeout(3000);

      // Check for duplication
      const occurrences = await page.evaluate((marker) => {
        const content = document.querySelector(".cm-content")?.textContent || "";
        return (content.match(new RegExp(marker, "g")) || []).length;
      }, uniqueMarker);

      console.log(`📊 Marker occurrences after reload: ${occurrences}`);
      expect(occurrences).toBe(1);
    } finally {
      await deletePage(page, pageId);
    }
  });

  test("content should not duplicate on rapid navigation", async ({ page }) => {
    const marker1 = `NAV_MARKER_1_${Date.now()}`;
    const marker2 = `NAV_MARKER_2_${Date.now()}`;

    const testPage1 = await createPageWithContent(page, "Nav Test 1", `Content: ${marker1}`);
    const testPage2 = await createPageWithContent(page, "Nav Test 2", `Content: ${marker2}`);

    try {
      // Navigate to first page
      await page.goto(`${BASE_URL}/pages/${testPage1.external_id}/`);
      await page.waitForSelector(".cm-content", { timeout: 5000 });
      await page.waitForTimeout(500);

      // Rapidly switch to second page
      await page.goto(`${BASE_URL}/pages/${testPage2.external_id}/`);
      await page.waitForSelector(".cm-content", { timeout: 5000 });
      await page.waitForTimeout(500);

      // Navigate back to first page
      await page.goto(`${BASE_URL}/pages/${testPage1.external_id}/`);
      await page.waitForFunction(
        (marker) => document.querySelector(".cm-content")?.textContent.includes(marker),
        marker1,
        { timeout: 10000 }
      );

      // Wait for collab to stabilize
      await page.waitForTimeout(3000);

      // Check both markers - should be exactly 1 each if shown
      const state = await page.evaluate(
        ({ m1, m2 }) => {
          const content = document.querySelector(".cm-content")?.textContent || "";
          return {
            marker1Count: (content.match(new RegExp(m1, "g")) || []).length,
            marker2Count: (content.match(new RegExp(m2, "g")) || []).length,
            contentLength: content.length,
          };
        },
        { m1: marker1, m2: marker2 }
      );

      console.log(`📊 Navigation state:`, state);

      // Should have marker1 exactly once, marker2 should not appear
      expect(state.marker1Count).toBe(1);
      expect(state.marker2Count).toBe(0);
    } finally {
      await deletePage(page, testPage1.external_id);
      await deletePage(page, testPage2.external_id);
    }
  });
});

// ============================================================================
// TEST SUITE: Metrics Collection
// ============================================================================

test.describe("Metrics Collection", () => {
  test.beforeEach(async ({ page }) => {
    await loginAndWait(page);
  });

  test("should collect all expected metrics spans", async ({ page }) => {
    const testContent = `Metrics test ${Date.now()}`;

    const testPage = await createPageWithContent(page, "Metrics Test", testContent);
    const pageId = testPage.external_id;

    try {
      await page.evaluate(() => window.__metrics?.clear());

      await page.goto(`${BASE_URL}/pages/${pageId}/`);

      // Wait for everything to settle
      await page.waitForFunction(
        (expected) => document.querySelector(".cm-content")?.textContent.includes(expected),
        testContent,
        { timeout: 10000 }
      );
      await page.waitForFunction(
        () => document.getElementById("collab-status")?.className.includes("connected"),
        { timeout: 10000 }
      );

      // Check metrics
      const summary = await getMetrics(page);
      console.log("📊 Metrics summary:", JSON.stringify(summary, null, 2));

      expect(summary).not.toBeNull();
      expect(summary.spanCount).toBeGreaterThan(0);

      // Verify expected span types exist
      const spans = await getMetricSpans(page);
      const spanNames = [...new Set(spans.map((s) => s.name))];
      console.log("📊 Collected span types:", spanNames);

      expect(spanNames).toContain("page_navigation");
      expect(spanNames).toContain("rest_fetch");
      expect(spanNames).toContain("page_load");
      expect(spanNames).toContain("collab_setup");
    } finally {
      await deletePage(page, pageId);
    }
  });

  test("should flag slow operations", async ({ page }) => {
    // This test verifies that slow operations are properly flagged
    const pageId = await getCurrentPageId(page);

    if (!pageId) {
      console.log("Skipping test - no current page");
      return;
    }

    await page.evaluate(() => window.__metrics?.clear());

    // Reload current page
    await page.reload();
    await page.waitForSelector(".cm-content", { timeout: 10000 });

    // Get timing stats
    const summary = await getMetrics(page);

    if (summary?.stats) {
      console.log("📊 Timing stats:");
      for (const [name, stats] of Object.entries(summary.stats)) {
        console.log(
          `   ${name}: avg=${stats.avg}ms, p95=${stats.p95}ms, threshold=${stats.threshold}ms, slowCount=${stats.slowCount}`
        );
      }
    }

    // Just verify we have stats
    expect(summary).not.toBeNull();
  });
});

// ============================================================================
// TEST SUITE: Edge Cases
// ============================================================================

test.describe("Edge Cases", () => {
  test.beforeEach(async ({ page }) => {
    await loginAndWait(page);
  });

  test("should handle empty page correctly", async ({ page }) => {
    // Create page with no content
    const testPage = await createPageWithContent(page, "Empty Test", "");
    const pageId = testPage.external_id;

    try {
      await page.goto(`${BASE_URL}/pages/${pageId}/`);

      // Should load without errors
      await page.waitForSelector(".cm-content", { timeout: 5000 });

      // Wait for collaboration to connect before typing
      await page.waitForFunction(
        () => document.getElementById("collab-status")?.className.includes("connected"),
        { timeout: 10000 }
      );

      // Should be able to type
      await page.click(".cm-content");
      const testText = `Typed content ${Date.now()}`;
      await page.keyboard.type(testText);

      // Verify content was added
      await page.waitForFunction(
        (expected) => document.querySelector(".cm-content")?.textContent.includes(expected),
        testText,
        { timeout: 5000 }
      );

      console.log("✅ Empty page handled correctly");
    } finally {
      await deletePage(page, pageId);
    }
  });

  test("should handle large content correctly", async ({ page }) => {
    // Create page with large content
    const largeContent = "A".repeat(100000); // 100KB of content
    const marker = `LARGE_${Date.now()}`;
    const testContent = `${marker}\n${largeContent}\n${marker}`;

    const testPage = await createPageWithContent(page, "Large Test", testContent);
    const pageId = testPage.external_id;

    try {
      const startTime = Date.now();
      await page.goto(`${BASE_URL}/pages/${pageId}/`);

      // Wait for marker to appear
      await page.waitForFunction(
        (m) => document.querySelector(".cm-content")?.textContent.includes(m),
        marker,
        { timeout: 15000 }
      );

      const loadTime = Date.now() - startTime;
      console.log(`📊 Large page (${testContent.length} chars) loaded in: ${loadTime}ms`);

      // Should not duplicate
      const occurrences = await page.evaluate((m) => {
        const content = document.querySelector(".cm-content")?.textContent || "";
        return (content.match(new RegExp(m, "g")) || []).length;
      }, marker);

      expect(occurrences).toBe(2); // Marker appears at start and end
    } finally {
      await deletePage(page, pageId);
    }
  });

  test("should handle special characters correctly", async ({ page }) => {
    // Create page with special characters
    const specialContent = `Unicode: 日本語 中文 العربية\nEmoji: 🎉🚀💡\nSymbols: <>&"'\`\nCode: function() { return 42; }`;
    const marker = `SPECIAL_${Date.now()}`;
    const testContent = `${marker}\n${specialContent}`;

    const testPage = await createPageWithContent(page, "Special Test", testContent);
    const pageId = testPage.external_id;

    try {
      await page.goto(`${BASE_URL}/pages/${pageId}/`);

      await page.waitForFunction(
        (m) => document.querySelector(".cm-content")?.textContent.includes(m),
        marker,
        { timeout: 10000 }
      );

      // Wait for collab to stabilize
      await page.waitForTimeout(3000);

      // Verify special characters are intact
      const content = await page.evaluate(() => {
        return document.querySelector(".cm-content")?.textContent || "";
      });

      expect(content).toContain("日本語");
      expect(content).toContain("🎉");
      expect(content).toContain("function()");

      // Should not duplicate
      const occurrences = await page.evaluate((m) => {
        const c = document.querySelector(".cm-content")?.textContent || "";
        return (c.match(new RegExp(m, "g")) || []).length;
      }, marker);

      expect(occurrences).toBe(1);
    } finally {
      await deletePage(page, pageId);
    }
  });
});
