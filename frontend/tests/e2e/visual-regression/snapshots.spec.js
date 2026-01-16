/**
 * Visual Snapshot Tests
 *
 * These tests capture screenshots and compare against baselines to detect
 * visual regressions. Use --update-snapshots to regenerate baselines.
 *
 * Run with: npx playwright test snapshots.spec.js --headed
 * Update baselines: npx playwright test snapshots.spec.js --update-snapshots
 */

import { test, expect } from "@playwright/test";
import { FIXTURES, login, setupTestPage } from "./fixtures.js";

test.describe("Visual Snapshots - Light Mode", () => {
  test.setTimeout(120000);

  test.beforeEach(async ({ page }) => {
    await page.emulateMedia({ colorScheme: "light" });
    await login(page);
  });

  test("mixed content renders correctly", async ({ page }) => {
    await setupTestPage(page, FIXTURES.mixedContent, "Mixed Content Snapshot");

    const editor = page.locator("#editor");
    await expect(editor).toHaveScreenshot("mixed-content-light.png", {
      maxDiffPixelRatio: 0.01,
    });
  });

  test("deep nesting renders correctly", async ({ page }) => {
    await setupTestPage(page, FIXTURES.deepNesting, "Deep Nesting Snapshot");

    const editor = page.locator("#editor");
    await expect(editor).toHaveScreenshot("deep-nesting-light.png", {
      maxDiffPixelRatio: 0.01,
    });
  });

  test("tables render correctly", async ({ page }) => {
    await setupTestPage(page, FIXTURES.tablesComplex, "Tables Snapshot");

    const editor = page.locator("#editor");
    await expect(editor).toHaveScreenshot("tables-light.png", {
      maxDiffPixelRatio: 0.01,
    });
  });

  test("links render correctly", async ({ page }) => {
    await setupTestPage(page, FIXTURES.linksVariety, "Links Snapshot");

    const editor = page.locator("#editor");
    await expect(editor).toHaveScreenshot("links-light.png", {
      maxDiffPixelRatio: 0.01,
    });
  });

  test("headings render correctly", async ({ page }) => {
    await setupTestPage(page, FIXTURES.headingsAll, "Headings Snapshot");

    const editor = page.locator("#editor");
    await expect(editor).toHaveScreenshot("headings-light.png", {
      maxDiffPixelRatio: 0.01,
    });
  });

  test("blockquotes render correctly", async ({ page }) => {
    await setupTestPage(page, FIXTURES.blockquotes, "Blockquotes Snapshot");

    const editor = page.locator("#editor");
    await expect(editor).toHaveScreenshot("blockquotes-light.png", {
      maxDiffPixelRatio: 0.01,
    });
  });

  test("code blocks render correctly", async ({ page }) => {
    await setupTestPage(page, FIXTURES.codeBlocks, "Code Snapshot");

    const editor = page.locator("#editor");
    await expect(editor).toHaveScreenshot("code-blocks-light.png", {
      maxDiffPixelRatio: 0.01,
    });
  });

  test("list alignment renders correctly", async ({ page }) => {
    await setupTestPage(page, FIXTURES.listAlignment, "List Alignment Snapshot");

    const editor = page.locator("#editor");
    await expect(editor).toHaveScreenshot("list-alignment-light.png", {
      maxDiffPixelRatio: 0.01,
    });
  });
});

test.describe("Visual Snapshots - Dark Mode", () => {
  test.setTimeout(120000);

  test.beforeEach(async ({ page }) => {
    await page.emulateMedia({ colorScheme: "dark" });
    await login(page);
  });

  test("mixed content renders correctly in dark mode", async ({ page }) => {
    await setupTestPage(page, FIXTURES.mixedContent, "Mixed Dark Snapshot");

    // Apply dark mode
    await page.evaluate(() => {
      document.documentElement.classList.add("dark");
      document.documentElement.setAttribute("data-theme", "dark");
    });
    await page.waitForTimeout(300);

    const editor = page.locator("#editor");
    await expect(editor).toHaveScreenshot("mixed-content-dark.png", {
      maxDiffPixelRatio: 0.01,
    });
  });

  test("links render correctly in dark mode", async ({ page }) => {
    await setupTestPage(page, FIXTURES.linksVariety, "Links Dark Snapshot");

    await page.evaluate(() => {
      document.documentElement.classList.add("dark");
      document.documentElement.setAttribute("data-theme", "dark");
    });
    await page.waitForTimeout(300);

    const editor = page.locator("#editor");
    await expect(editor).toHaveScreenshot("links-dark.png", {
      maxDiffPixelRatio: 0.01,
    });
  });

  test("tables render correctly in dark mode", async ({ page }) => {
    await setupTestPage(page, FIXTURES.tablesComplex, "Tables Dark Snapshot");

    await page.evaluate(() => {
      document.documentElement.classList.add("dark");
      document.documentElement.setAttribute("data-theme", "dark");
    });
    await page.waitForTimeout(300);

    const editor = page.locator("#editor");
    await expect(editor).toHaveScreenshot("tables-dark.png", {
      maxDiffPixelRatio: 0.01,
    });
  });

  test("code blocks render correctly in dark mode", async ({ page }) => {
    await setupTestPage(page, FIXTURES.codeBlocks, "Code Dark Snapshot");

    await page.evaluate(() => {
      document.documentElement.classList.add("dark");
      document.documentElement.setAttribute("data-theme", "dark");
    });
    await page.waitForTimeout(300);

    const editor = page.locator("#editor");
    await expect(editor).toHaveScreenshot("code-blocks-dark.png", {
      maxDiffPixelRatio: 0.01,
    });
  });
});

test.describe("Visual Snapshots - Viewport Sizes", () => {
  test.setTimeout(120000);

  // Note: Mobile viewport (375px) excluded - sidebar is hidden at that width
  // and setupTestPage relies on sidebar buttons. Mobile responsiveness
  // should be tested separately with appropriate navigation patterns.
  const viewports = [
    { name: "desktop", width: 1280, height: 800 },
    { name: "tablet", width: 768, height: 1024 },
  ];

  for (const vp of viewports) {
    test(`mixed content at ${vp.name} viewport`, async ({ page }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await login(page);
      await setupTestPage(page, FIXTURES.mixedContent, `Viewport ${vp.name} Snapshot`);

      const editor = page.locator("#editor");
      await expect(editor).toHaveScreenshot(`mixed-content-${vp.name}.png`, {
        maxDiffPixelRatio: 0.02, // Slightly more tolerance for responsive layouts
      });
    });
  }
});

test.describe("Visual Snapshots - Specific Issues", () => {
  test.setTimeout(120000);

  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test("customer-reported: link in blockquote styling", async ({ page }) => {
    // This tests the specific issue from customer screenshot
    const content = `> This is a blockquote with a [link here](https://example.com).

Regular text after blockquote.`;

    await setupTestPage(page, content, "Blockquote Link Issue");

    const editor = page.locator("#editor");
    await expect(editor).toHaveScreenshot("blockquote-link-issue.png", {
      maxDiffPixelRatio: 0.01,
    });
  });

  test("customer-reported: table separator styling", async ({ page }) => {
    // This tests table separator rendering
    const content = `| Header A | Header B | Header C |
|----------|----------|----------|
| Cell 1   | Cell 2   | Cell 3   |
| Cell 4   | Cell 5   | Cell 6   |`;

    await setupTestPage(page, content, "Table Separator Issue");

    const editor = page.locator("#editor");
    await expect(editor).toHaveScreenshot("table-separator-issue.png", {
      maxDiffPixelRatio: 0.01,
    });
  });

  test("customer-reported: list bullet alignment", async ({ page }) => {
    // This tests bullet/checkbox alignment
    const content = `# Section Title

- Bullet item one
- Bullet item two

- [ ] Checkbox one
- [x] Checkbox two

Text after lists.`;

    await setupTestPage(page, content, "List Alignment Issue");

    const editor = page.locator("#editor");
    await expect(editor).toHaveScreenshot("list-alignment-issue.png", {
      maxDiffPixelRatio: 0.01,
    });
  });

  test("customer-reported: heading and text alignment", async ({ page }) => {
    // This tests heading-to-text alignment
    const content = `# Heading Level 1

Regular paragraph text here.

## Heading Level 2

More regular text.

- List item after heading`;

    await setupTestPage(page, content, "Heading Alignment Issue");

    const editor = page.locator("#editor");
    await expect(editor).toHaveScreenshot("heading-alignment-issue.png", {
      maxDiffPixelRatio: 0.01,
    });
  });
});
