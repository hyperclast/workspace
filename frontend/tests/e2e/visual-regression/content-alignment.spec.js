/**
 * Content Left-Alignment Regression Test
 *
 * Verifies that the breadcrumb, toolbar, page title, and editor content
 * all start at the same left pixel position — flush alignment like Obsidian.
 *
 * Measures the actual text-start X position of each element using
 * getBoundingClientRect().left + computedStyle.paddingLeft, so padding
 * doesn't fool us.
 *
 * Run with: npx playwright test content-alignment.spec.js --project=visual-regression --headed
 */

import { test, expect } from "@playwright/test";
import { FIXTURES, login, setupTestPage } from "./fixtures.js";

const ALIGNMENT_TOLERANCE = 2; // 2px tolerance for subpixel rendering

test.describe("Content Left-Alignment", () => {
  test.setTimeout(90000);

  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test("breadcrumb, toolbar, title, and editor content are left-aligned", async ({ page }) => {
    await setupTestPage(page, FIXTURES.mixedContent, "Alignment Flush Test");

    // Wait for all elements to render
    await page.waitForSelector(".cm-line", { timeout: 10000 });
    await page.waitForTimeout(500);

    const positions = await page.evaluate(() => {
      /**
       * Get the X pixel where visible text starts inside an element.
       * Uses a TreeWalker to find the first non-empty text node, then
       * measures its position with a Range — immune to padding tricks.
       */
      function getTextStartX(el) {
        const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null);
        let node;
        while ((node = walker.nextNode())) {
          if (node.textContent.trim()) {
            const trimStart = node.textContent.search(/\S/);
            if (trimStart >= 0 && trimStart < node.textContent.length) {
              const range = document.createRange();
              range.setStart(node, trimStart);
              range.setEnd(node, trimStart + 1);
              return range.getBoundingClientRect().left;
            }
          }
        }
        // Fallback: element left + padding
        const rect = el.getBoundingClientRect();
        const style = getComputedStyle(el);
        return rect.left + parseFloat(style.paddingLeft);
      }

      // 1. Breadcrumb — first text in the breadcrumb row
      const breadcrumb = document.querySelector(".breadcrumb-row");
      const breadcrumbX = breadcrumb ? getTextStartX(breadcrumb) : null;

      // 2. Toolbar — first visible button's left edge
      const toolbarBtn = document.querySelector(".toolbar-container .toolbar-btn");
      const toolbarX = toolbarBtn ? toolbarBtn.getBoundingClientRect().left : null;

      // 3. Page title — text start inside the input
      const titleInput = document.querySelector(".note-title-input");
      let titleX = null;
      if (titleInput) {
        // For input elements, text starts at left + paddingLeft
        const rect = titleInput.getBoundingClientRect();
        const style = getComputedStyle(titleInput);
        titleX = rect.left + parseFloat(style.paddingLeft);
      }

      // 4. Editor content — first non-empty .cm-line text start
      const cmLines = document.querySelectorAll(".cm-line");
      let contentX = null;
      for (const line of cmLines) {
        if (line.textContent.trim()) {
          contentX = getTextStartX(line);
          break;
        }
      }

      return {
        breadcrumbX: breadcrumbX ? Math.round(breadcrumbX * 10) / 10 : null,
        toolbarX: toolbarX ? Math.round(toolbarX * 10) / 10 : null,
        titleX: titleX ? Math.round(titleX * 10) / 10 : null,
        contentX: contentX ? Math.round(contentX * 10) / 10 : null,
      };
    });

    console.log("Left-alignment positions (px from viewport left):");
    console.log(`  Breadcrumb: ${positions.breadcrumbX}px`);
    console.log(`  Toolbar:    ${positions.toolbarX}px`);
    console.log(`  Title:      ${positions.titleX}px`);
    console.log(`  Content:    ${positions.contentX}px`);

    // All must be present
    expect(positions.breadcrumbX, "Breadcrumb not found").not.toBeNull();
    expect(positions.toolbarX, "Toolbar not found").not.toBeNull();
    expect(positions.titleX, "Title not found").not.toBeNull();
    expect(positions.contentX, "Content not found").not.toBeNull();

    // Use breadcrumb as the reference point
    const reference = positions.breadcrumbX;

    expect(
      Math.abs(positions.toolbarX - reference),
      `Toolbar (${positions.toolbarX}px) misaligned with breadcrumb (${reference}px)`
    ).toBeLessThanOrEqual(ALIGNMENT_TOLERANCE);

    expect(
      Math.abs(positions.titleX - reference),
      `Title (${positions.titleX}px) misaligned with breadcrumb (${reference}px)`
    ).toBeLessThanOrEqual(ALIGNMENT_TOLERANCE);

    expect(
      Math.abs(positions.contentX - reference),
      `Content (${positions.contentX}px) misaligned with breadcrumb (${reference}px)`
    ).toBeLessThanOrEqual(ALIGNMENT_TOLERANCE);
  });

  test("ordered list text aligns with paragraph text", async ({ page }) => {
    const content = `Regular paragraph text for reference.

1. First ordered item
2. Second ordered item`;

    await setupTestPage(page, content, "OL Alignment Test");
    await page.waitForSelector(".cm-line", { timeout: 10000 });
    await page.waitForTimeout(500);

    await page.keyboard.press("Control+End");
    await page.keyboard.press("Enter");
    await page.keyboard.press("Enter");
    await page.waitForTimeout(300);

    const positions = await page.evaluate(() => {
      function getTextStartX(el) {
        const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, {
          acceptNode(node) {
            const parent = node.parentElement;
            if (parent?.classList.contains("format-list-syntax")) return NodeFilter.FILTER_REJECT;
            if (node.textContent.trim()) return NodeFilter.FILTER_ACCEPT;
            return NodeFilter.FILTER_REJECT;
          },
        });
        const node = walker.nextNode();
        if (node) {
          const trimStart = node.textContent.search(/\S/);
          if (trimStart >= 0) {
            const range = document.createRange();
            range.setStart(node, trimStart);
            range.setEnd(node, trimStart + 1);
            return range.getBoundingClientRect().left;
          }
        }
        return null;
      }

      const paragraphs = Array.from(document.querySelectorAll(".cm-line")).filter(
        (l) => !l.className.includes("format-") && l.textContent.includes("Regular paragraph")
      );
      const paragraphX = paragraphs.length ? getTextStartX(paragraphs[0]) : null;

      const orderedItems = document.querySelectorAll(
        ".cm-line.format-ordered-item:not(.format-list-raw)"
      );
      const orderedX = orderedItems.length ? getTextStartX(orderedItems[0]) : null;

      return {
        paragraphX: paragraphX ? Math.round(paragraphX * 10) / 10 : null,
        orderedX: orderedX ? Math.round(orderedX * 10) / 10 : null,
      };
    });

    console.log("OL alignment (px from viewport left):");
    console.log(`  Paragraph: ${positions.paragraphX}px`);
    console.log(`  Ordered:   ${positions.orderedX}px`);

    expect(positions.paragraphX, "Paragraph not found").not.toBeNull();
    expect(positions.orderedX, "Ordered list not found").not.toBeNull();

    expect(
      Math.abs(positions.orderedX - positions.paragraphX),
      `OL text (${positions.orderedX}px) misaligned with paragraph (${positions.paragraphX}px)`
    ).toBeLessThanOrEqual(ALIGNMENT_TOLERANCE);
  });

  test("bullet and checkbox markers are not to the left of paragraph text", async ({ page }) => {
    const content = `Paragraph text.

- Bullet item

- [ ] Checkbox item`;

    await setupTestPage(page, content, "Marker Position Test");
    await page.waitForSelector(".cm-line", { timeout: 10000 });
    await page.waitForTimeout(500);

    await page.keyboard.press("Control+End");
    await page.keyboard.press("Enter");
    await page.keyboard.press("Enter");
    await page.waitForTimeout(300);

    const positions = await page.evaluate(() => {
      const paragraphs = Array.from(document.querySelectorAll(".cm-line")).filter(
        (l) => !l.className.includes("format-") && l.textContent.includes("Paragraph")
      );
      const paraX = paragraphs.length
        ? paragraphs[0].getBoundingClientRect().left +
          parseFloat(getComputedStyle(paragraphs[0]).paddingLeft)
        : null;

      const bullet = document.querySelector(".format-bullet");
      const bulletX = bullet ? bullet.getBoundingClientRect().left : null;

      const checkbox = document.querySelector(".format-checkbox");
      const checkboxX = checkbox ? checkbox.getBoundingClientRect().left : null;

      return {
        paraX: paraX ? Math.round(paraX) : null,
        bulletX: bulletX ? Math.round(bulletX) : null,
        checkboxX: checkboxX ? Math.round(checkboxX) : null,
      };
    });

    console.log("Marker positions:");
    console.log(`  Paragraph edge: ${positions.paraX}px`);
    console.log(`  Bullet marker:  ${positions.bulletX}px`);
    console.log(`  Checkbox marker: ${positions.checkboxX}px`);

    // Markers must be at or to the right of paragraph text edge
    if (positions.bulletX !== null && positions.paraX !== null) {
      expect(
        positions.bulletX,
        `Bullet (${positions.bulletX}px) is left of paragraph edge (${positions.paraX}px)`
      ).toBeGreaterThanOrEqual(positions.paraX - 2); // 2px tolerance
    }

    if (positions.checkboxX !== null && positions.paraX !== null) {
      expect(
        positions.checkboxX,
        `Checkbox (${positions.checkboxX}px) is left of paragraph edge (${positions.paraX}px)`
      ).toBeGreaterThanOrEqual(positions.paraX - 2); // 2px tolerance
    }
  });

  // Responsive alignment: verify flush alignment holds at all breakpoints
  // --page-padding: 48px (>900), 32px (≤900), 20px (≤700), 16px (≤640)
  for (const width of [900, 700, 640]) {
    test(`alignment holds at ${width}px viewport`, async ({ page }) => {
      await page.setViewportSize({ width, height: 800 });
      await setupTestPage(page, FIXTURES.mixedContent, `Responsive ${width}`);
      await page.waitForSelector(".cm-line", { timeout: 10000 });
      await page.waitForTimeout(500);

      const positions = await page.evaluate(() => {
        function getTextStartX(el) {
          const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null);
          let node;
          while ((node = walker.nextNode())) {
            if (node.textContent.trim()) {
              const trimStart = node.textContent.search(/\S/);
              if (trimStart >= 0 && trimStart < node.textContent.length) {
                const range = document.createRange();
                range.setStart(node, trimStart);
                range.setEnd(node, trimStart + 1);
                return range.getBoundingClientRect().left;
              }
            }
          }
          const rect = el.getBoundingClientRect();
          const style = getComputedStyle(el);
          return rect.left + parseFloat(style.paddingLeft);
        }

        const breadcrumb = document.querySelector(".breadcrumb-row");
        const breadcrumbX = breadcrumb ? getTextStartX(breadcrumb) : null;

        const toolbarBtn = document.querySelector(".toolbar-container .toolbar-btn");
        const toolbarX = toolbarBtn ? toolbarBtn.getBoundingClientRect().left : null;

        const titleInput = document.querySelector(".note-title-input");
        let titleX = null;
        if (titleInput) {
          const rect = titleInput.getBoundingClientRect();
          const style = getComputedStyle(titleInput);
          titleX = rect.left + parseFloat(style.paddingLeft);
        }

        const cmLines = document.querySelectorAll(".cm-line");
        let contentX = null;
        for (const line of cmLines) {
          if (line.textContent.trim()) {
            contentX = getTextStartX(line);
            break;
          }
        }

        return {
          breadcrumbX: breadcrumbX ? Math.round(breadcrumbX * 10) / 10 : null,
          toolbarX: toolbarX ? Math.round(toolbarX * 10) / 10 : null,
          titleX: titleX ? Math.round(titleX * 10) / 10 : null,
          contentX: contentX ? Math.round(contentX * 10) / 10 : null,
        };
      });

      console.log(`Alignment at ${width}px:`);
      console.log(`  Breadcrumb: ${positions.breadcrumbX}px`);
      console.log(`  Toolbar:    ${positions.toolbarX}px`);
      console.log(`  Title:      ${positions.titleX}px`);
      console.log(`  Content:    ${positions.contentX}px`);

      expect(positions.breadcrumbX, "Breadcrumb not found").not.toBeNull();
      expect(positions.contentX, "Content not found").not.toBeNull();

      const reference = positions.breadcrumbX;

      if (positions.toolbarX !== null) {
        expect(
          Math.abs(positions.toolbarX - reference),
          `@${width}px: Toolbar (${positions.toolbarX}px) misaligned with breadcrumb (${reference}px)`
        ).toBeLessThanOrEqual(ALIGNMENT_TOLERANCE);
      }

      if (positions.titleX !== null) {
        expect(
          Math.abs(positions.titleX - reference),
          `@${width}px: Title (${positions.titleX}px) misaligned with breadcrumb (${reference}px)`
        ).toBeLessThanOrEqual(ALIGNMENT_TOLERANCE);
      }

      expect(
        Math.abs(positions.contentX - reference),
        `@${width}px: Content (${positions.contentX}px) misaligned with breadcrumb (${reference}px)`
      ).toBeLessThanOrEqual(ALIGNMENT_TOLERANCE);
    });
  }
});
