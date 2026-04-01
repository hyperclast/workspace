/**
 * Shared E2E test helpers.
 */

/**
 * Dismiss the Socrates floating panel if it's present.
 *
 * The Socratic feature (`WS_PRIVATE_FEATURES=socratic`) renders a fixed-position
 * panel at z-index 1000 that can intercept clicks on elements beneath it.
 * This helper hides it to prevent test interference.
 *
 * Call this after login/page load, before interacting with the UI.
 *
 * @param {import('@playwright/test').Page} page
 */
export async function dismissSocratesPanel(page) {
  await page.evaluate(() => {
    const panel = document.querySelector(".socrates-panel");
    if (panel) {
      panel.style.display = "none";
    }
  });
}

/**
 * Wait for the CodeMirror editor to contain expected text.
 * Works regardless of whether collab sync has completed — the app loads
 * content via REST first and upgrades to collaboration later.
 *
 * @param {import('@playwright/test').Page} page
 * @param {string} expectedText - Text that should appear in the editor
 * @param {number} [timeout=15000] - Maximum wait time in ms
 */
export async function waitForEditorContent(page, expectedText, timeout = 15000) {
  await page.waitForFunction(
    (expected) => (window.editorView?.state?.doc?.toString() || "").includes(expected),
    expectedText,
    { timeout }
  );
}

/**
 * Click a toolbar button by title, handling the case where the button
 * may have been moved to the overflow menu at narrower viewport widths.
 *
 * In the main toolbar, buttons have class="toolbar-btn" and a title attribute.
 * In the overflow menu, buttons don't have toolbar-btn class and their title
 * attribute is empty (only set when disabled). Instead, they have a <span>
 * child with the button's label text.
 *
 * @param {import('@playwright/test').Page} page
 * @param {string} title - The button's title attribute (e.g., 'Checklist (Cmd+L)')
 * @param {string} label - The button's label text in the overflow menu (e.g., 'Checklist')
 */
export async function clickToolbarButton(page, title, label) {
  // First, try to find the button in the main toolbar
  const mainBtn = page.locator(`button.toolbar-btn[title="${title}"]`);
  if (await mainBtn.isVisible()) {
    await mainBtn.click();
    return;
  }

  // Button is in the overflow menu — open it
  const overflowToggle = page.locator(
    '.toolbar-overflow > button.toolbar-btn[title="More options"]'
  );
  await overflowToggle.click();

  // Wait for the overflow menu to appear, then find the button by label text
  const overflowMenu = page.locator(".toolbar-overflow-menu");
  await overflowMenu.waitFor({ state: "visible", timeout: 3000 });

  const overflowBtn = overflowMenu.locator(`button:has(span:text-is("${label}"))`);
  await overflowBtn.click();
}
