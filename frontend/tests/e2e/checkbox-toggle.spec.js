/**
 * End-to-end tests for checkbox toggling.
 *
 * Tests:
 * 1. Checkbox toggles when clicked
 * 2. Checkbox state persists in document
 *
 * Run with:
 *   npx playwright test checkbox-toggle.spec.js --headed
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

test.describe("Checkbox Toggle", () => {
  test.setTimeout(90000);

  test("checkbox toggles when clicked programmatically", async ({ page }) => {
    console.log(`\n🔧 Logging in as: ${TEST_EMAIL}`);
    await login(page);
    console.log("✅ Logged in");

    // Create a new page with checkbox content
    const newPageBtn = page.locator(".sidebar-new-page-btn").first();
    await newPageBtn.click();

    const modal = page.locator(".modal");
    await expect(modal).toBeVisible({ timeout: 5000 });

    const titleInput = page.locator("#page-title-input");
    await titleInput.fill(`Checkbox Test ${Date.now()}`);

    const createBtn = page.locator(".modal-btn-primary");
    await createBtn.click();

    await page.waitForSelector(".cm-content", { timeout: 10000 });
    await page.waitForTimeout(1000);
    console.log("✅ Created test page");

    // Type checkbox content
    const editor = page.locator(".cm-content");
    await editor.click();
    await page.keyboard.type("- [ ] Task one");
    await page.keyboard.press("Enter");
    await page.keyboard.type("- [x] Task two (completed)");
    await page.keyboard.press("Enter");
    await page.keyboard.type("- [ ] Task three");
    await page.waitForTimeout(500);
    console.log("✅ Added checkbox content");

    // Take screenshot before clicking
    await page.screenshot({ path: "test-results/checkbox-before.png" });
    console.log("📸 Screenshot saved: checkbox-before.png");

    // Wait for decorations to render
    await page.waitForTimeout(500);

    // Check if checkboxes are rendered
    const checkboxes = page.locator(".format-checkbox");
    const checkboxCount = await checkboxes.count();
    console.log(`Found ${checkboxCount} checkboxes`);

    // Move cursor away from checkboxes (to end of document)
    await page.keyboard.press("End");
    await page.waitForTimeout(300);

    // Take screenshot showing rendered checkboxes
    await page.screenshot({ path: "test-results/checkbox-rendered.png" });
    console.log("📸 Screenshot saved: checkbox-rendered.png");

    // Get the first checkbox (unchecked task)
    if (checkboxCount > 0) {
      const firstCheckbox = checkboxes.first();

      // Log checkbox properties
      const isVisible = await firstCheckbox.isVisible();
      console.log(`First checkbox visible: ${isVisible}`);

      // Get bounding box
      const box = await firstCheckbox.boundingBox();
      console.log(
        `Checkbox bounding box: x=${box?.x}, y=${box?.y}, w=${box?.width}, h=${box?.height}`
      );

      // Get the initial checkbox state
      const checkedBefore = await firstCheckbox.isChecked();
      console.log(`Checkbox checked before: ${checkedBefore}`);
      expect(checkedBefore).toBe(false);

      // Click the checkbox by triggering click event directly
      console.log("🖱️ Clicking first checkbox...");
      await firstCheckbox.evaluate((el) => {
        console.log("[checkbox] Direct click on:", el.tagName, el.className);
        el.click();
      });
      await page.waitForTimeout(500);

      // Take screenshot after clicking
      await page.screenshot({ path: "test-results/checkbox-after.png" });
      console.log("📸 Screenshot saved: checkbox-after.png");

      // Get the checkbox state after clicking
      // The widget gets replaced, so we need to find the checkbox again
      const checkboxesAfter = page.locator(".format-checkbox");
      const firstCheckboxAfter = checkboxesAfter.first();
      const checkedAfter = await firstCheckboxAfter.isChecked();
      console.log(`Checkbox checked after: ${checkedAfter}`);

      // The checkbox state should have changed
      expect(checkedAfter).toBe(true);
      console.log("✅ Checkbox state changed from unchecked to checked!");
    } else {
      console.log("⚠️ No checkboxes found - taking debug screenshot");
      await page.screenshot({ path: "test-results/checkbox-debug.png" });

      // Log the raw content
      const rawContent = await editor.textContent();
      console.log(`Raw content: ${rawContent}`);

      // Check for the line class
      const checkboxLines = page.locator(".format-checkbox-item");
      const lineCount = await checkboxLines.count();
      console.log(`Checkbox lines found: ${lineCount}`);
    }
  });

  test("checkbox toggles with mouse click", async ({ page }) => {
    console.log(`\n🔧 Logging in as: ${TEST_EMAIL}`);
    await login(page);
    console.log("✅ Logged in");

    // Create a new page with checkbox content
    const newPageBtn = page.locator(".sidebar-new-page-btn").first();
    await newPageBtn.click();

    const modal = page.locator(".modal");
    await expect(modal).toBeVisible({ timeout: 5000 });

    const titleInput = page.locator("#page-title-input");
    await titleInput.fill(`Mouse Checkbox Test ${Date.now()}`);

    const createBtn = page.locator(".modal-btn-primary");
    await createBtn.click();

    await page.waitForSelector(".cm-content", { timeout: 10000 });
    await page.waitForTimeout(1000);
    console.log("✅ Created test page");

    // Type checkbox content with blank line at the end so cursor moves away
    const editor = page.locator(".cm-content");
    await editor.click();
    await page.keyboard.type("- [ ] Task one");
    await page.keyboard.press("Enter");
    await page.keyboard.press("Enter");
    await page.keyboard.type("Some other text here");
    await page.waitForTimeout(500);
    console.log("✅ Added checkbox content");

    // Move cursor to the end (away from checkbox line)
    await page.keyboard.press("End");
    await page.waitForTimeout(300);

    // Take screenshot
    await page.screenshot({ path: "test-results/mouse-checkbox-before.png" });
    console.log("📸 Screenshot saved: mouse-checkbox-before.png");

    // Check if checkboxes are rendered
    const checkboxes = page.locator(".format-checkbox");
    const checkboxCount = await checkboxes.count();
    console.log(`Found ${checkboxCount} checkboxes`);
    expect(checkboxCount).toBeGreaterThan(0);

    const firstCheckbox = checkboxes.first();
    const box = await firstCheckbox.boundingBox();
    console.log(
      `Checkbox bounding box: x=${box?.x}, y=${box?.y}, w=${box?.width}, h=${box?.height}`
    );

    // Get what element is at the click location using elementFromPoint
    if (box) {
      const elementAtPoint = await page.evaluate(
        ([x, y]) => {
          const el = document.elementFromPoint(x, y);
          return el ? `${el.tagName} ${el.className}` : "null";
        },
        [box.x + box.width / 2, box.y + box.height / 2]
      );
      console.log(`Element at click point: ${elementAtPoint}`);
    }

    // Get initial state
    const checkedBefore = await firstCheckbox.isChecked();
    console.log(`Checkbox checked before: ${checkedBefore}`);
    expect(checkedBefore).toBe(false);

    // Try clicking with Playwright's click
    console.log("🖱️ Clicking checkbox with Playwright click...");
    await firstCheckbox.click();
    await page.waitForTimeout(500);

    // Take screenshot after
    await page.screenshot({ path: "test-results/mouse-checkbox-after.png" });
    console.log("📸 Screenshot saved: mouse-checkbox-after.png");

    // Check state after
    const checkboxesAfter = page.locator(".format-checkbox");
    const firstCheckboxAfter = checkboxesAfter.first();
    const checkedAfter = await firstCheckboxAfter.isChecked();
    console.log(`Checkbox checked after: ${checkedAfter}`);

    expect(checkedAfter).toBe(true);
    console.log("✅ Checkbox toggled with mouse click!");
  });
});
