/**
 * Alignment Measurement Tests
 *
 * These tests PROVE alignment mathematically by measuring actual pixel positions.
 * They fail when elements that should align have different positions.
 *
 * Run with: npx playwright test alignment.spec.js --headed
 */

import { test, expect } from "@playwright/test";
import { FIXTURES, login, setupTestPage } from "./fixtures.js";
import {
  measureIndentLevels,
  getTextStartPositions,
  measureTableColumns,
} from "./measurement-utils.js";

const ALIGNMENT_TOLERANCE = 1; // Allow 1px tolerance for subpixel rendering

test.describe("Alignment Measurements", () => {
  test.setTimeout(90000);

  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test("all base-level list items align at same left position", async ({ page }) => {
    await setupTestPage(page, FIXTURES.listAlignment, "List Alignment");

    const positions = await page.evaluate(() => {
      const items = document.querySelectorAll(
        '.cm-line.format-bullet-item:not([class*="format-indent"]), ' +
          '.cm-line.format-checkbox-item:not([class*="format-indent"]), ' +
          '.cm-line.format-ordered-item:not([class*="format-indent"])'
      );
      const container = document.querySelector(".cm-content");
      const containerLeft = container?.getBoundingClientRect().left || 0;

      return Array.from(items).map((item) => {
        const rect = item.getBoundingClientRect();
        const style = getComputedStyle(item);
        return {
          paddingLeft: parseFloat(style.paddingLeft),
          left: rect.left - containerLeft,
          className: item.className
            .split(" ")
            .filter((c) => c.includes("format"))
            .join(" "),
          text: item.textContent?.slice(0, 30),
        };
      });
    });

    console.log("Base-level list positions:", JSON.stringify(positions, null, 2));

    // ASSERTION: All base-level items should have the same padding-left
    if (positions.length > 1) {
      const firstPadding = positions[0].paddingLeft;
      for (const item of positions) {
        expect(
          Math.abs(item.paddingLeft - firstPadding),
          `List item "${item.text}" has padding ${item.paddingLeft}px, expected ${firstPadding}px`
        ).toBeLessThanOrEqual(ALIGNMENT_TOLERANCE);
      }
    }
  });

  test("nested list items have consistent indent increments", async ({ page }) => {
    await setupTestPage(page, FIXTURES.deepNesting, "Deep Nesting");

    const indentData = await page.evaluate(measureIndentLevels());

    console.log("Indent data:", JSON.stringify(indentData, null, 2));

    // Group by indent level
    const byLevel = {};
    for (const item of indentData) {
      if (!byLevel[item.indentLevel]) byLevel[item.indentLevel] = [];
      byLevel[item.indentLevel].push(item.paddingLeft);
    }

    // ASSERTION: Each indent level should have consistent padding
    for (const [level, paddings] of Object.entries(byLevel)) {
      const uniquePaddings = [...new Set(paddings.map((p) => Math.round(p)))];
      expect(
        uniquePaddings.length,
        `Indent level ${level} has inconsistent paddings: ${paddings.join(", ")}`
      ).toBe(1);
    }

    // ASSERTION: Indent increments should be consistent
    const levels = Object.keys(byLevel)
      .map(Number)
      .sort((a, b) => a - b);
    const increments = [];
    for (let i = 1; i < levels.length; i++) {
      const prevPadding = byLevel[levels[i - 1]][0];
      const currPadding = byLevel[levels[i]][0];
      increments.push(currPadding - prevPadding);
    }

    if (increments.length > 1) {
      const avgIncrement = increments.reduce((a, b) => a + b, 0) / increments.length;
      for (const inc of increments) {
        expect(
          Math.abs(inc - avgIncrement),
          `Inconsistent indent increment: ${inc}px, expected ~${avgIncrement.toFixed(1)}px`
        ).toBeLessThanOrEqual(2); // 2px tolerance for indent increments
      }
    }
  });

  test("table rows align vertically", async ({ page }) => {
    await setupTestPage(page, FIXTURES.tablesComplex, "Table Alignment");

    const tableData = await page.evaluate(measureTableColumns());

    console.log("Table row data:", JSON.stringify(tableData, null, 2));

    // ASSERTION: All table rows should have same left position
    if (tableData.length > 1) {
      const leftPositions = tableData.map((r) => r.left);
      const avgLeft = leftPositions.reduce((a, b) => a + b, 0) / leftPositions.length;

      for (const row of tableData) {
        expect(
          Math.abs(row.left - avgLeft),
          `Table row "${row.text}" has left ${row.left}px, expected ~${avgLeft.toFixed(1)}px`
        ).toBeLessThanOrEqual(ALIGNMENT_TOLERANCE);
      }
    }

    // ASSERTION: All table rows should have same width
    if (tableData.length > 1) {
      const widths = tableData.map((r) => r.width);
      const avgWidth = widths.reduce((a, b) => a + b, 0) / widths.length;

      for (const row of tableData) {
        expect(
          Math.abs(row.width - avgWidth),
          `Table row width ${row.width}px differs from avg ${avgWidth.toFixed(1)}px`
        ).toBeLessThanOrEqual(2);
      }
    }
  });

  test("heading text aligns with paragraph text", async ({ page }) => {
    await setupTestPage(page, FIXTURES.headingsAll, "Headings Alignment");

    // Measure text start positions (not element edges)
    const positions = await page.evaluate(() => {
      const container = document.querySelector(".cm-content");
      const containerRect = container?.getBoundingClientRect();
      const containerLeft = containerRect?.left || 0;

      const getTextStartX = (el) => {
        const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
        let node;
        while ((node = walker.nextNode())) {
          if (node.textContent.trim()) {
            const range = document.createRange();
            const trimStart = node.textContent.search(/\S/);
            if (trimStart >= 0 && trimStart < node.textContent.length) {
              range.setStart(node, trimStart);
              range.setEnd(node, trimStart + 1);
              return range.getBoundingClientRect().left - containerLeft;
            }
          }
        }
        return el.getBoundingClientRect().left - containerLeft;
      };

      const headings = document.querySelectorAll('.cm-line[class*="format-h"]');
      const paragraphs = Array.from(document.querySelectorAll(".cm-line"))
        .filter((l) => !l.className.includes("format-h") && l.textContent?.trim().length)
        .filter((l) => l.textContent.includes("Content"));

      return {
        headings: Array.from(headings).map((h) => ({
          level: h.className.match(/format-h(\d)/)?.[1],
          textStartX: getTextStartX(h),
          text: h.textContent?.slice(0, 20),
        })),
        paragraphs: paragraphs.slice(0, 3).map((p) => ({
          textStartX: getTextStartX(p),
          text: p.textContent?.slice(0, 20),
        })),
      };
    });

    console.log("Text start positions:", JSON.stringify(positions, null, 2));

    // ASSERTION: All headings should start at same X position
    if (positions.headings.length > 1) {
      const firstX = positions.headings[0].textStartX;
      for (const h of positions.headings) {
        expect(
          Math.abs(h.textStartX - firstX),
          `Heading "${h.text}" starts at ${h.textStartX}px, expected ${firstX}px`
        ).toBeLessThanOrEqual(ALIGNMENT_TOLERANCE);
      }
    }

    // ASSERTION: Paragraph text should align with heading text
    if (positions.headings.length > 0 && positions.paragraphs.length > 0) {
      const headingX = positions.headings[0].textStartX;
      const paragraphX = positions.paragraphs[0].textStartX;

      expect(
        Math.abs(headingX - paragraphX),
        `Heading text (${headingX}px) doesn't align with paragraph text (${paragraphX}px)`
      ).toBeLessThanOrEqual(ALIGNMENT_TOLERANCE);
    }
  });

  test("blockquote text aligns consistently", async ({ page }) => {
    await setupTestPage(page, FIXTURES.blockquotes, "Blockquote Alignment");

    const blockquoteData = await page.evaluate(() => {
      const blockquotes = document.querySelectorAll(".cm-line.format-blockquote");
      const container = document.querySelector(".cm-content");
      const containerLeft = container?.getBoundingClientRect().left || 0;

      return Array.from(blockquotes).map((bq) => {
        const rect = bq.getBoundingClientRect();
        const style = getComputedStyle(bq);
        return {
          left: rect.left - containerLeft,
          paddingLeft: parseFloat(style.paddingLeft),
          marginLeft: parseFloat(style.marginLeft),
          text: bq.textContent?.slice(0, 30),
        };
      });
    });

    console.log("Blockquote data:", JSON.stringify(blockquoteData, null, 2));

    // ASSERTION: All blockquotes should have same left position
    if (blockquoteData.length > 1) {
      const firstLeft = blockquoteData[0].left;
      for (const bq of blockquoteData) {
        expect(
          Math.abs(bq.left - firstLeft),
          `Blockquote "${bq.text}" at ${bq.left}px, expected ${firstLeft}px`
        ).toBeLessThanOrEqual(ALIGNMENT_TOLERANCE);
      }
    }
  });

  test("code block lines align consistently", async ({ page }) => {
    await setupTestPage(page, FIXTURES.codeBlocks, "Code Alignment");

    const codeData = await page.evaluate(() => {
      const codeLines = document.querySelectorAll(
        ".cm-line.format-code-block, .cm-line.format-code-fence"
      );
      const container = document.querySelector(".cm-content");
      const containerLeft = container?.getBoundingClientRect().left || 0;

      return Array.from(codeLines).map((line) => {
        const rect = line.getBoundingClientRect();
        const style = getComputedStyle(line);
        return {
          left: rect.left - containerLeft,
          paddingLeft: parseFloat(style.paddingLeft),
          width: rect.width,
          className: line.className
            .split(" ")
            .filter((c) => c.includes("format"))
            .join(" "),
          text: line.textContent?.slice(0, 30),
        };
      });
    });

    console.log("Code block data:", JSON.stringify(codeData, null, 2));

    // ASSERTION: All code lines should have same left position
    if (codeData.length > 1) {
      const firstLeft = codeData[0].left;
      for (const line of codeData) {
        expect(
          Math.abs(line.left - firstLeft),
          `Code line "${line.text}" at ${line.left}px, expected ${firstLeft}px`
        ).toBeLessThanOrEqual(ALIGNMENT_TOLERANCE);
      }
    }
  });
});
