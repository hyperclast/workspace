/**
 * Fold gutter chevron position regression test.
 *
 * Locks in the fix from the "chevrons need to be in the margin, not
 * overlapping content" CSS change in editor.css:
 *
 *   - The chevron column does not overlap the text content (no negative
 *     margin on .cm-gutters combined with sticky-pulled overlap).
 *   - Every chevron sits at the same x — they form a clean vertical column.
 *   - The chevron glyph stays fully inside the scroller (no left-edge clip).
 *   - The chevrons are hidden by default and shown via the section-hover
 *     class added by sectionFoldHover.js.
 *
 * Run with:
 *   npx playwright test chevron-debug.spec.js --reporter=list
 */

import { test, expect } from "@playwright/test";
import { setupTestPage } from "./visual-regression/fixtures.js";

const BASE_URL = process.env.TEST_BASE_URL || "http://localhost:9800";
const TEST_EMAIL = process.env.TEST_EMAIL || "dev@localhost";
const TEST_PASSWORD = process.env.TEST_PASSWORD || "dev";

const FIXTURE = `# One Thing

- [ ] task

## Another Section

Some text here.

### Subsection

More text.

#### H4 heading

Content.

##### H5 heading

Content.
`;

async function flexibleLogin(page) {
  await page.goto(`${BASE_URL}/login`);
  await page.waitForSelector("#login-email", { timeout: 10000 });
  await page.fill("#login-email", TEST_EMAIL);
  await page.fill("#login-password", TEST_PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForSelector("#editor", { timeout: 20000 });
}

test("fold chevrons sit cleanly in the margin without overlapping content", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await flexibleLogin(page);
  await setupTestPage(page, FIXTURE, "Chevron Layout");
  await page.waitForTimeout(300);

  // Reveal all chevrons at once so we can read every fold marker's geometry
  await page.evaluate(() => {
    document
      .querySelectorAll(".cm-gutter.cm-foldGutter .cm-gutterElement")
      .forEach((el) => el.classList.add("section-hover"));
  });
  await page.waitForTimeout(150);

  const probe = await page.evaluate(() => {
    const scroller = document.querySelector(".cm-scroller");
    const content = document.querySelector(".cm-content");
    const spans = Array.from(
      document.querySelectorAll(".cm-gutter.cm-foldGutter .cm-gutterElement span")
    );

    const r = (el) => el.getBoundingClientRect();
    return {
      scrollerLeft: r(scroller).left,
      scrollerRight: r(scroller).right,
      contentLeft: r(content).left,
      chevronRects: spans.map((s) => ({
        left: r(s).left,
        right: r(s).right,
        text: s.textContent,
      })),
    };
  });

  expect(probe.chevronRects.length).toBeGreaterThanOrEqual(5);

  // Invariant 1: every chevron stays inside the scroller's clipping box
  for (const c of probe.chevronRects) {
    expect(c.left).toBeGreaterThanOrEqual(probe.scrollerLeft - 0.5);
    expect(c.right).toBeLessThanOrEqual(probe.scrollerRight + 0.5);
  }

  // Invariant 2: every chevron sits at the same x — column-aligned
  const xs = probe.chevronRects.map((c) => c.left);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  expect(maxX - minX).toBeLessThanOrEqual(0.5);

  // Invariant 3: chevron's right edge is before the content's left edge —
  // there must be a clean gap, not a pixel of overlap with the heading text.
  // This is the original bug: with margin-left: -8 + sticky, the chevron
  // visually sat inside the content's first 8px and crowded the heading.
  const maxRight = Math.max(...probe.chevronRects.map((c) => c.right));
  expect(maxRight).toBeLessThanOrEqual(probe.contentLeft);
  expect(probe.contentLeft - maxRight).toBeGreaterThanOrEqual(4);

  // Invariant 4: chevrons are hidden by default — once the override class is
  // removed and the pointer is moved off the gutter, opacity returns to 0.
  await page.evaluate(() => {
    document
      .querySelectorAll(".cm-gutter.cm-foldGutter .cm-gutterElement")
      .forEach((el) => el.classList.remove("section-hover"));
  });
  await page.mouse.move(0, 0);
  await page.waitForTimeout(200);
  const defaultOpacities = await page.evaluate(() => {
    return Array.from(document.querySelectorAll(".cm-gutter.cm-foldGutter .cm-gutterElement")).map(
      (el) => getComputedStyle(el).opacity
    );
  });
  for (const op of defaultOpacities) {
    expect(parseFloat(op)).toBeLessThan(0.01);
  }
});
