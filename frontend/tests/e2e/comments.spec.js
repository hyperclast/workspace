/**
 * End-to-end tests for the comments feature.
 *
 * Tests critical comment flows:
 * 1. Create a comment via inline popover and verify anchor bar appears
 * 2. Reply to a comment and delete the root (cascade deletes reply too)
 * 3. Submitting oversized comment body shows error in popover
 * 4. Bidirectional click-to-scroll between sidebar and editor
 * 5. Bars persist after page reload
 * 6. Clicking a bar opens the sidebar to comments tab
 * 7. Arbitrary nesting: reply-to-reply via API + cascade delete
 *
 * Run with:
 *   npx playwright test comments.spec.js --headed
 *
 * To test with a different account:
 *   TEST_EMAIL=you@example.com TEST_PASSWORD=yourpass npx playwright test comments.spec.js --headed
 */

import { test, expect } from "@playwright/test";
import { dismissSocratesPanel, waitForEditorContent } from "./helpers.js";

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

/**
 * Create a new page with some content and return its external_id.
 */
async function createPageWithContent(page, title, content) {
  const newPageBtn = page.locator(".sidebar-new-page-btn").first();
  await newPageBtn.click();

  const modal = page.locator(".modal");
  await modal.waitFor({ state: "visible", timeout: 5000 });
  await page.locator("#page-title-input").fill(title);
  await page.locator(".modal-btn-primary").click();

  await page.waitForSelector(".sidebar-item.active", { timeout: 10000 });
  await page.waitForSelector(".cm-content", { timeout: 10000 });

  // Wait for page to be fully loaded (getCurrentPage is a function, not a property)
  const pageId = await page.evaluate(async (expectedTitle) => {
    for (let i = 0; i < 20; i++) {
      const cp = window.getCurrentPage?.();
      if (cp?.title === expectedTitle || cp?.details?.title === expectedTitle) {
        return cp.external_id;
      }
      await new Promise((r) => setTimeout(r, 250));
    }
    return window.getCurrentPage?.()?.external_id || "";
  }, title);

  // Type content into the editor
  await page.click(".cm-content");
  await page.keyboard.type(content);

  // Wait for typed content to appear in the editor
  await waitForEditorContent(page, content.substring(0, 30));

  return pageId;
}

/**
 * Open the Comments tab in the sidebar.
 */
async function openCommentsTab(page) {
  const commentsTab = page.locator('button.sidebar-tab[data-tab="comments"]');
  await commentsTab.click();
  // Wait for the tab content to be visible
  await page.waitForSelector(".comments-content", { timeout: 5000 });
}

/**
 * Select text in the CodeMirror editor by searching for it and setting the selection.
 */
async function selectTextInEditor(page, text) {
  await page.evaluate((textToSelect) => {
    const view = window.editorView;
    if (!view) throw new Error("editorView not available");

    const content = view.state.doc.toString();
    const idx = content.indexOf(textToSelect);
    if (idx === -1) throw new Error(`Text "${textToSelect}" not found in editor`);

    view.dispatch({
      selection: { anchor: idx, head: idx + textToSelect.length },
      scrollIntoView: true,
    });
    view.focus();
  }, text);
}

/**
 * Create an anchored comment via the inline popover.
 * Selects text, opens the popover, fills the body, and submits.
 */
async function createCommentViaPopover(page, textToSelect, commentBody) {
  await selectTextInEditor(page, textToSelect);

  const popoverBtn = page.locator(".cm-comment-popover-button button");
  await expect(popoverBtn).toBeVisible({ timeout: 5000 });
  await popoverBtn.click();

  const textarea = page.locator(".cm-comment-popover-textarea");
  await expect(textarea).toBeVisible({ timeout: 5000 });
  await textarea.fill(commentBody);

  await page.locator(".cm-comment-popover-submit").click();
}

test.describe("Comments", () => {
  test.setTimeout(120000);

  test("Cmd+Alt+M opens comment form when text is selected", async ({ page }) => {
    await login(page);
    console.log("Logged in");

    await createPageWithContent(
      page,
      `Shortcut Test ${Date.now()}`,
      "Text for keyboard shortcut test. Select this to comment."
    );
    console.log("Created page");

    await openCommentsTab(page);

    // Select text via JS
    await selectTextInEditor(page, "keyboard shortcut test");
    console.log("Text selected");

    // Press Cmd+Alt+M (Meta+Alt+m on Mac, Control+Alt+m elsewhere)
    const isMac = await page.evaluate(() => /Mac/.test(navigator.platform));
    const modifier = isMac ? "Meta" : "Control";
    await page.keyboard.press(`${modifier}+Alt+m`);
    console.log(`Pressed ${modifier}+Alt+M`);

    // The comment form textarea should appear
    const textarea = page.locator(".cm-comment-popover-textarea");
    await expect(textarea).toBeVisible({ timeout: 5000 });
    console.log("Comment form opened via shortcut");

    // Type a comment and submit with Cmd/Ctrl+Enter
    await textarea.fill("Comment via keyboard shortcut");
    await page.keyboard.press(`${modifier}+Enter`);

    // Comment card should appear in sidebar
    const commentCard = page.locator(".comment-card").first();
    await expect(commentCard).toBeVisible({ timeout: 10000 });
    const commentBody = commentCard.locator(".comment-body");
    await expect(commentBody).toContainText("Comment via keyboard shortcut");
    console.log("TEST PASSED: Cmd+Alt+M shortcut works end-to-end");
  });

  test("create comment with text selection shows anchor bar", async ({ page }) => {
    await login(page);
    console.log("Logged in");

    const pageId = await createPageWithContent(
      page,
      `Comment Test ${Date.now()}`,
      "This is a test paragraph for commenting. It has enough text to select a range."
    );
    console.log(`Created page: ${pageId}`);

    // Open comments tab
    await openCommentsTab(page);
    console.log("Comments tab open");

    // Verify empty state
    const emptyText = page.locator(".comments-empty-text");
    await expect(emptyText).toBeVisible({ timeout: 5000 });
    console.log("Empty state visible");

    // Create a comment via the inline popover
    await createCommentViaPopover(page, "test paragraph", "This is my first comment on this text.");
    console.log("Comment submitted via popover");

    // Wait for the comment card to appear in the sidebar
    const commentCard = page.locator(".comment-card").first();
    await expect(commentCard).toBeVisible({ timeout: 10000 });
    console.log("Comment card appeared");

    // Verify the comment body text
    const commentBody = commentCard.locator(".comment-body");
    await expect(commentBody).toContainText("This is my first comment on this text.");

    // Verify the anchor bar appears in the editor
    const anchorBar = page.locator(".cm-comment-bar");
    await expect(anchorBar).toBeVisible({ timeout: 5000 });
    console.log("Anchor bar visible in editor");

    // Verify the empty state is gone
    await expect(emptyText).not.toBeVisible();
    console.log("TEST PASSED: Comment created with anchor bar");
  });

  test("reply to comment and delete root cascades to reply", async ({ page }) => {
    await login(page);
    console.log("Logged in");

    const pageId = await createPageWithContent(
      page,
      `Delete Test ${Date.now()}`,
      "Some content for the delete cascade test. This text will be commented on."
    );
    console.log(`Created page: ${pageId}`);

    await openCommentsTab(page);

    // Create a root comment via the inline popover
    await createCommentViaPopover(page, "delete cascade test", "Root comment for delete test");

    // Wait for root comment to appear
    const rootCard = page.locator(".comment-card").first();
    await expect(rootCard).toBeVisible({ timeout: 10000 });
    console.log("Root comment created");

    // Click Reply button on the root comment
    const replyBtn = rootCard.locator(".comment-action-btn", { hasText: "Reply" });
    await replyBtn.click();

    // Type and submit a reply
    const replyTextarea = rootCard.locator(".comment-reply-input .comment-textarea");
    await expect(replyTextarea).toBeVisible({ timeout: 3000 });
    await replyTextarea.fill("This is a reply to the root comment");

    const replySubmitBtn = rootCard.locator(".comment-reply-input .comment-submit-btn");
    await replySubmitBtn.click();

    // Wait for the reply to appear
    const replyEl = page.locator(".comment-reply");
    await expect(replyEl).toBeVisible({ timeout: 10000 });
    console.log("Reply created");

    // Verify reply body
    const replyBody = replyEl.locator(".comment-body");
    await expect(replyBody).toContainText("This is a reply to the root comment");

    // Now delete the root comment (two clicks: first enters confirm state, second deletes)
    // Use > .comment-actions to target only the root's actions, not the reply's nested actions
    const deleteBtn = rootCard.locator("> .comment-actions .comment-action-delete");
    await deleteBtn.click();

    // Confirm the delete
    const confirmBtn = rootCard.locator("> .comment-actions .comment-action-confirm");
    await expect(confirmBtn).toBeVisible({ timeout: 3000 });
    await confirmBtn.click();

    // Wait for both root and reply to disappear (cascade delete)
    await expect(rootCard).not.toBeVisible({ timeout: 10000 });
    await expect(replyEl).not.toBeVisible({ timeout: 5000 });
    console.log("Root and reply both deleted (cascade)");

    // Verify we're back to the empty state
    const emptyText = page.locator(".comments-empty-text");
    await expect(emptyText).toBeVisible({ timeout: 5000 });
    console.log("TEST PASSED: Delete cascade works correctly");
  });

  test("submitting oversized comment body shows error in popover", async ({ page }) => {
    await login(page);
    console.log("Logged in");

    const pageId = await createPageWithContent(
      page,
      `Toast Error Test ${Date.now()}`,
      "Some content to anchor a comment to for the error handling test."
    );
    console.log(`Created page: ${pageId}`);

    await openCommentsTab(page);

    // Select text and open the popover form
    await selectTextInEditor(page, "anchor a comment");
    console.log("Text selected");

    const popoverBtn = page.locator(".cm-comment-popover-button button");
    await expect(popoverBtn).toBeVisible({ timeout: 5000 });
    await popoverBtn.click();

    const textarea = page.locator(".cm-comment-popover-textarea");
    await expect(textarea).toBeVisible({ timeout: 5000 });

    // Fill with a body that exceeds the 10,000-character backend limit
    const oversizedBody = "x".repeat(10_001);
    await textarea.fill(oversizedBody);

    // Submit the comment
    const submitBtn = page.locator(".cm-comment-popover-submit");
    await submitBtn.click();

    // Verify the popover's inline error message appears
    const errorEl = page.locator(".cm-comment-popover-error");
    await expect(errorEl).toContainText("Failed to post comment.", { timeout: 10000 });
    console.log("Popover error message appeared");

    // Verify no comment card was created
    const commentCard = page.locator(".comment-card");
    await expect(commentCard).not.toBeVisible({ timeout: 3000 });
    console.log("TEST PASSED: Oversized comment shows error in popover");
  });

  test("clicking comment card scrolls editor to anchor", async ({ page }) => {
    await login(page);
    console.log("Logged in");

    // Create a short page and add the comment while the popover fits in the viewport.
    const pageId = await createPageWithContent(
      page,
      `Scroll Test ${Date.now()}`,
      "TARGET TEXT FOR SCROLL TEST"
    );
    console.log(`Created page: ${pageId}`);

    await openCommentsTab(page);

    // Create an anchored comment while the document is short (tooltip fits in viewport)
    await createCommentViaPopover(page, "TARGET TEXT FOR SCROLL TEST", "Scroll test comment");

    // Wait for comment card in sidebar
    const commentCard = page.locator(".comment-card").first();
    await expect(commentCard).toBeVisible({ timeout: 10000 });
    console.log("Comment card visible");

    // Now insert bulk content BEFORE the target to push it below the viewport.
    // Yjs RelativePositions survive content insertion above the anchor.
    await page.evaluate(() => {
      const view = window.editorView;
      const lines = Array.from({ length: 100 }, (_, i) => `Padding line ${i + 1}`);
      const bulk = lines.join("\n") + "\n";
      view.dispatch({
        changes: { from: 0, insert: bulk },
      });
    });

    // Wait for the debounced anchor re-resolution after content change (500ms debounce + margin)
    await page.waitForTimeout(1500);

    // Scroll editor to the very top — the anchor is now far below the viewport
    await page.evaluate(() => {
      const view = window.editorView;
      view.dispatch({ selection: { anchor: 0 }, scrollIntoView: true });
    });
    await page.waitForTimeout(300);

    // Click the comment card — editor should scroll to the anchor
    await commentCard.click();
    await page.waitForTimeout(500);

    // Verify the active comment bar is visible in the editor viewport
    const activeBar = page.locator(".cm-comment-bar-active");
    await expect(activeBar).toBeVisible({ timeout: 5000 });

    // Verify it's within the editor's visible area (not just in DOM buffer)
    const isInView = await page.evaluate(() => {
      const bar = document.querySelector(".cm-comment-bar-active");
      const scroller = document.querySelector(".cm-scroller");
      if (!bar || !scroller) return false;
      const barRect = bar.getBoundingClientRect();
      const scrollerRect = scroller.getBoundingClientRect();
      return barRect.top >= scrollerRect.top && barRect.bottom <= scrollerRect.bottom;
    });
    expect(isInView).toBe(true);
    console.log("TEST PASSED: Clicking comment card scrolls editor to anchor");
  });

  test("bars appear after page reload without opening comments tab", async ({ page }) => {
    await login(page);
    console.log("Logged in");

    const pageId = await createPageWithContent(
      page,
      `Reload Test ${Date.now()}`,
      "Reload test paragraph for comment persistence. This text will be anchored."
    );
    console.log(`Created page: ${pageId}`);

    // Open comments tab and create a comment so there's data in the DB
    await openCommentsTab(page);
    await createCommentViaPopover(
      page,
      "Reload test paragraph",
      "Comment that should survive reload"
    );

    const commentCard = page.locator(".comment-card").first();
    await expect(commentCard).toBeVisible({ timeout: 10000 });

    // Verify bar is present before reload
    await expect(page.locator(".cm-comment-bar")).toBeVisible({ timeout: 5000 });
    console.log("Bar visible before reload");

    // Switch away from comments tab before reload — simulates a user who
    // doesn't have comments tab open when they reload
    const askTab = page.locator('button.sidebar-tab[data-tab="ask"]');
    await askTab.click();
    await page.waitForTimeout(300);
    console.log("Switched to Ask tab before reload");

    // Reload the page
    await page.reload();
    await page.waitForSelector(".cm-content", { timeout: 20000 });
    console.log("Page reloaded, editor visible");

    // DO NOT open the comments tab — bars should appear automatically.
    // Bars require Yjs anchor resolution (which happens after collab sync),
    // so give a generous timeout instead of blocking on isCollabSynced.
    const anchorBar = page.locator(".cm-comment-bar");
    await expect(anchorBar).toBeVisible({ timeout: 30000 });
    console.log("TEST PASSED: Bars appear after reload without opening comments tab");
  });

  test("clicking bar opens sidebar to comments tab and highlights card", async ({ page }) => {
    await login(page);
    console.log("Logged in");

    const pageId = await createPageWithContent(
      page,
      `Bar Click Test ${Date.now()}`,
      "Text for bar click test. This paragraph will get a comment."
    );
    console.log(`Created page: ${pageId}`);

    // Open comments tab and create a comment so bars are loaded
    await openCommentsTab(page);
    await createCommentViaPopover(page, "bar click test", "Bar click test comment");

    const commentCard = page.locator(".comment-card").first();
    await expect(commentCard).toBeVisible({ timeout: 10000 });
    console.log("Comment card created");

    // Switch to a different tab (e.g., links) so sidebar is not on comments
    const linksTab = page.locator('button.sidebar-tab[data-tab="links"]');
    await linksTab.click();
    await page.waitForTimeout(500);

    // Verify we're NOT on comments tab
    const commentsContent = page.locator(".comments-content");
    await expect(commentsContent).not.toBeVisible();

    // Click on the line that has the comment bar
    const bar = page.locator(".cm-comment-bar");
    await expect(bar).toBeVisible({ timeout: 5000 });
    await bar.click();

    // Sidebar should switch to comments tab
    await expect(commentsContent).toBeVisible({ timeout: 5000 });
    console.log("Sidebar switched to comments tab after bar click");

    // The comment card should be highlighted as active
    const activeCard = page.locator(".comment-card-active");
    await expect(activeCard).toBeVisible({ timeout: 5000 });
    console.log("TEST PASSED: Bar click opens sidebar and highlights card");
  });

  test("arbitrary nesting: reply-to-reply via UI and cascade delete", async ({ page }) => {
    await login(page);
    console.log("Logged in");

    await createPageWithContent(
      page,
      `Nesting Test ${Date.now()}`,
      "Arbitrary nesting test content. This text will be commented on."
    );

    await openCommentsTab(page);

    // 1. Create root comment via UI popover
    await createCommentViaPopover(page, "nesting test", "Root comment");
    const commentCard = page.locator(".comment-card").first();
    await expect(commentCard).toBeVisible({ timeout: 10000 });
    console.log("Root comment created");

    // 2. Reply to root via UI (level 1)
    const rootReplyBtn = commentCard.locator("> .comment-actions .comment-action-btn", {
      hasText: "Reply",
    });
    await rootReplyBtn.click();
    const rootReplyTextarea = commentCard.locator("> .comment-reply-input .comment-textarea");
    await expect(rootReplyTextarea).toBeVisible({ timeout: 3000 });
    await rootReplyTextarea.fill("Level 1 reply");
    await commentCard.locator("> .comment-reply-input .comment-submit-btn").click();

    const level1Reply = commentCard.locator("> .comment-replies > .comment-reply").first();
    await expect(level1Reply).toBeVisible({ timeout: 10000 });
    await expect(level1Reply.locator("> .comment-body")).toContainText("Level 1 reply");
    console.log("Level 1 reply created via UI");

    // 3. Reply to level 1 reply via UI (level 2) — the key arbitrary nesting test
    const level1ReplyBtn = level1Reply.locator("> .comment-actions .comment-action-btn", {
      hasText: "Reply",
    });
    await expect(level1ReplyBtn).toBeVisible({ timeout: 3000 });
    await level1ReplyBtn.click();

    const level1ReplyTextarea = level1Reply.locator("> .comment-reply-input .comment-textarea");
    await expect(level1ReplyTextarea).toBeVisible({ timeout: 3000 });
    await level1ReplyTextarea.fill("Level 2 reply");
    await level1Reply.locator("> .comment-reply-input .comment-submit-btn").click();

    const level2Reply = level1Reply.locator("> .comment-replies > .comment-reply").first();
    await expect(level2Reply).toBeVisible({ timeout: 10000 });
    await expect(level2Reply.locator("> .comment-body")).toContainText("Level 2 reply");
    console.log("Level 2 reply created via UI (reply to reply)");

    // 4. Reply to level 2 reply via UI (level 3) — even deeper nesting
    const level2ReplyBtn = level2Reply.locator("> .comment-actions .comment-action-btn", {
      hasText: "Reply",
    });
    await expect(level2ReplyBtn).toBeVisible({ timeout: 3000 });
    await level2ReplyBtn.click();

    const level2ReplyTextarea = level2Reply.locator("> .comment-reply-input .comment-textarea");
    await expect(level2ReplyTextarea).toBeVisible({ timeout: 3000 });
    await level2ReplyTextarea.fill("Level 3 reply");
    await level2Reply.locator("> .comment-reply-input .comment-submit-btn").click();

    const level3Reply = level2Reply.locator("> .comment-replies > .comment-reply").first();
    await expect(level3Reply).toBeVisible({ timeout: 10000 });
    await expect(level3Reply.locator("> .comment-body")).toContainText("Level 3 reply");
    console.log("Level 3 reply created via UI (3 levels deep)");

    // 5. Verify all 3 levels are visible simultaneously
    await expect(commentCard.locator(".comment-reply")).toHaveCount(3);
    console.log("All 3 nested replies visible in the tree");

    // 6. Cascade delete: delete level 1 reply → should remove levels 2 and 3 too
    const deleteBtn = level1Reply.locator("> .comment-actions .comment-action-delete");
    await deleteBtn.click();
    const confirmBtn = level1Reply.locator("> .comment-actions .comment-action-confirm");
    await expect(confirmBtn).toBeVisible({ timeout: 3000 });
    await confirmBtn.click();

    // All replies should be gone
    await expect(commentCard.locator(".comment-reply")).toHaveCount(0, { timeout: 10000 });
    console.log("TEST PASSED: Arbitrary nesting via UI + cascade delete works");
  });
});
