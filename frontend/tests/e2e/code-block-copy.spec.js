/**
 * End-to-end test for code block copy button.
 *
 * Creates a fenced code block with 100+ lines and verifies that clicking
 * the copy button copies the full content to the clipboard.
 *
 * Run with:
 *   npx playwright test code-block-copy.spec.js --headed
 */

import { test, expect } from "@playwright/test";
import { dismissSocratesPanel } from "./helpers.js";

const BASE_URL = process.env.TEST_BASE_URL || "http://localhost:9800";
const TEST_EMAIL = process.env.TEST_EMAIL || "dev@localhost";
const TEST_PASSWORD = process.env.TEST_PASSWORD || "dev";

const LINE_COUNT = 120;

/** Generate the code lines that go inside the fences (no fences included). */
function generateCodeLines(count) {
  const lines = [];
  for (let i = 1; i <= count; i++) {
    lines.push(`  console.log("line ${i}");`);
  }
  return lines;
}

const CODE_LINES = generateCodeLines(LINE_COUNT);

/** Full editor content: fenced code block wrapping the generated lines. */
const CODE_BLOCK_CONTENT = ["```javascript", ...CODE_LINES, "```"].join("\n");

async function login(page) {
  await page.goto(`${BASE_URL}/login`);
  await page.waitForSelector("#login-email", { timeout: 10000 });
  await page.fill("#login-email", TEST_EMAIL);
  await page.fill("#login-password", TEST_PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForSelector("#editor", { timeout: 20000 });
  await page.waitForSelector(".cm-content", { timeout: 10000 });
  await dismissSocratesPanel(page);
}

async function createPageWithContent(page, title, content) {
  const newPageBtn = page.locator(".sidebar-new-page-btn").first();
  await newPageBtn.click();

  const modal = page.locator(".modal");
  await modal.waitFor({ state: "visible", timeout: 5000 });
  await page.locator("#page-title-input").fill(title);
  await page.locator(".modal-btn-primary").click();

  await page.waitForSelector(".cm-content", { timeout: 10000 });
  await page.waitForTimeout(500);

  // Insert via CodeMirror dispatch so decorations (code block widgets) render
  await page.evaluate((text) => {
    const view = window.editorView;
    if (view) {
      view.dispatch({
        changes: { from: 0, to: view.state.doc.length, insert: text },
      });
    }
  }, content);

  // Let decorations render
  await page.waitForTimeout(1000);
}

test.describe("Code block copy button", () => {
  test.beforeEach(async ({ page, context }) => {
    // Grant clipboard permissions so navigator.clipboard.writeText works
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    await login(page);
  });

  test("copies all 120 lines from a large code block", async ({ page }) => {
    await createPageWithContent(page, "Copy Test", CODE_BLOCK_CONTENT);

    // Scroll to top so the copy button is visible
    await page.keyboard.press("Control+Home");
    await page.waitForTimeout(300);

    // The copy button sits inside the code block widget
    const copyBtn = page.locator("button.code-block-copy-btn").first();
    await expect(copyBtn).toBeVisible({ timeout: 5000 });

    await copyBtn.click();

    // Verify the success toast appears
    await expect(page.locator(".toast")).toContainText("Copied to clipboard", {
      timeout: 3000,
    });

    // Read clipboard and verify every line was copied
    const clipboardText = await page.evaluate(() => navigator.clipboard.readText());

    const copiedLines = clipboardText.split("\n");
    expect(copiedLines).toHaveLength(LINE_COUNT);

    // Verify first, last, and a middle line
    expect(copiedLines[0]).toBe('  console.log("line 1");');
    expect(copiedLines[59]).toBe('  console.log("line 60");');
    expect(copiedLines[LINE_COUNT - 1]).toBe(`  console.log("line ${LINE_COUNT}");`);

    // Verify the full content matches exactly (no truncation)
    expect(clipboardText).toBe(CODE_LINES.join("\n"));
  });
});
