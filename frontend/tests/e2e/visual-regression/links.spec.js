/**
 * Link Styling Consistency Tests
 *
 * These tests verify that links are styled consistently across the document.
 * They check both internal and external links for visual consistency.
 *
 * Run with: npx playwright test links.spec.js --headed
 */

import { test, expect } from "@playwright/test";
import { FIXTURES, login, setupTestPage } from "./fixtures.js";
import { measureLinkStyles } from "./measurement-utils.js";

test.describe("Link Styling Consistency", () => {
  test.setTimeout(90000);

  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test("all internal links have identical styling", async ({ page }) => {
    await setupTestPage(page, FIXTURES.linksVariety, "Link Styling");

    const linkStyles = await page.evaluate(measureLinkStyles());

    console.log("Link styles:", JSON.stringify(linkStyles, null, 2));

    const internalLinks = linkStyles.filter((l) => l.isInternal);

    // ASSERTION: All internal links should have same color
    if (internalLinks.length > 1) {
      const firstColor = internalLinks[0].color;
      for (const link of internalLinks.slice(1)) {
        expect(
          link.color,
          `Internal link "${link.text}" has color ${link.color}, expected ${firstColor}`
        ).toBe(firstColor);
      }
    }

    // ASSERTION: All internal links should have same font-weight
    if (internalLinks.length > 1) {
      const firstWeight = internalLinks[0].fontWeight;
      for (const link of internalLinks.slice(1)) {
        expect(
          link.fontWeight,
          `Internal link "${link.text}" has font-weight ${link.fontWeight}, expected ${firstWeight}`
        ).toBe(firstWeight);
      }
    }
  });

  test("all external links have identical styling", async ({ page }) => {
    await setupTestPage(page, FIXTURES.linksVariety, "External Links");

    const linkStyles = await page.evaluate(measureLinkStyles());

    const externalLinks = linkStyles.filter((l) => l.isExternal);

    // ASSERTION: All external links should have same color
    if (externalLinks.length > 1) {
      const firstColor = externalLinks[0].color;
      for (const link of externalLinks.slice(1)) {
        expect(
          link.color,
          `External link "${link.text}" has color ${link.color}, expected ${firstColor}`
        ).toBe(firstColor);
      }
    }

    // ASSERTION: All external links should have same font-weight
    if (externalLinks.length > 1) {
      const firstWeight = externalLinks[0].fontWeight;
      for (const link of externalLinks.slice(1)) {
        expect(
          link.fontWeight,
          `External link "${link.text}" has font-weight ${link.fontWeight}, expected ${firstWeight}`
        ).toBe(firstWeight);
      }
    }
  });

  test("internal and external links are visually distinct", async ({ page }) => {
    await setupTestPage(page, FIXTURES.linksVariety, "Link Distinction");

    const linkStyles = await page.evaluate(measureLinkStyles());

    const internalLinks = linkStyles.filter((l) => l.isInternal);
    const externalLinks = linkStyles.filter((l) => l.isExternal);

    if (internalLinks.length > 0 && externalLinks.length > 0) {
      const internalSample = internalLinks[0];
      const externalSample = externalLinks[0];

      // ASSERTION: Internal and external should be visually different
      const hasDistinction =
        internalSample.color !== externalSample.color ||
        internalSample.fontWeight !== externalSample.fontWeight ||
        internalSample.textDecoration !== externalSample.textDecoration;

      expect(
        hasDistinction,
        `Internal and external links should be visually distinct. ` +
          `Internal: color=${internalSample.color}, weight=${internalSample.fontWeight}. ` +
          `External: color=${externalSample.color}, weight=${externalSample.fontWeight}.`
      ).toBe(true);
    }
  });

  test("link underlines appear consistently on hover", async ({ page }) => {
    const linkContent = `Here is a [test link](https://example.com) to check.`;
    await setupTestPage(page, linkContent, "Link Hover");

    // Get initial state
    const initialState = await page.evaluate(() => {
      const link = document.querySelector(".format-link");
      if (!link) return null;
      const style = getComputedStyle(link);
      return {
        textDecoration: style.textDecoration,
        textDecorationLine: style.textDecorationLine,
        backgroundColor: style.backgroundColor,
      };
    });

    console.log("Initial link state:", initialState);

    // Hover over link
    await page.hover(".format-link");
    await page.waitForTimeout(300);

    const hoverState = await page.evaluate(() => {
      const link = document.querySelector(".format-link");
      if (!link) return null;
      const style = getComputedStyle(link);
      return {
        textDecoration: style.textDecoration,
        textDecorationLine: style.textDecorationLine,
        backgroundColor: style.backgroundColor,
      };
    });

    console.log("Hover link state:", hoverState);

    // ASSERTION: Hover should add underline
    expect(hoverState.textDecorationLine, "Link should have underline on hover").toContain(
      "underline"
    );
  });

  test("links in different contexts have consistent base styling", async ({ page }) => {
    await setupTestPage(page, FIXTURES.linksVariety, "Link Contexts");

    // Measure links in different contexts
    const contextLinks = await page.evaluate(() => {
      const results = [];

      // Link in paragraph
      const paragraphLink = document.querySelector(
        ".cm-line:not(.format-bullet-item):not(.format-blockquote) .format-link"
      );
      if (paragraphLink) {
        const style = getComputedStyle(paragraphLink);
        results.push({
          context: "paragraph",
          color: style.color,
          fontWeight: style.fontWeight,
          fontSize: style.fontSize,
        });
      }

      // Link in list
      const listLink = document.querySelector(".cm-line.format-bullet-item .format-link");
      if (listLink) {
        const style = getComputedStyle(listLink);
        results.push({
          context: "list",
          color: style.color,
          fontWeight: style.fontWeight,
          fontSize: style.fontSize,
        });
      }

      // Link in blockquote
      const blockquoteLink = document.querySelector(".cm-line.format-blockquote .format-link");
      if (blockquoteLink) {
        const style = getComputedStyle(blockquoteLink);
        results.push({
          context: "blockquote",
          color: style.color,
          fontWeight: style.fontWeight,
          fontSize: style.fontSize,
        });
      }

      return results;
    });

    console.log("Context links:", JSON.stringify(contextLinks, null, 2));

    // ASSERTION: Links should have consistent color across contexts
    if (contextLinks.length > 1) {
      const firstColor = contextLinks[0].color;
      for (const link of contextLinks.slice(1)) {
        expect(
          link.color,
          `Link in ${link.context} has color ${link.color}, expected ${firstColor}`
        ).toBe(firstColor);
      }
    }
  });

  test("multiple adjacent links have consistent spacing", async ({ page }) => {
    const adjacentLinks = `[one](/pages/a/) [two](/pages/b/) [three](/pages/c/)`;
    await setupTestPage(page, adjacentLinks, "Adjacent Links");

    const linkPositions = await page.evaluate(() => {
      const links = document.querySelectorAll(".format-link");
      const results = [];

      for (let i = 0; i < links.length; i++) {
        const rect = links[i].getBoundingClientRect();
        results.push({
          index: i,
          left: rect.left,
          right: rect.right,
          text: links[i].textContent,
        });
      }

      // Calculate gaps between adjacent links
      const gaps = [];
      for (let i = 1; i < results.length; i++) {
        gaps.push({
          from: results[i - 1].text,
          to: results[i].text,
          gap: results[i].left - results[i - 1].right,
        });
      }

      return { links: results, gaps };
    });

    console.log("Adjacent link data:", JSON.stringify(linkPositions, null, 2));

    // ASSERTION: Gaps between adjacent links should be reasonably consistent
    // Note: Some variance is expected due to markdown/editor whitespace handling
    if (linkPositions.gaps.length > 1) {
      const firstGap = linkPositions.gaps[0].gap;
      for (const g of linkPositions.gaps.slice(1)) {
        expect(
          Math.abs(g.gap - firstGap),
          `Gap between "${g.from}" and "${g.to}" is ${g.gap}px, expected ~${firstGap}px`
        ).toBeLessThanOrEqual(15);
      }
    }
  });

  test("link height matches surrounding text height", async ({ page }) => {
    const mixedContent = `Regular text [link here](https://example.com) more text.`;
    await setupTestPage(page, mixedContent, "Link Height");

    const heights = await page.evaluate(() => {
      const link = document.querySelector(".format-link");
      const line = document.querySelector(".cm-line");

      if (!link || !line) return null;

      const linkRect = link.getBoundingClientRect();
      const lineRect = line.getBoundingClientRect();

      return {
        linkHeight: linkRect.height,
        lineHeight: lineRect.height,
        linkText: link.textContent,
      };
    });

    console.log("Height comparison:", heights);

    // ASSERTION: Link should not be taller than line
    if (heights) {
      expect(
        heights.linkHeight,
        `Link height ${heights.linkHeight}px exceeds line height ${heights.lineHeight}px`
      ).toBeLessThanOrEqual(heights.lineHeight + 2);
    }
  });
});
