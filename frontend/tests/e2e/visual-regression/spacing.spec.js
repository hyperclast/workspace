/**
 * Spacing Measurement Tests
 *
 * These tests verify that spacing between elements is consistent and intentional.
 * They detect overlapping elements and excessive gaps.
 *
 * Run with: npx playwright test spacing.spec.js --headed
 */

import { test, expect } from "@playwright/test";
import { FIXTURES, login, setupTestPage } from "./fixtures.js";
import {
  measureVerticalSpacing,
  measureElementHeightsByType,
  measureLineHeights,
} from "./measurement-utils.js";

test.describe("Spacing Measurements", () => {
  test.setTimeout(90000);

  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test("same-type elements have consistent heights", async ({ page }) => {
    await setupTestPage(page, FIXTURES.listAlignment, "Height Consistency");

    const heightData = await page.evaluate(measureElementHeightsByType());

    console.log("Height data by type:", JSON.stringify(heightData, null, 2));

    // Group by type
    const byType = {};
    for (const item of heightData) {
      if (item.type === "empty") continue; // Skip empty lines
      if (!byType[item.type]) byType[item.type] = [];
      byType[item.type].push(item.height);
    }

    // ASSERTION: Same-type elements should have consistent heights
    for (const [type, heights] of Object.entries(byType)) {
      if (heights.length < 2) continue;

      const avgHeight = heights.reduce((a, b) => a + b, 0) / heights.length;
      const maxDeviation = Math.max(...heights.map((h) => Math.abs(h - avgHeight)));

      console.log(
        `Type "${type}": avg height ${avgHeight.toFixed(1)}px, max deviation ${maxDeviation.toFixed(
          1
        )}px`
      );

      expect(
        maxDeviation,
        `Type "${type}" has excessive height variance: max deviation ${maxDeviation.toFixed(
          1
        )}px from avg ${avgHeight.toFixed(1)}px`
      ).toBeLessThanOrEqual(3); // 3px tolerance for same-type elements
    }
  });

  test("no overlapping elements", async ({ page }) => {
    await setupTestPage(page, FIXTURES.spacingTest, "Overlap Check");

    const spacings = await page.evaluate(measureVerticalSpacing(".cm-line:not(:empty)"));

    console.log("Vertical spacings:", JSON.stringify(spacings, null, 2));

    // ASSERTION: No overlapping (negative gaps allowed up to -1px for subpixel)
    for (const s of spacings) {
      expect(
        s.spacing,
        `Overlapping elements: "${s.prevText}" and "${s.currText}" have ${s.spacing.toFixed(
          1
        )}px gap`
      ).toBeGreaterThanOrEqual(-1);
    }
  });

  test("no excessive gaps between elements", async ({ page }) => {
    await setupTestPage(page, FIXTURES.spacingTest, "Gap Check");

    const spacings = await page.evaluate(measureVerticalSpacing(".cm-line:not(:empty)"));

    // ASSERTION: No excessive gaps (more than 50px suggests a problem)
    for (const s of spacings) {
      expect(
        s.spacing,
        `Excessive gap: "${s.prevText}" to "${s.currText}" has ${s.spacing.toFixed(1)}px gap`
      ).toBeLessThanOrEqual(50);
    }
  });

  test("line heights are within reasonable bounds", async ({ page }) => {
    await setupTestPage(page, FIXTURES.mixedContent, "Line Height Bounds");

    const lineHeights = await page.evaluate(measureLineHeights());

    console.log("Line heights sample:", JSON.stringify(lineHeights.slice(0, 10), null, 2));

    for (const line of lineHeights) {
      if (line.lineHeight === "normal") continue;

      // Skip empty lines with intentionally small line-heights (e.g., HR-adjacent blanks)
      if (!line.text.trim() && line.className.includes("format-hr")) continue;

      const numericLineHeight = parseFloat(line.lineHeight);

      // If it's a unitless ratio
      if (!line.lineHeight.includes("px")) {
        expect(
          numericLineHeight,
          `Line "${line.text}" has line-height ${line.lineHeight} which is too small`
        ).toBeGreaterThanOrEqual(1.0);

        expect(
          numericLineHeight,
          `Line "${line.text}" has line-height ${line.lineHeight} which is too large`
        ).toBeLessThanOrEqual(2.5);
      } else {
        // If it's a px value, should be >= font size
        expect(
          numericLineHeight,
          `Line "${line.text}" has line-height ${line.lineHeight} which is smaller than font-size ${line.fontSize}px`
        ).toBeGreaterThanOrEqual(line.fontSize * 0.9);
      }
    }
  });

  test("bullet items have consistent spacing between them", async ({ page }) => {
    // Prefix with a blank line so cursor at position 0 (from Ctrl+Home in
    // setupTestPage) doesn't land on the first bullet line, which would
    // show raw "- " syntax instead of the "●" widget and change line height.
    const bulletContent = `Bullets:
- Item one
- Item two
- Item three
- Item four
- Item five`;

    await setupTestPage(page, bulletContent, "Bullet Spacing");

    const bulletMetrics = await page.evaluate(() => {
      const bullets = document.querySelectorAll(".format-bullet-item");
      const results = [];

      for (let i = 0; i < bullets.length; i++) {
        const rect = bullets[i].getBoundingClientRect();
        results.push({
          index: i,
          top: rect.top,
          bottom: rect.bottom,
          height: rect.height,
        });
      }

      // Calculate spacings
      const spacings = [];
      for (let i = 1; i < results.length; i++) {
        spacings.push({
          fromIndex: i - 1,
          toIndex: i,
          gap: results[i].top - results[i - 1].bottom,
        });
      }

      return { items: results, spacings };
    });

    console.log("Bullet metrics:", JSON.stringify(bulletMetrics, null, 2));

    // ASSERTION: All heights should be consistent
    const heights = bulletMetrics.items.map((b) => b.height);
    const avgHeight = heights.reduce((a, b) => a + b, 0) / heights.length;
    for (const h of heights) {
      expect(
        Math.abs(h - avgHeight),
        `Bullet height ${h}px differs from avg ${avgHeight.toFixed(1)}px`
      ).toBeLessThanOrEqual(2);
    }

    // ASSERTION: All spacings should be consistent
    if (bulletMetrics.spacings.length > 1) {
      const gaps = bulletMetrics.spacings.map((s) => s.gap);
      const avgGap = gaps.reduce((a, b) => a + b, 0) / gaps.length;

      for (const s of bulletMetrics.spacings) {
        expect(
          Math.abs(s.gap - avgGap),
          `Bullet spacing ${s.gap.toFixed(1)}px differs from avg ${avgGap.toFixed(1)}px`
        ).toBeLessThanOrEqual(2);
      }
    }
  });

  test("headings have appropriate spacing before and after", async ({ page }) => {
    await setupTestPage(page, FIXTURES.headingsAll, "Heading Spacing");

    const headingSpacing = await page.evaluate(() => {
      const lines = Array.from(document.querySelectorAll(".cm-line"));
      const results = [];

      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        if (line.className.includes("format-h")) {
          const rect = line.getBoundingClientRect();
          const prevRect = i > 0 ? lines[i - 1].getBoundingClientRect() : null;
          const nextRect = i < lines.length - 1 ? lines[i + 1].getBoundingClientRect() : null;

          results.push({
            level: line.className.match(/format-h(\d)/)?.[1],
            text: line.textContent?.slice(0, 20),
            height: rect.height,
            spaceBefore: prevRect ? rect.top - prevRect.bottom : null,
            spaceAfter: nextRect ? nextRect.top - rect.bottom : null,
          });
        }
      }

      return results;
    });

    console.log("Heading spacing:", JSON.stringify(headingSpacing, null, 2));

    // ASSERTION: Headings should have non-negative spacing
    for (const h of headingSpacing) {
      if (h.spaceBefore !== null) {
        expect(
          h.spaceBefore,
          `Heading "${h.text}" overlaps with previous element`
        ).toBeGreaterThanOrEqual(-1);
      }
      if (h.spaceAfter !== null) {
        expect(
          h.spaceAfter,
          `Heading "${h.text}" overlaps with next element`
        ).toBeGreaterThanOrEqual(-1);
      }
    }
  });

  test("blockquotes have consistent internal spacing", async ({ page }) => {
    await setupTestPage(page, FIXTURES.blockquotes, "Blockquote Spacing");

    const blockquoteMetrics = await page.evaluate(() => {
      const blockquotes = document.querySelectorAll(".format-blockquote");
      const results = [];

      for (let i = 0; i < blockquotes.length; i++) {
        const rect = blockquotes[i].getBoundingClientRect();
        results.push({
          index: i,
          height: rect.height,
          top: rect.top,
          bottom: rect.bottom,
          text: blockquotes[i].textContent?.slice(0, 30),
        });
      }

      // Calculate consecutive blockquote spacing
      const spacings = [];
      for (let i = 1; i < results.length; i++) {
        const gap = results[i].top - results[i - 1].bottom;
        // Only consider consecutive blockquotes (small gap)
        if (gap < 20) {
          spacings.push({
            fromIndex: i - 1,
            toIndex: i,
            gap,
          });
        }
      }

      return { items: results, spacings };
    });

    console.log("Blockquote metrics:", JSON.stringify(blockquoteMetrics, null, 2));

    // ASSERTION: All blockquote heights should be similar (within line-height)
    const heights = blockquoteMetrics.items.map((b) => b.height);
    const avgHeight = heights.reduce((a, b) => a + b, 0) / heights.length;

    for (const h of heights) {
      expect(
        Math.abs(h - avgHeight),
        `Blockquote height ${h}px differs significantly from avg ${avgHeight.toFixed(1)}px`
      ).toBeLessThanOrEqual(avgHeight * 0.5); // Allow 50% variance for multi-line
    }
  });

  test("table rows have consistent height", async ({ page }) => {
    await setupTestPage(page, FIXTURES.tablesComplex, "Table Row Spacing");

    const tableMetrics = await page.evaluate(() => {
      // Get non-separator table rows
      const rows = document.querySelectorAll(".cm-line.cm-table-header, .cm-line.cm-table-row");
      return Array.from(rows).map((row) => {
        const rect = row.getBoundingClientRect();
        return {
          height: rect.height,
          className: row.className,
          text: row.textContent?.slice(0, 30),
        };
      });
    });

    console.log("Table row metrics:", JSON.stringify(tableMetrics, null, 2));

    if (tableMetrics.length > 1) {
      const heights = tableMetrics.map((r) => r.height);
      const avgHeight = heights.reduce((a, b) => a + b, 0) / heights.length;

      // ASSERTION: All data rows should have similar height
      for (const row of tableMetrics) {
        expect(
          Math.abs(row.height - avgHeight),
          `Table row "${row.text}" height ${row.height}px differs from avg ${avgHeight.toFixed(
            1
          )}px`
        ).toBeLessThanOrEqual(5); // 5px tolerance for table rows
      }
    }
  });
});
