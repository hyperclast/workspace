/**
 * End-to-end tests for the "Apply" button on AI comment suggestions.
 *
 * Tests:
 * 1. Apply button appears on AI comments, is clickable, and recovers from errors
 * 2. Apply button does NOT appear on human comments
 *
 * Run with:
 *   npx playwright test apply-suggestion.spec.js --headed
 */

import { test, expect } from "@playwright/test";
import { execSync } from "child_process";
import { dismissSocratesPanel } from "./helpers.js";

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
  await dismissSocratesPanel(page);
}

async function createPageWithContent(page, title, content) {
  const newPageBtn = page.locator(".sidebar-new-page-btn").first();
  await newPageBtn.click();

  const modal = page.locator(".modal");
  await modal.waitFor({ state: "visible", timeout: 5000 });
  await page.locator("#page-title-input").fill(title);
  await page.locator(".modal-btn-primary").click();

  await page.waitForSelector(".sidebar-item.active", { timeout: 10000 });
  await page.waitForSelector(".cm-content", { timeout: 10000 });

  // Extract page ID from URL: /pages/{external_id}/
  await page.waitForURL(/\/pages\/[A-Za-z0-9]+\//, { timeout: 10000 });
  const pageId = page.url().match(/\/pages\/([A-Za-z0-9]+)\//)?.[1] || "";

  await page.click(".cm-content");
  await page.keyboard.type(content);

  await page.waitForFunction(() => window.isCollabSynced?.() === true, {
    timeout: 15000,
  });

  return pageId;
}

async function openCommentsTab(page) {
  const commentsTab = page.locator('button.sidebar-tab[data-tab="comments"]');
  await commentsTab.click();
  await page.waitForSelector(".comments-content", { timeout: 5000 });
}

/**
 * Create an AI comment via Django shell in Docker (bypasses API schema limits).
 */
function createAIComment(pageId, anchorText, body, persona = "dewey") {
  const cmd = `docker exec backend-workspace-internal-9800-ws-web-1 python manage.py shell -c "
from pages.models import Page, Comment
page = Page.objects.get(external_id='${pageId}')
Comment.objects.create(page=page, ai_persona='${persona}', anchor_text='''${anchorText}''', body='''${body}''')
print('OK')
"`;
  const result = execSync(cmd, { encoding: "utf-8", timeout: 15000 });
  if (!result.includes("OK")) {
    throw new Error(`Failed to create AI comment: ${result}`);
  }
}

test.describe("Apply AI Suggestion", () => {
  test.setTimeout(120000);

  test("Apply button appears on AI comments and recovers from errors", async ({ page }) => {
    // Collect console errors
    const consoleErrors = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });
    page.on("pageerror", (err) => consoleErrors.push(err.message));

    await login(page);
    console.log("Logged in");

    const content =
      "The exploration of hyperparameter spaces is prohibitively expensive. " +
      "No systematic pruning method exists for this problem.";
    const pageId = await createPageWithContent(page, `Apply Test ${Date.now()}`, content);
    console.log("Created page:", pageId);

    await openCommentsTab(page);
    console.log("Comments tab open");

    // Ensure we have a valid pageId
    expect(pageId).toBeTruthy();

    // Create an AI comment via Django shell
    const anchorText = "No systematic pruning method exists";
    const commentBody =
      "Consider looking into BOHB (Bayesian Optimization + HyperBand) " +
      "for systematic hyperparameter pruning.";

    createAIComment(pageId, anchorText, commentBody, "dewey");
    console.log("AI comment created via Django shell");

    // Navigate to the page directly to trigger a fresh load with comments
    await page.goto(`${BASE_URL}/pages/${pageId}/`);
    await page.waitForSelector(".cm-content", { timeout: 20000 });
    await page.waitForFunction(() => window.isCollabSynced?.() === true, {
      timeout: 15000,
    });
    await dismissSocratesPanel(page);
    await openCommentsTab(page);
    await page.waitForTimeout(2000);

    // Verify AI comment card with badge is visible
    const aiBadge = page.locator(".comment-ai-badge").first();
    await expect(aiBadge).toBeVisible({ timeout: 10000 });
    console.log("AI comment card visible");

    // The Apply button should be visible
    const applyBtn = page.locator("button.comment-action-btn", { hasText: "Apply" }).first();
    await expect(applyBtn).toBeVisible({ timeout: 5000 });
    console.log("Apply button visible");

    // Click Apply
    await applyBtn.click();
    console.log("Clicked Apply button");

    // Wait for the API call to complete (will fail since no AI key in test)
    await page.waitForTimeout(3000);

    // Button should still be visible and functional (reset after error)
    await expect(applyBtn).toBeVisible();
    await expect(applyBtn).toContainText("Apply");
    console.log("Button still visible after API call");

    // Log any console errors for debugging
    if (consoleErrors.length > 0) {
      console.log("Console errors:", consoleErrors.join("; ").slice(0, 200));
    }

    console.log("TEST PASSED: Apply button visible, clickable, and recovers from errors");
  });

  test("Apply button does NOT appear on human comments", async ({ page }) => {
    await login(page);
    console.log("Logged in");

    const content = "Some text for human comment testing.";
    await createPageWithContent(page, `Human Comment ${Date.now()}`, content);

    // Extract page ID from URL
    await page.waitForURL(/\/pages\/[A-Za-z0-9]+\//, { timeout: 10000 });
    const pageId2 = page.url().match(/\/pages\/([A-Za-z0-9]+)\//)?.[1] || "";
    expect(pageId2).toBeTruthy();

    // Create a human comment via API
    await page.evaluate(async (externalId) => {
      const csrfToken = document.cookie
        .split("; ")
        .find((c) => c.startsWith("csrftoken="))
        ?.split("=")[1];

      await fetch(`/api/v1/pages/${externalId}/comments/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify({
          body: "A human comment",
          anchor_text: "human comment testing",
        }),
      });
    }, pageId2);

    // Navigate to page to reload with comment
    await page.goto(`${BASE_URL}/pages/${pageId2}/`);
    await page.waitForSelector(".cm-content", { timeout: 20000 });
    await dismissSocratesPanel(page);
    await openCommentsTab(page);
    await page.waitForTimeout(2000);

    // Human comment card should be visible
    const commentCard = page.locator(".comment-card").first();
    await expect(commentCard).toBeVisible({ timeout: 10000 });
    console.log("Human comment card visible");

    // Apply button should NOT be visible on human comments
    const applyBtn = page.locator("button.comment-action-btn", { hasText: "Apply" });
    await expect(applyBtn).toHaveCount(0);
    console.log("TEST PASSED: Apply button not shown on human comments");
  });
});
