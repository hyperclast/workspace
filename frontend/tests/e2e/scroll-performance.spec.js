/**
 * Scroll Performance Regression Tests
 *
 * Tests for scroll performance with various document sizes.
 * These tests verify that scrolling remains fast regardless of document size.
 *
 * Performance thresholds:
 * - Scroll dispatch: < 50ms
 * - Total scroll operation: < 200ms
 * - Decorations should be stable (not increasing significantly over time)
 *
 * Run with:
 *   npx playwright test tests/e2e/scroll-performance.spec.js --headed
 */

import { test, expect } from "@playwright/test";

const BASE_URL = process.env.TEST_BASE_URL || "http://localhost:9800";
const TEST_EMAIL = process.env.TEST_EMAIL || "dev@localhost";
const TEST_PASSWORD = process.env.TEST_PASSWORD || "dev";

const PERF_THRESHOLDS = {
  scrollDispatchMs: 50,
  scrollTotalMs: 200,
  contentInjectionMsPerKLines: 500,
  decorationDelayThreshold: 1.5,
};

function generateLargeContent(lines) {
  const result = [];
  for (let i = 0; i < lines; i++) {
    const lineType = i % 10;
    switch (lineType) {
      case 0:
        result.push(`## Section ${Math.floor(i / 10) + 1}`);
        break;
      case 1:
        result.push(`**Bold text** on line ${i}`);
        break;
      case 2:
        result.push(`[Link ${i}](https://example.com/${i})`);
        break;
      case 3:
        result.push(`- Bullet item ${i}`);
        break;
      case 4:
        result.push(`- [ ] Task item ${i}`);
        break;
      case 5:
        result.push(`\`inline code ${i}\``);
        break;
      default:
        result.push(`Line ${i}: Regular paragraph text content for testing purposes.`);
    }
  }
  return result.join("\n");
}

test.describe("Scroll Performance", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}/login`);
    await page.waitForSelector("#login-email", { timeout: 10000 });
    await page.fill("#login-email", TEST_EMAIL);
    await page.fill("#login-password", TEST_PASSWORD);
    await page.click('button[type="submit"]');
    await page.waitForSelector("#editor", { timeout: 15000 });
    await page.waitForSelector(".cm-content", { timeout: 10000 });
  });

  test("content injection is fast for 2000 lines", async ({ page }) => {
    await page.waitForTimeout(1000);

    const content = generateLargeContent(2000);

    await page.click(".cm-content");
    await page.waitForTimeout(200);

    console.log("\n📊 Starting content injection (2000 lines)...");
    const startTime = Date.now();

    const result = await page.evaluate((text) => {
      const view = window.editorView;
      if (!view) return { success: false, error: "No editorView" };

      try {
        const initialLength = view.state.doc.length;

        view.dispatch({
          changes: { from: 0, to: view.state.doc.length, insert: text },
        });

        const afterLength = view.state.doc.length;

        return {
          success: true,
          initialLength,
          afterLength,
          expectedLength: text.length,
          docLines: view.state.doc.lines,
        };
      } catch (e) {
        return { success: false, error: e.message };
      }
    }, content);

    const injectTime = Date.now() - startTime;

    console.log(`   Injection result: ${result.success ? "SUCCESS" : "FAILED"}`);
    console.log(`   Document lines: ${result.docLines}`);
    console.log(`   Injection time: ${injectTime}ms`);
    console.log(`   Threshold: ${2 * PERF_THRESHOLDS.contentInjectionMsPerKLines}ms`);

    expect(result.success).toBe(true);
    expect(injectTime).toBeLessThan(2 * PERF_THRESHOLDS.contentInjectionMsPerKLines);
  });

  test("scroll performance with 3000 line document", async ({ page }) => {
    await page.waitForTimeout(1000);

    const content = generateLargeContent(3000);

    await page.click(".cm-content");
    await page.waitForTimeout(200);

    await page.evaluate((text) => {
      const view = window.editorView;
      if (view) {
        view.dispatch({
          changes: { from: 0, to: view.state.doc.length, insert: text },
        });
      }
    }, content);

    await page.waitForTimeout(500);

    console.log("\n📊 Measuring scroll performance (3000 lines)...");

    const scrollTimings = [];

    for (let targetLine = 500; targetLine <= 2500; targetLine += 500) {
      const timing = await page.evaluate(async (lineNum) => {
        const view = window.editorView;
        if (!view) return { error: "No editorView" };

        const actualLine = Math.min(lineNum, view.state.doc.lines);
        const line = view.state.doc.line(actualLine);

        const start = performance.now();

        view.dispatch({
          selection: { anchor: line.from },
          scrollIntoView: true,
        });

        document.body.offsetHeight;

        const afterDispatch = performance.now();

        await new Promise((r) => setTimeout(r, 50));

        const afterWait = performance.now();

        const decorationCount = document.querySelectorAll('[class*="format-"]').length;

        return {
          targetLine: lineNum,
          actualLine,
          dispatchTime: afterDispatch - start,
          totalTime: afterWait - start,
          decorationCount,
          viewportFrom: view.viewport.from,
          viewportTo: view.viewport.to,
        };
      }, targetLine);

      scrollTimings.push(timing);
      console.log(
        `   Line ${timing.targetLine}: dispatch=${timing.dispatchTime.toFixed(
          1
        )}ms, total=${timing.totalTime.toFixed(1)}ms, decorations=${timing.decorationCount}`
      );
    }

    const avgDispatch =
      scrollTimings.reduce((a, b) => a + b.dispatchTime, 0) / scrollTimings.length;
    const avgTotal = scrollTimings.reduce((a, b) => a + b.totalTime, 0) / scrollTimings.length;
    const maxDispatch = Math.max(...scrollTimings.map((t) => t.dispatchTime));

    console.log(`\n📊 Results:`);
    console.log(`   Avg dispatch time: ${avgDispatch.toFixed(1)}ms`);
    console.log(`   Avg total time: ${avgTotal.toFixed(1)}ms`);
    console.log(`   Max dispatch time: ${maxDispatch.toFixed(1)}ms`);
    console.log(
      `   Thresholds: dispatch < ${PERF_THRESHOLDS.scrollDispatchMs}ms, total < ${PERF_THRESHOLDS.scrollTotalMs}ms`
    );

    expect(avgDispatch).toBeLessThan(PERF_THRESHOLDS.scrollDispatchMs);
    expect(avgTotal).toBeLessThan(PERF_THRESHOLDS.scrollTotalMs);
  });

  test("decorations render without delay after scroll (5000 lines)", async ({ page }) => {
    await page.waitForTimeout(1000);

    const content = generateLargeContent(5000);

    await page.click(".cm-content");
    await page.waitForTimeout(200);

    console.log("\n📊 Injecting 5000 lines of content...");
    const injectStart = Date.now();

    await page.evaluate((text) => {
      const view = window.editorView;
      if (view) {
        view.dispatch({
          changes: { from: 0, to: view.state.doc.length, insert: text },
        });
      }
    }, content);

    const injectTime = Date.now() - injectStart;
    console.log(`   Content injection took: ${injectTime}ms`);

    await page.waitForTimeout(200);

    console.log("\n📊 Scrolling to line 4500...");

    const scrollResult = await page.evaluate(async () => {
      const view = window.editorView;
      if (!view) return { error: "No editorView" };

      const results = [];

      const targetLine = Math.min(4500, view.state.doc.lines);
      const line = view.state.doc.line(targetLine);

      view.dispatch({
        selection: { anchor: line.from },
        scrollIntoView: true,
      });

      results.push({
        time: 0,
        viewportFrom: view.viewport.from,
        viewportTo: view.viewport.to,
        decorationCount: document.querySelectorAll('[class*="format-"]').length,
      });

      await new Promise((r) => setTimeout(r, 100));
      results.push({
        time: 100,
        viewportFrom: view.viewport.from,
        viewportTo: view.viewport.to,
        decorationCount: document.querySelectorAll('[class*="format-"]').length,
      });

      await new Promise((r) => setTimeout(r, 400));
      results.push({
        time: 500,
        viewportFrom: view.viewport.from,
        viewportTo: view.viewport.to,
        decorationCount: document.querySelectorAll('[class*="format-"]').length,
      });

      await new Promise((r) => setTimeout(r, 500));
      results.push({
        time: 1000,
        viewportFrom: view.viewport.from,
        viewportTo: view.viewport.to,
        decorationCount: document.querySelectorAll('[class*="format-"]').length,
      });

      return results;
    });

    console.log("\n📊 Decoration visibility over time:");
    for (const r of scrollResult) {
      console.log(
        `   t=${r.time}ms: viewport=${r.viewportFrom}-${r.viewportTo}, decorations=${r.decorationCount}`
      );
    }

    const initialDecorations = scrollResult[0]?.decorationCount || 0;
    const finalDecorations = scrollResult[scrollResult.length - 1]?.decorationCount || 0;
    const decorationRatio = initialDecorations > 0 ? finalDecorations / initialDecorations : 1;

    const decorationsStable = decorationRatio < PERF_THRESHOLDS.decorationDelayThreshold;

    if (!decorationsStable) {
      console.log(
        `\n⚠️ DETECTED: Decorations increasing over time (${initialDecorations} → ${finalDecorations}, ratio: ${decorationRatio.toFixed(
          2
        )})`
      );
    } else {
      console.log(
        `\n✅ Decorations stable (${initialDecorations} → ${finalDecorations}, ratio: ${decorationRatio.toFixed(
          2
        )})`
      );
    }

    expect(decorationsStable).toBe(true);
  });

  test("rapid consecutive scrolls remain performant", async ({ page }) => {
    await page.waitForTimeout(1000);

    const content = generateLargeContent(3000);

    await page.click(".cm-content");
    await page.waitForTimeout(200);

    await page.evaluate((text) => {
      const view = window.editorView;
      if (view) {
        view.dispatch({
          changes: { from: 0, to: view.state.doc.length, insert: text },
        });
      }
    }, content);

    await page.waitForTimeout(500);

    console.log("\n📊 Testing rapid consecutive scrolls...");

    const result = await page.evaluate(async () => {
      const view = window.editorView;
      if (!view) return { error: "No editorView" };

      const timings = [];
      const targetLines = [500, 1500, 2500, 1000, 2000, 100, 2800, 200];

      for (const lineNum of targetLines) {
        const actualLine = Math.min(lineNum, view.state.doc.lines);
        const line = view.state.doc.line(actualLine);

        const start = performance.now();

        view.dispatch({
          selection: { anchor: line.from },
          scrollIntoView: true,
        });

        document.body.offsetHeight;

        const elapsed = performance.now() - start;
        timings.push({ lineNum, elapsed });
      }

      return {
        timings,
        avg: timings.reduce((a, b) => a + b.elapsed, 0) / timings.length,
        max: Math.max(...timings.map((t) => t.elapsed)),
      };
    });

    console.log("   Rapid scroll timings:");
    for (const t of result.timings) {
      console.log(`     Line ${t.lineNum}: ${t.elapsed.toFixed(1)}ms`);
    }

    console.log(`\n📊 Results:`);
    console.log(`   Avg time: ${result.avg.toFixed(1)}ms`);
    console.log(`   Max time: ${result.max.toFixed(1)}ms`);

    expect(result.avg).toBeLessThan(PERF_THRESHOLDS.scrollDispatchMs);
    expect(result.max).toBeLessThan(PERF_THRESHOLDS.scrollTotalMs);
  });

  test("scroll in both directions performs equally", async ({ page }) => {
    await page.waitForTimeout(1000);

    const content = generateLargeContent(3000);

    await page.click(".cm-content");
    await page.waitForTimeout(200);

    await page.evaluate((text) => {
      const view = window.editorView;
      if (view) {
        view.dispatch({
          changes: { from: 0, to: view.state.doc.length, insert: text },
        });
      }
    }, content);

    await page.waitForTimeout(500);

    console.log("\n📊 Testing scroll in both directions...");

    const result = await page.evaluate(async () => {
      const view = window.editorView;
      if (!view) return { error: "No editorView" };

      const downTimings = [];
      const upTimings = [];

      for (let lineNum = 500; lineNum <= 2500; lineNum += 500) {
        const line = view.state.doc.line(lineNum);
        const start = performance.now();
        view.dispatch({
          selection: { anchor: line.from },
          scrollIntoView: true,
        });
        document.body.offsetHeight;
        downTimings.push(performance.now() - start);
      }

      for (let lineNum = 2500; lineNum >= 500; lineNum -= 500) {
        const line = view.state.doc.line(lineNum);
        const start = performance.now();
        view.dispatch({
          selection: { anchor: line.from },
          scrollIntoView: true,
        });
        document.body.offsetHeight;
        upTimings.push(performance.now() - start);
      }

      return {
        downAvg: downTimings.reduce((a, b) => a + b, 0) / downTimings.length,
        upAvg: upTimings.reduce((a, b) => a + b, 0) / upTimings.length,
        downTimings,
        upTimings,
      };
    });

    console.log(`   Scroll down avg: ${result.downAvg.toFixed(1)}ms`);
    console.log(`   Scroll up avg: ${result.upAvg.toFixed(1)}ms`);

    const ratio = Math.max(result.downAvg, result.upAvg) / Math.min(result.downAvg, result.upAvg);
    console.log(`   Direction ratio: ${ratio.toFixed(2)}x`);

    expect(result.downAvg).toBeLessThan(PERF_THRESHOLDS.scrollDispatchMs);
    expect(result.upAvg).toBeLessThan(PERF_THRESHOLDS.scrollDispatchMs);
    expect(ratio).toBeLessThan(3);
  });
});
