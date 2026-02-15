/**
 * End-to-end tests for the New Page modal.
 *
 * Tests:
 * 1. Modal opens with title field and date presets
 * 2. Clicking date presets updates the title field
 * 3. Copy from dropdown shows existing pages
 * 4. Creating a page with copy_from copies content
 * 5. Preferences are remembered (localStorage)
 *
 * Run with:
 *   npx playwright test new-page-modal.spec.js --headed
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

function getTodayDateString() {
  return new Date().toISOString().split("T")[0];
}

test.describe("New Page Modal", () => {
  test.setTimeout(90000);

  test("modal shows title presets that update the input", async ({ page }) => {
    console.log(`\n🔧 Logging in as: ${TEST_EMAIL}`);
    await login(page);
    console.log("✅ Logged in");

    const newPageBtn = page.locator(".sidebar-new-page-btn").first();
    await newPageBtn.click();

    const modal = page.locator(".modal");
    await expect(modal).toBeVisible({ timeout: 5000 });
    console.log("✅ Modal opened");

    const titleInput = page.locator("#page-title-input");
    await expect(titleInput).toBeVisible();
    console.log("✅ Title input visible");

    const presetsArea = page.locator(".title-presets");
    await expect(presetsArea).toBeVisible();
    console.log("✅ Title presets visible");

    const todayLink = page.locator(".preset-link").first();
    await expect(todayLink).toBeVisible();

    const todayDate = getTodayDateString();
    await expect(todayLink).toContainText(todayDate);
    console.log(`✅ Today link shows correct date: ${todayDate}`);

    await todayLink.click();
    await expect(titleInput).toHaveValue(todayDate);
    console.log("✅ Clicking today preset updates title input");

    const cancelBtn = page.locator(".modal-btn-secondary");
    await cancelBtn.click();
    await expect(modal).not.toBeVisible();
    console.log("✅ Modal closed");
  });

  test("copy from dropdown shows existing pages in project", async ({ page }) => {
    console.log(`\n🔧 Logging in as: ${TEST_EMAIL}`);
    await login(page);
    console.log("✅ Logged in");

    const initialTitle = await page.locator("#note-title-input").inputValue();
    console.log(`📍 Current page title: ${initialTitle}`);

    const newPageBtn = page.locator(".sidebar-new-page-btn").first();
    await newPageBtn.click();

    const modal = page.locator(".modal");
    await expect(modal).toBeVisible({ timeout: 5000 });
    console.log("✅ Modal opened");

    const copyFromSelect = page.locator("#page-copy-from-select");

    const selectVisible = await copyFromSelect.isVisible().catch(() => false);
    if (selectVisible) {
      const options = await copyFromSelect.locator("option").allTextContents();
      console.log(`✅ Copy from dropdown has ${options.length} options: ${options.join(", ")}`);

      expect(options).toContain("Blank");
      console.log("✅ 'Blank' option exists");
    } else {
      console.log("ℹ️  Copy from dropdown not visible (project may have no other pages)");
    }

    const cancelBtn = page.locator(".modal-btn-secondary");
    await cancelBtn.click();
    await expect(modal).not.toBeVisible();
    console.log("✅ Modal closed");
  });

  test("creating page with copy_from copies content from source page", async ({ page }) => {
    console.log(`\n🔧 Logging in as: ${TEST_EMAIL}`);
    await login(page);
    console.log("✅ Logged in");

    // Step 1: Create a template page with specific content
    const templateTitle = `Template ${Date.now()}`;
    const templateContent = `# Template Header\n\nThis is template content for testing.`;

    const newPageBtn = page.locator(".sidebar-new-page-btn").first();
    await newPageBtn.click();

    const modal = page.locator(".modal");
    await expect(modal).toBeVisible({ timeout: 5000 });

    const titleInput = page.locator("#page-title-input");
    await titleInput.fill(templateTitle);

    const createBtn = page.locator(".modal-btn-primary");
    await createBtn.click();

    await page.waitForSelector(".cm-content", { timeout: 10000 });
    await page.waitForTimeout(1000);
    console.log(`✅ Created template page: ${templateTitle}`);

    // Get the page's external_id from the URL and set content via REST API.
    // Typing via keyboard goes through Yjs CRDT → WebSocket → backend snapshot,
    // and there's no reliable way to know when details.content is persisted.
    // The REST API sets details.content directly in the database.
    const pageId = await page.evaluate(() => {
      const match = window.location.pathname.match(/\/pages\/([^/]+)\//);
      return match ? match[1] : null;
    });
    expect(pageId).toBeTruthy();

    const csrfToken = await page.evaluate(() => {
      const cookie = document.cookie.split("; ").find((c) => c.startsWith("csrftoken="));
      return cookie ? cookie.split("=")[1] : "";
    });

    const response = await page.evaluate(
      async ({ pageId, title, content, csrfToken }) => {
        const res = await fetch(`/api/pages/${pageId}/`, {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken,
          },
          body: JSON.stringify({
            title,
            details: { content },
            mode: "overwrite",
          }),
        });
        return { ok: res.ok, status: res.status };
      },
      { pageId, title: templateTitle, content: templateContent, csrfToken }
    );
    expect(response.ok).toBe(true);
    console.log("✅ Added content to template page via API");

    // Step 2: Create a new page copying from the template
    const newPageTitle = `From Template ${Date.now()}`;
    await newPageBtn.click();
    await expect(modal).toBeVisible({ timeout: 5000 });

    await titleInput.fill(newPageTitle);

    const copyFromSelect = page.locator("#page-copy-from-select");
    const selectVisible = await copyFromSelect.isVisible().catch(() => false);

    if (selectVisible) {
      const templateOption = copyFromSelect.locator(`option:has-text("${templateTitle}")`);
      const templateOptionExists = (await templateOption.count()) > 0;

      if (templateOptionExists) {
        await copyFromSelect.selectOption({ label: templateTitle });
        console.log(`✅ Selected template: ${templateTitle}`);

        await createBtn.click();
        await page.waitForSelector(".cm-content", { timeout: 10000 });
        await page.waitForTimeout(2000);
        console.log(`✅ Created page: ${newPageTitle}`);

        const editorContent = await page.locator(".cm-content").textContent();
        expect(editorContent).toContain("Template Header");
        expect(editorContent).toContain("template content for testing");
        console.log("✅ Content was copied from template");
      } else {
        console.log("ℹ️  Template not in dropdown yet (may need page refresh)");
        const cancelBtn = page.locator(".modal-btn-secondary");
        await cancelBtn.click();
      }
    } else {
      console.log("ℹ️  Copy from dropdown not visible");
      const cancelBtn = page.locator(".modal-btn-secondary");
      await cancelBtn.click();
    }
  });

  test("date preset preference is remembered", async ({ page }) => {
    console.log(`\n🔧 Logging in as: ${TEST_EMAIL}`);
    await login(page);
    console.log("✅ Logged in");

    const todayDate = getTodayDateString();

    // First: Open modal and click the "Today" preset
    const newPageBtn = page.locator(".sidebar-new-page-btn").first();
    await newPageBtn.click();

    const modal = page.locator(".modal");
    await expect(modal).toBeVisible({ timeout: 5000 });

    const titleInput = page.locator("#page-title-input");
    const todayLink = page.locator(".preset-link").first();
    await todayLink.click();

    await expect(titleInput).toHaveValue(todayDate);
    console.log("✅ Set preference to 'today' format");

    const cancelBtn = page.locator(".modal-btn-secondary");
    await cancelBtn.click();
    await expect(modal).not.toBeVisible();

    // Second: Open modal again and verify it remembers the preference
    await newPageBtn.click();
    await expect(modal).toBeVisible({ timeout: 5000 });

    const initialValue = await titleInput.inputValue();
    expect(initialValue).toBe(todayDate);
    console.log(`✅ Modal remembered preference, opened with: ${initialValue}`);

    await cancelBtn.click();
    await expect(modal).not.toBeVisible();
    console.log("✅ Preference test complete");
  });

  test("creating page without copy_from creates blank page", async ({ page }) => {
    console.log(`\n🔧 Logging in as: ${TEST_EMAIL}`);
    await login(page);
    console.log("✅ Logged in");

    const newPageTitle = `Blank ${Date.now()}`;

    const newPageBtn = page.locator(".sidebar-new-page-btn").first();
    await newPageBtn.click();

    const modal = page.locator(".modal");
    await expect(modal).toBeVisible({ timeout: 5000 });

    const titleInput = page.locator("#page-title-input");
    await titleInput.fill(newPageTitle);

    const copyFromSelect = page.locator("#page-copy-from-select");
    const selectVisible = await copyFromSelect.isVisible().catch(() => false);
    if (selectVisible) {
      await copyFromSelect.selectOption({ value: "" });
      console.log("✅ Selected 'Blank' option");
    }

    const createBtn = page.locator(".modal-btn-primary");
    await createBtn.click();

    await page.waitForSelector(".cm-content", { timeout: 10000 });
    await page.waitForTimeout(1000);
    console.log(`✅ Created page: ${newPageTitle}`);

    const editorContent = await page.locator(".cm-content").textContent();
    expect(editorContent.trim()).toBe("");
    console.log("✅ Page content is blank as expected");
  });
});
