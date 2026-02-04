/**
 * End-to-end tests for list formatting operations.
 *
 * Tests:
 * 1. Multi-line bullet list (ul) toggle via toolbar
 * 2. Multi-line ordered list (ol) toggle via toolbar
 * 3. Mixed content toggling
 * 4. Undo/redo functionality
 *
 * Run with:
 *   npx playwright test list-formatting.spec.js --headed
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

async function createTestPage(page, title) {
  const newPageBtn = page.locator(".sidebar-new-page-btn").first();
  await newPageBtn.click();

  const modal = page.locator(".modal");
  await expect(modal).toBeVisible({ timeout: 5000 });

  const titleInput = page.locator("#page-title-input");
  await titleInput.fill(title);

  const createBtn = page.locator(".modal-btn-primary");
  await createBtn.click();

  await page.waitForSelector(".cm-content", { timeout: 10000 });
  await page.waitForTimeout(1000);
}

async function getDocContent(page) {
  return await page.evaluate(() => {
    const cmContent = document.querySelector(".cm-content");
    const editorView = cmContent?.__codemirrorView || window.editorView;
    return editorView?.state.doc.toString() || null;
  });
}

async function selectAllText(page) {
  const isMac = process.platform === "darwin";
  await page.keyboard.press(isMac ? "Meta+a" : "Control+a");
  await page.waitForTimeout(200);
}

async function undoAction(page) {
  const isMac = process.platform === "darwin";
  await page.keyboard.press(isMac ? "Meta+z" : "Control+z");
  await page.waitForTimeout(200);
}

async function redoAction(page) {
  const isMac = process.platform === "darwin";
  await page.keyboard.press(isMac ? "Meta+Shift+z" : "Control+y");
  await page.waitForTimeout(200);
}

test.describe("List Formatting", () => {
  test.setTimeout(120000);

  test("multi-line bullet list toggle via toolbar", async ({ page }) => {
    console.log(`\n🔧 Logging in as: ${TEST_EMAIL}`);
    await login(page);
    console.log("✅ Logged in");

    await createTestPage(page, `Bullet List Test ${Date.now()}`);
    console.log("✅ Created test page");

    // Type multiple plain text lines
    const editor = page.locator(".cm-content");
    await editor.click();
    await page.keyboard.type("First item");
    await page.keyboard.press("Enter");
    await page.keyboard.type("Second item");
    await page.keyboard.press("Enter");
    await page.keyboard.type("Third item");
    await page.waitForTimeout(500);
    console.log("✅ Added three plain text lines");

    // Select all lines
    await selectAllText(page);
    console.log("✅ Selected all text");

    // Click the bullet list toolbar button
    const bulletBtn = page.locator('button.toolbar-btn[title="Bullet list"]');
    await expect(bulletBtn).toBeVisible({ timeout: 5000 });
    await bulletBtn.click();
    await page.waitForTimeout(500);
    console.log("✅ Clicked bullet list toolbar button");

    // Verify all lines have bullets
    const content = await getDocContent(page);
    console.log(`Content after toggle: ${content}`);

    expect(content).toBe("- First item\n- Second item\n- Third item");
    console.log("✅ All three lines converted to bullet list!");

    // Toggle again to remove bullets
    await selectAllText(page);
    await bulletBtn.click();
    await page.waitForTimeout(500);

    const contentAfterRemove = await getDocContent(page);
    expect(contentAfterRemove).toBe("First item\nSecond item\nThird item");
    console.log("✅ Bullets removed successfully!");
  });

  test("multi-line ordered list toggle via toolbar", async ({ page }) => {
    console.log(`\n🔧 Logging in as: ${TEST_EMAIL}`);
    await login(page);
    console.log("✅ Logged in");

    await createTestPage(page, `Ordered List Test ${Date.now()}`);
    console.log("✅ Created test page");

    // Type multiple plain text lines
    const editor = page.locator(".cm-content");
    await editor.click();
    await page.keyboard.type("First item");
    await page.keyboard.press("Enter");
    await page.keyboard.type("Second item");
    await page.keyboard.press("Enter");
    await page.keyboard.type("Third item");
    await page.waitForTimeout(500);
    console.log("✅ Added three plain text lines");

    // Select all lines
    await selectAllText(page);
    console.log("✅ Selected all text");

    // Click the numbered list toolbar button
    const numberedBtn = page.locator('button.toolbar-btn[title="Numbered list"]');
    await expect(numberedBtn).toBeVisible({ timeout: 5000 });
    await numberedBtn.click();
    await page.waitForTimeout(500);
    console.log("✅ Clicked numbered list toolbar button");

    // Verify all lines have numbers
    const content = await getDocContent(page);
    console.log(`Content after toggle: ${content}`);

    expect(content).toBe("1. First item\n2. Second item\n3. Third item");
    console.log("✅ All three lines converted to ordered list!");

    // Toggle again to remove numbers
    await selectAllText(page);
    await numberedBtn.click();
    await page.waitForTimeout(500);

    const contentAfterRemove = await getDocContent(page);
    expect(contentAfterRemove).toBe("First item\nSecond item\nThird item");
    console.log("✅ Numbers removed successfully!");
  });

  test("mixed ul/ol/checkbox toggling", async ({ page }) => {
    console.log(`\n🔧 Logging in as: ${TEST_EMAIL}`);
    await login(page);
    console.log("✅ Logged in");

    await createTestPage(page, `Mixed List Test ${Date.now()}`);
    console.log("✅ Created test page");

    // Start with plain text
    const editor = page.locator(".cm-content");
    await editor.click();
    await page.keyboard.type("Task A");
    await page.keyboard.press("Enter");
    await page.keyboard.type("Task B");
    await page.keyboard.press("Enter");
    await page.keyboard.type("Task C");
    await page.waitForTimeout(500);
    console.log("✅ Added three plain text lines");

    // Convert to bullets
    await selectAllText(page);
    const bulletBtn = page.locator('button.toolbar-btn[title="Bullet list"]');
    await bulletBtn.click();
    await page.waitForTimeout(300);

    let content = await getDocContent(page);
    expect(content).toBe("- Task A\n- Task B\n- Task C");
    console.log("✅ Converted to bullets");

    // Convert to checkboxes
    await selectAllText(page);
    const checklistBtn = page.locator('button.toolbar-btn[title^="Checklist"]');
    await checklistBtn.click();
    await page.waitForTimeout(300);

    content = await getDocContent(page);
    expect(content).toBe("- [ ] Task A\n- [ ] Task B\n- [ ] Task C");
    console.log("✅ Converted bullets to checkboxes");

    // Check all checkboxes
    await selectAllText(page);
    await checklistBtn.click();
    await page.waitForTimeout(300);

    content = await getDocContent(page);
    expect(content).toBe("- [x] Task A\n- [x] Task B\n- [x] Task C");
    console.log("✅ Checked all checkboxes");

    // Add numbers on top (for mixed format demonstration)
    await selectAllText(page);
    const numberedBtn = page.locator('button.toolbar-btn[title="Numbered list"]');
    await numberedBtn.click();
    await page.waitForTimeout(300);

    content = await getDocContent(page);
    expect(content).toBe("1. - [x] Task A\n2. - [x] Task B\n3. - [x] Task C");
    console.log("✅ Added numbers to checked checkboxes");
  });

  test("undo/redo with bullet list toggle", async ({ page }) => {
    console.log(`\n🔧 Logging in as: ${TEST_EMAIL}`);
    await login(page);
    console.log("✅ Logged in");

    await createTestPage(page, `Undo Redo Test ${Date.now()}`);
    console.log("✅ Created test page");

    const editor = page.locator(".cm-content");
    await editor.click();
    await page.keyboard.type("Item A");
    await page.keyboard.press("Enter");
    await page.keyboard.type("Item B");
    await page.waitForTimeout(500);

    const original = await getDocContent(page);
    expect(original).toBe("Item A\nItem B");
    console.log("✅ Created original content");

    // Add bullets
    await selectAllText(page);
    const bulletBtn = page.locator('button.toolbar-btn[title="Bullet list"]');
    await bulletBtn.click();
    await page.waitForTimeout(300);

    const withBullets = await getDocContent(page);
    expect(withBullets).toBe("- Item A\n- Item B");
    console.log("✅ Added bullets");

    // Undo
    await undoAction(page);
    const afterUndo = await getDocContent(page);
    expect(afterUndo).toBe(original);
    console.log("✅ Undo successful - back to original");

    // Redo
    await redoAction(page);
    const afterRedo = await getDocContent(page);
    expect(afterRedo).toBe(withBullets);
    console.log("✅ Redo successful - bullets restored");
  });

  test("undo/redo with ordered list toggle", async ({ page }) => {
    console.log(`\n🔧 Logging in as: ${TEST_EMAIL}`);
    await login(page);
    console.log("✅ Logged in");

    await createTestPage(page, `OL Undo Redo Test ${Date.now()}`);
    console.log("✅ Created test page");

    const editor = page.locator(".cm-content");
    await editor.click();
    await page.keyboard.type("Step 1");
    await page.keyboard.press("Enter");
    await page.keyboard.type("Step 2");
    await page.keyboard.press("Enter");
    await page.keyboard.type("Step 3");
    await page.waitForTimeout(500);

    const original = await getDocContent(page);
    console.log("✅ Created original content");

    // Add numbers
    await selectAllText(page);
    const numberedBtn = page.locator('button.toolbar-btn[title="Numbered list"]');
    await numberedBtn.click();
    await page.waitForTimeout(300);

    const withNumbers = await getDocContent(page);
    expect(withNumbers).toBe("1. Step 1\n2. Step 2\n3. Step 3");
    console.log("✅ Added numbers");

    // Undo
    await undoAction(page);
    const afterUndo = await getDocContent(page);
    expect(afterUndo).toBe(original);
    console.log("✅ Undo successful - back to original");

    // Redo
    await redoAction(page);
    const afterRedo = await getDocContent(page);
    expect(afterRedo).toBe(withNumbers);
    console.log("✅ Redo successful - numbers restored");
  });

  test("undo/redo multiple sequential toggles", async ({ page }) => {
    console.log(`\n🔧 Logging in as: ${TEST_EMAIL}`);
    await login(page);
    console.log("✅ Logged in");

    await createTestPage(page, `Multi Undo Test ${Date.now()}`);
    console.log("✅ Created test page");

    const editor = page.locator(".cm-content");
    await editor.click();
    await page.keyboard.type("Task A");
    await page.keyboard.press("Enter");
    await page.keyboard.type("Task B");
    await page.waitForTimeout(500);

    const original = await getDocContent(page);
    console.log("✅ Created original content");

    const bulletBtn = page.locator('button.toolbar-btn[title="Bullet list"]');
    const checklistBtn = page.locator('button.toolbar-btn[title^="Checklist"]');

    // Step 1: Add bullets
    await selectAllText(page);
    await bulletBtn.click();
    await page.waitForTimeout(300);
    const step1 = await getDocContent(page);
    expect(step1).toBe("- Task A\n- Task B");
    console.log("✅ Step 1: Added bullets");

    // Step 2: Convert to checkboxes
    await selectAllText(page);
    await checklistBtn.click();
    await page.waitForTimeout(300);
    const step2 = await getDocContent(page);
    expect(step2).toBe("- [ ] Task A\n- [ ] Task B");
    console.log("✅ Step 2: Converted to checkboxes");

    // Step 3: Check all
    await selectAllText(page);
    await checklistBtn.click();
    await page.waitForTimeout(300);
    const step3 = await getDocContent(page);
    expect(step3).toBe("- [x] Task A\n- [x] Task B");
    console.log("✅ Step 3: Checked all");

    // Undo back through all steps
    await undoAction(page);
    expect(await getDocContent(page)).toBe(step2);
    console.log("✅ Undo to step 2");

    await undoAction(page);
    expect(await getDocContent(page)).toBe(step1);
    console.log("✅ Undo to step 1");

    await undoAction(page);
    expect(await getDocContent(page)).toBe(original);
    console.log("✅ Undo to original");

    // Redo forward through all steps
    await redoAction(page);
    expect(await getDocContent(page)).toBe(step1);
    console.log("✅ Redo to step 1");

    await redoAction(page);
    expect(await getDocContent(page)).toBe(step2);
    console.log("✅ Redo to step 2");

    await redoAction(page);
    expect(await getDocContent(page)).toBe(step3);
    console.log("✅ Redo to step 3");
  });

  test("toggle cycles: add -> remove -> add", async ({ page }) => {
    console.log(`\n🔧 Logging in as: ${TEST_EMAIL}`);
    await login(page);
    console.log("✅ Logged in");

    await createTestPage(page, `Toggle Cycle Test ${Date.now()}`);
    console.log("✅ Created test page");

    const editor = page.locator(".cm-content");
    await editor.click();
    await page.keyboard.type("Line 1");
    await page.keyboard.press("Enter");
    await page.keyboard.type("Line 2");
    await page.keyboard.press("Enter");
    await page.keyboard.type("Line 3");
    await page.waitForTimeout(500);

    const original = await getDocContent(page);
    const bulletBtn = page.locator('button.toolbar-btn[title="Bullet list"]');

    // Cycle 1: Add bullets
    await selectAllText(page);
    await bulletBtn.click();
    await page.waitForTimeout(300);
    expect(await getDocContent(page)).toBe("- Line 1\n- Line 2\n- Line 3");
    console.log("✅ Cycle 1: Added bullets");

    // Cycle 2: Remove bullets
    await selectAllText(page);
    await bulletBtn.click();
    await page.waitForTimeout(300);
    expect(await getDocContent(page)).toBe(original);
    console.log("✅ Cycle 2: Removed bullets");

    // Cycle 3: Add bullets again
    await selectAllText(page);
    await bulletBtn.click();
    await page.waitForTimeout(300);
    expect(await getDocContent(page)).toBe("- Line 1\n- Line 2\n- Line 3");
    console.log("✅ Cycle 3: Added bullets again");

    // Cycle 4: Remove again
    await selectAllText(page);
    await bulletBtn.click();
    await page.waitForTimeout(300);
    expect(await getDocContent(page)).toBe(original);
    console.log("✅ Cycle 4: Removed bullets again");
  });
});
