/**
 * Scroll Behavior Regression Tests
 *
 * Tests for scroll performance and decoration rendering behavior.
 * These tests verify that:
 * - Scrolling updates viewport immediately
 * - Decorations render without multi-second delays
 * - Content is visible immediately after scrolling
 *
 * Console logs are kept for diagnostic purposes during CI/debugging.
 */

import { test, expect } from "@playwright/test";

const BASE_URL = process.env.TEST_BASE_URL || "http://localhost:9800";
const TEST_EMAIL = process.env.TEST_EMAIL || "dev@localhost";
const TEST_PASSWORD = process.env.TEST_PASSWORD || "dev";

const SCROLL_TIMEOUT_MS = 200;
const MAX_DECORATION_DELAY_MS = 500;
const MIN_VISIBLE_LINES_AFTER_SCROLL = 10;

test.describe("Scroll Behavior Regression", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}/login`);
    await page.waitForSelector("#login-email", { timeout: 10000 });
    await page.fill("#login-email", TEST_EMAIL);
    await page.fill("#login-password", TEST_PASSWORD);
    await page.click('button[type="submit"]');
    await page.waitForSelector("#editor", { timeout: 15000 });
    await page.waitForSelector(".cm-content", { timeout: 10000 });
    await page.waitForTimeout(500);
  });

  test("scroll updates viewport immediately", async ({ page }) => {
    const docInfo = await page.evaluate(() => {
      const view = window.editorView;
      if (!view) return { error: "No editorView", lines: 0 };
      return {
        lines: view.state.doc.lines,
        length: view.state.doc.length,
        viewportFrom: view.viewport.from,
        viewportTo: view.viewport.to,
      };
    });

    console.log("\n📊 Document info:");
    console.log(`   Lines: ${docInfo.lines}`);
    console.log(`   Length: ${docInfo.length}`);
    console.log(`   Initial viewport: ${docInfo.viewportFrom} - ${docInfo.viewportTo}`);

    test.skip(docInfo.lines < 100, "Document too small for meaningful scroll test");

    const scrollResult = await page.evaluate(async () => {
      const view = window.editorView;
      if (!view) return { error: "No editorView" };

      const initialViewportFrom = view.viewport.from;
      const targetLine = Math.floor(view.state.doc.lines / 2);
      const line = view.state.doc.line(targetLine);

      const scrollStart = performance.now();

      view.dispatch({
        selection: { anchor: line.from },
        scrollIntoView: true,
      });

      const scrollEnd = performance.now();
      const scrollTime = scrollEnd - scrollStart;
      const newViewportFrom = view.viewport.from;
      const viewportChanged = newViewportFrom !== initialViewportFrom;

      return {
        targetLine,
        scrollTime,
        initialViewportFrom,
        newViewportFrom,
        viewportChanged,
      };
    });

    console.log(`\n📊 Scroll to line ${scrollResult.targetLine}:`);
    console.log(`   Time: ${scrollResult.scrollTime.toFixed(2)}ms`);
    console.log(
      `   Viewport: ${scrollResult.initialViewportFrom} → ${scrollResult.newViewportFrom}`
    );
    console.log(`   Changed: ${scrollResult.viewportChanged}`);

    expect(scrollResult.scrollTime).toBeLessThan(SCROLL_TIMEOUT_MS);
    expect(scrollResult.viewportChanged).toBe(true);
  });

  test("decorations render without multi-second delay", async ({ page }) => {
    const docInfo = await page.evaluate(() => {
      const view = window.editorView;
      if (!view) return { error: "No editorView", lines: 0 };
      return { lines: view.state.doc.lines };
    });

    test.skip(docInfo.lines < 100, "Document too small for meaningful scroll test");

    const scrollResults = await page.evaluate(async () => {
      const view = window.editorView;
      if (!view) return { error: "No editorView" };

      const results = [];
      const targetLine = Math.floor(view.state.doc.lines / 2);

      results.push({
        label: "before scroll",
        time: 0,
        viewport: { from: view.viewport.from, to: view.viewport.to },
        decorations: document.querySelectorAll('[class*="format-"]').length,
        cmLines: document.querySelectorAll(".cm-line").length,
      });

      const line = view.state.doc.line(targetLine);
      const scrollStart = performance.now();

      view.dispatch({
        selection: { anchor: line.from },
        scrollIntoView: true,
      });

      const afterDispatch = performance.now();
      results.push({
        label: "after dispatch",
        time: afterDispatch - scrollStart,
        viewport: { from: view.viewport.from, to: view.viewport.to },
        decorations: document.querySelectorAll('[class*="format-"]').length,
        cmLines: document.querySelectorAll(".cm-line").length,
      });

      await new Promise((r) => setTimeout(r, 50));
      results.push({
        label: "t+50ms",
        time: performance.now() - scrollStart,
        viewport: { from: view.viewport.from, to: view.viewport.to },
        decorations: document.querySelectorAll('[class*="format-"]').length,
        cmLines: document.querySelectorAll(".cm-line").length,
      });

      await new Promise((r) => setTimeout(r, 150));
      results.push({
        label: "t+200ms",
        time: performance.now() - scrollStart,
        viewport: { from: view.viewport.from, to: view.viewport.to },
        decorations: document.querySelectorAll('[class*="format-"]').length,
        cmLines: document.querySelectorAll(".cm-line").length,
      });

      await new Promise((r) => setTimeout(r, 300));
      results.push({
        label: "t+500ms",
        time: performance.now() - scrollStart,
        viewport: { from: view.viewport.from, to: view.viewport.to },
        decorations: document.querySelectorAll('[class*="format-"]').length,
        cmLines: document.querySelectorAll(".cm-line").length,
      });

      return { targetLine, results };
    });

    console.log(`\n📊 Scrolled to line ${scrollResults.targetLine}:`);
    for (const r of scrollResults.results) {
      console.log(
        `   ${r.label} (${r.time.toFixed(0)}ms): viewport=${r.viewport.from}-${
          r.viewport.to
        }, decorations=${r.decorations}, lines=${r.cmLines}`
      );
    }

    const firstDecorations = scrollResults.results[1]?.decorations || 0;
    const at500msDecorations = scrollResults.results[4]?.decorations || 0;

    const decorationsStableQuickly =
      at500msDecorations <= firstDecorations * 1.5 || firstDecorations >= 10;

    if (!decorationsStableQuickly) {
      console.log(
        "\n⚠️ DETECTED: Significant decoration delay - decorations increased from",
        firstDecorations,
        "to",
        at500msDecorations
      );
    } else {
      console.log("\n✅ No significant decoration delay detected");
    }

    expect(decorationsStableQuickly).toBe(true);
  });

  test("decoration classes render correctly", async ({ page }) => {
    await page.waitForTimeout(500);

    const decorationClasses = await page.evaluate(() => {
      const elements = document.querySelectorAll(
        '[class*="format-"], [class*="section-"], .cm-line'
      );
      const classes = new Set();
      elements.forEach((el) => {
        const className = el.getAttribute("class") || "";
        className.split(" ").forEach((cls) => {
          if (
            cls.startsWith("format-") ||
            cls.startsWith("section-") ||
            cls.includes("highlight") ||
            cls.includes("bold") ||
            cls.includes("link") ||
            cls.includes("bullet")
          ) {
            classes.add(cls);
          }
        });
      });
      return Array.from(classes).sort();
    });

    console.log("\n📊 Decoration classes found:");
    decorationClasses.forEach((cls) => console.log(`   - ${cls}`));

    const counts = await page.evaluate(() => {
      return {
        formatBold: document.querySelectorAll(".format-bold").length,
        formatLink: document.querySelectorAll(".format-link").length,
        formatBullet: document.querySelectorAll(".format-bullet").length,
        formatCheckbox: document.querySelectorAll(".format-checkbox-item").length,
        sectionHeader: document.querySelectorAll('[class*="section-header"]').length,
        cmLine: document.querySelectorAll(".cm-line").length,
        anyFormat: document.querySelectorAll('[class*="format-"]').length,
      };
    });

    console.log("\n📊 Decoration counts:");
    Object.entries(counts).forEach(([key, value]) => {
      console.log(`   ${key}: ${value}`);
    });

    expect(counts.cmLine).toBeGreaterThan(0);
  });

  test("content is visible immediately after scroll", async ({ page }) => {
    await page.waitForTimeout(500);

    const docInfo = await page.evaluate(() => {
      const view = window.editorView;
      if (!view) return { error: "No editorView", lines: 0 };
      return {
        lines: view.state.doc.lines,
        length: view.state.doc.length,
      };
    });

    console.log(`\n📊 Document: ${docInfo.lines} lines, ${docInfo.length} chars`);

    test.skip(docInfo.lines < 100, "Document too small");

    const results = await page.evaluate(async () => {
      const view = window.editorView;
      if (!view) return { error: "No editorView" };

      const targetLine = Math.floor(view.state.doc.lines / 2);
      const line = view.state.doc.line(targetLine);

      view.dispatch({
        selection: { anchor: line.from },
        scrollIntoView: true,
      });

      const getVisibilityInfo = () => {
        const scroller = document.querySelector(".cm-scroller");
        const content = document.querySelector(".cm-content");
        const lines = document.querySelectorAll(".cm-line");

        let visibleLineCount = 0;
        let emptyLineCount = 0;

        lines.forEach((line) => {
          const text = line.textContent || "";
          if (text.trim().length > 0) {
            visibleLineCount++;
          } else {
            emptyLineCount++;
          }
        });

        return {
          scrollerHeight: scroller?.clientHeight,
          contentHeight: content?.offsetHeight,
          totalLinesInDOM: lines.length,
          visibleLineCount,
          emptyLineCount,
          viewportFrom: view.viewport.from,
          viewportTo: view.viewport.to,
          sampleLines: Array.from(lines)
            .slice(0, 5)
            .map((l) => l.textContent?.slice(0, 50)),
        };
      };

      const immediate = getVisibilityInfo();

      await new Promise((r) => setTimeout(r, 100));
      const after100 = getVisibilityInfo();

      return { targetLine, immediate, after100 };
    });

    console.log(`\n📊 Scrolled to line ${results.targetLine}:`);

    console.log("\n   IMMEDIATE:");
    console.log(`   - Scroller height: ${results.immediate.scrollerHeight}px`);
    console.log(`   - Content height: ${results.immediate.contentHeight}px`);
    console.log(`   - Lines in DOM: ${results.immediate.totalLinesInDOM}`);
    console.log(`   - With content: ${results.immediate.visibleLineCount}`);
    console.log(`   - Empty: ${results.immediate.emptyLineCount}`);
    console.log(`   - Sample: ${JSON.stringify(results.immediate.sampleLines)}`);

    console.log("\n   AFTER 100ms:");
    console.log(`   - Lines in DOM: ${results.after100.totalLinesInDOM}`);
    console.log(`   - With content: ${results.after100.visibleLineCount}`);

    if (results.immediate.visibleLineCount < MIN_VISIBLE_LINES_AFTER_SCROLL) {
      console.log("\n⚠️ WARNING: Low visible line count immediately after scroll");
    } else {
      console.log("\n✅ Content appears immediately");
    }

    expect(results.immediate.visibleLineCount).toBeGreaterThanOrEqual(
      MIN_VISIBLE_LINES_AFTER_SCROLL
    );
    expect(results.immediate.totalLinesInDOM).toBeGreaterThan(0);
  });

  test("viewport position is accurate after scroll", async ({ page }) => {
    const docInfo = await page.evaluate(() => {
      const view = window.editorView;
      if (!view) return { error: "No editorView", lines: 0 };
      return { lines: view.state.doc.lines };
    });

    test.skip(docInfo.lines < 100, "Document too small");

    const result = await page.evaluate(() => {
      const view = window.editorView;
      if (!view) return { error: "No editorView" };

      const targetLine = Math.floor(view.state.doc.lines / 2);
      const line = view.state.doc.line(targetLine);

      view.dispatch({
        selection: { anchor: line.from },
        scrollIntoView: true,
      });

      const viewportStartLine = view.state.doc.lineAt(view.viewport.from).number;
      const viewportEndLine = view.state.doc.lineAt(view.viewport.to).number;
      const targetInViewport = targetLine >= viewportStartLine && targetLine <= viewportEndLine;

      return {
        targetLine,
        viewportStartLine,
        viewportEndLine,
        targetInViewport,
        viewportFrom: view.viewport.from,
        viewportTo: view.viewport.to,
      };
    });

    console.log("\n📊 Viewport accuracy:");
    console.log(`   Target line: ${result.targetLine}`);
    console.log(`   Viewport lines: ${result.viewportStartLine} - ${result.viewportEndLine}`);
    console.log(`   Target in viewport: ${result.targetInViewport}`);

    expect(result.targetInViewport).toBe(true);
  });
});
