/**
 * Visual regression test for checkbox indentation.
 *
 * Ensures nested checkboxes maintain consistent indentation alignment
 * with headings and other content.
 *
 * Run with:
 *   npx playwright test checkbox-indentation.spec.js --headed
 *
 * To update baseline screenshots:
 *   npx playwright test checkbox-indentation.spec.js --update-snapshots
 */

import { test, expect } from "@playwright/test";

const BASE_URL = process.env.TEST_BASE_URL || "http://localhost:9800";
const TEST_EMAIL = process.env.TEST_EMAIL || "dev@localhost";
const TEST_PASSWORD = process.env.TEST_PASSWORD || "dev";

async function login(page) {
  await page.goto(`${BASE_URL}/login`);
  await page.waitForSelector("#login-email", { timeout: 10000 });
  await page.fill("#login-email", TEST_EMAIL);
  await page.fill("#login-password", TEST_PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForSelector("#editor", { timeout: 20000 });
  await page.waitForSelector(".cm-content", { timeout: 10000 });
}

test.describe("Checkbox Indentation", () => {
  test.setTimeout(90000);

  test("nested checkboxes have consistent indentation", async ({ page }) => {
    await login(page);

    const newPageBtn = page.locator(".sidebar-new-page-btn").first();
    await newPageBtn.click();

    const modal = page.locator(".modal");
    await expect(modal).toBeVisible({ timeout: 5000 });

    const titleInput = page.locator("#page-title-input");
    await titleInput.fill("Indentation Test");

    const createBtn = page.locator(".modal-btn-primary");
    await createBtn.click();

    await page.waitForSelector(".cm-content", { timeout: 10000 });
    await page.waitForTimeout(1000);

    const editor = page.locator(".cm-content");
    await editor.click();

    // Insert markdown content as a single block
    const markdown = `# Heading Text

Regular paragraph text for alignment reference.

- [ ] Base level checkbox
  - [ ] First indent level
    - [ ] Second indent level
      - [ ] Third indent level

More text after checkboxes.`;

    await editor.fill(markdown);

    // Move cursor to the heading line (far from checkboxes) so decorations fully render
    await page.keyboard.press("Control+Home"); // Go to start of document
    await page.waitForTimeout(300);
    // Click on the heading line to position cursor there
    const headingElement = page.locator(".format-h1").first();
    await headingElement.click();
    await page.waitForTimeout(500);

    // Wait for checkboxes to render
    const checkboxes = page.locator(".format-checkbox");
    await expect(checkboxes.first()).toBeVisible({ timeout: 5000 });

    // Take a screenshot of just the editor content area for visual comparison
    const editorContainer = page.locator("#editor");
    await expect(editorContainer).toHaveScreenshot("checkbox-indentation.png", {
      maxDiffPixelRatio: 0.01,
    });
  });

  test("checkbox text aligns with bullet list text", async ({ page }) => {
    await login(page);

    const newPageBtn = page.locator(".sidebar-new-page-btn").first();
    await newPageBtn.click();

    const modal = page.locator(".modal");
    await expect(modal).toBeVisible({ timeout: 5000 });

    const titleInput = page.locator("#page-title-input");
    await titleInput.fill("Checkbox Bullet Alignment");

    const createBtn = page.locator(".modal-btn-primary");
    await createBtn.click();

    await page.waitForSelector(".cm-content", { timeout: 10000 });
    await page.waitForTimeout(1000);

    const editor = page.locator(".cm-content");
    await editor.click();

    // Insert markdown content as a single block
    const markdown = `
# Alignment Test

- Bullet item one
  - Nested bullet

- [ ] Checkbox item one
  - [ ] Nested checkbox

Text should align with list item text above.
`.trim();

    await editor.fill(markdown);

    // Move cursor to the heading line (far from lists) so decorations fully render
    await page.keyboard.press("Control+Home");
    await page.waitForTimeout(300);
    const headingElement = page.locator(".format-h1").first();
    await headingElement.click();
    await page.waitForTimeout(500);

    const checkboxes = page.locator(".format-checkbox");
    await expect(checkboxes.first()).toBeVisible({ timeout: 5000 });

    const editorContainer = page.locator("#editor");
    await expect(editorContainer).toHaveScreenshot("checkbox-bullet-alignment.png", {
      maxDiffPixelRatio: 0.01,
    });
  });
});
