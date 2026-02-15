/**
 * Breadcrumb Responsive Layout Test
 *
 * Tests that the breadcrumb row doesn't overflow/overlap at narrow viewport widths,
 * including when sidebars squeeze the content area. Also verifies that interactive
 * elements (Options dropdown, presence popover) remain functional at all sizes.
 *
 * Run with: npx playwright test breadcrumb-responsive.spec.js --headed
 */

import { test, expect } from "@playwright/test";
import { login } from "./visual-regression/fixtures.js";
import { dismissSocratesPanel } from "./helpers.js";

const BASE_URL = process.env.TEST_BASE_URL || "http://localhost:9800";

/**
 * Login and wait for the page shell to be ready (sidebar, header, toggle).
 * Does NOT require the collab WebSocket / CodeMirror editor to load.
 */
async function loginAndWaitForPageShell(page, baseUrl) {
  const url = baseUrl || BASE_URL;
  const email = process.env.TEST_EMAIL || "dev@localhost";
  const password = process.env.TEST_PASSWORD || "dev";

  await page.goto(`${url}/login`);
  await page.waitForSelector("#login-email", { timeout: 10000 });
  await page.fill("#login-email", email);
  await page.fill("#login-password", password);
  await page.click('button[type="submit"]');
  // Wait for the page shell — sidebar toggle is always visible now
  await page.waitForSelector("#sidebar-toggle", {
    state: "visible",
    timeout: 20000,
  });
}

test.describe("Breadcrumb Responsive Layout", () => {
  test.setTimeout(60000);

  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await login(page, BASE_URL);
    await dismissSocratesPanel(page);
    await page.waitForSelector("#breadcrumb-row", {
      state: "visible",
      timeout: 10000,
    });
  });

  test("breadcrumb row does not overflow at narrow widths", async ({ page }) => {
    const widths = [1280, 844, 640, 480, 390];
    for (const width of widths) {
      await page.setViewportSize({ width, height: 800 });
      await page.waitForTimeout(300);

      const overflow = await page.evaluate(() => {
        const row = document.querySelector(".breadcrumb-row");
        const breadcrumb = document.querySelector(".breadcrumb");
        const actions = document.querySelector(".breadcrumb-actions");
        if (!row || !breadcrumb || !actions) return { error: "missing elements" };

        const breadcrumbRect = breadcrumb.getBoundingClientRect();
        const actionsRect = actions.getBoundingClientRect();

        return {
          breadcrumbActionsOverlap: breadcrumbRect.right > actionsRect.left + 1,
          rowOverflowsContainer:
            row.getBoundingClientRect().right > row.parentElement.getBoundingClientRect().right + 1,
        };
      });

      expect(overflow.breadcrumbActionsOverlap, `At ${width}px: breadcrumb overlaps actions`).toBe(
        false
      );

      expect(overflow.rowOverflowsContainer, `At ${width}px: row overflows container`).toBe(false);
    }
  });

  test("Options dropdown opens and all items are accessible", async ({ page }) => {
    // Use a short viewport to test scrollability
    await page.setViewportSize({ width: 1020, height: 395 });
    await page.waitForTimeout(300);

    const actionsBtn = page.locator("#actions-btn");
    await actionsBtn.click();

    const dropdown = page.locator("#actions-dropdown");
    await expect(dropdown).toBeVisible({ timeout: 3000 });

    // Check that dropdown doesn't extend past viewport without being scrollable
    const dropdownInfo = await page.evaluate(() => {
      const dd = document.querySelector("#actions-dropdown");
      if (!dd) return null;
      const rect = dd.getBoundingClientRect();
      const style = window.getComputedStyle(dd);
      return {
        bottom: Math.round(rect.bottom),
        viewportHeight: window.innerHeight,
        overflowY: style.overflowY,
        exceedsViewport: rect.bottom > window.innerHeight,
      };
    });

    if (dropdownInfo.exceedsViewport) {
      expect(
        dropdownInfo.overflowY === "auto" || dropdownInfo.overflowY === "scroll",
        `Dropdown exceeds viewport (bottom: ${dropdownInfo.bottom}, viewport: ${dropdownInfo.viewportHeight}) but is not scrollable (overflow-y: ${dropdownInfo.overflowY})`
      ).toBe(true);
    }
  });

  test("collab-status popover opens on click and closes on click outside", async ({ page }) => {
    const collabWrapper = page.locator("#collab-status-wrapper");
    await collabWrapper.waitFor({ state: "attached", timeout: 10000 });

    // Click to open (simulates touch/tap)
    await collabWrapper.click();
    const popover = page.locator("#collab-popover");
    await expect(popover).toBeVisible({ timeout: 3000 });

    // Click outside — popover should close
    await page.locator("#editor").click({ force: true });
    await expect(popover).toBeHidden({ timeout: 3000 });
  });

  test("presence popover opens on click and closes on click outside", async ({ page }) => {
    const widths = [1280, 1020, 640];
    for (const width of widths) {
      await page.setViewportSize({ width, height: 800 });
      await page.waitForTimeout(300);

      const presence = page.locator("#presence-indicator");

      const isVisible = await presence.isVisible();
      expect(isVisible, `At ${width}px: presence indicator is not visible/clickable`).toBe(true);

      // Click to open (simulates touch/tap)
      await presence.click();

      const popover = page.locator("#presence-popover");
      await expect(popover).toBeVisible({ timeout: 3000 });

      // Click outside — popover should close
      await page.locator("#editor").click({ force: true });
      await expect(popover).toBeHidden({ timeout: 3000 });
    }
  });

  test("presence indicator shows compact count at narrow container width", async ({ page }) => {
    // At 844px with sidebars open, container is ~160px — triggers @container(max-width:400px)
    await page.setViewportSize({ width: 844, height: 800 });
    await page.waitForTimeout(300);

    const countInfo = await page.evaluate(() => {
      const span = document.getElementById("user-count");
      if (!span) return null;
      const style = window.getComputedStyle(span);
      const beforeStyle = window.getComputedStyle(span, "::before");
      return {
        dataCount: span.getAttribute("data-count"),
        fontSize: style.fontSize,
        beforeContent: beforeStyle.content,
      };
    });

    // The data-count attribute should be set
    expect(countInfo.dataCount).toBeTruthy();
    // When container query fires, the ::before shows the count
    if (countInfo.fontSize === "0px") {
      expect(countInfo.beforeContent).toContain(countInfo.dataCount);
    }
  });
});

test.describe("Sidebar Responsive Collapse", () => {
  test.setTimeout(60000);

  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await loginAndWaitForPageShell(page, BASE_URL);
  });

  test("sidebar toggle visible and collapses sidenav inline at desktop", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.waitForTimeout(300);

    const toggle = page.locator("#sidebar-toggle");
    const sidebar = page.locator("#note-sidebar");

    // Toggle should be visible at desktop
    await expect(toggle).toBeVisible();

    // Sidebar should be visible and not collapsed
    await expect(sidebar).toBeVisible();
    await expect(sidebar).not.toHaveClass(/collapsed/);

    // Click toggle — should collapse inline (not overlay)
    await toggle.click();
    await expect(sidebar).toHaveClass(/collapsed/);

    // Wait for CSS transition (width 0.2s ease) to finish
    await page.waitForTimeout(300);

    // Verify sidebar actually has zero width (not just the class)
    const collapsedWidth = await sidebar.evaluate((el) => el.getBoundingClientRect().width);
    expect(collapsedWidth).toBe(0);

    const overlay = page.locator("#sidebar-overlay");
    await expect(overlay).not.toHaveClass(/visible/);

    // Click toggle again — should expand
    await toggle.click();
    await expect(sidebar).not.toHaveClass(/collapsed/);

    // Wait for CSS transition to finish
    await page.waitForTimeout(300);

    // Verify sidebar expanded back to a visible width
    const expandedWidth = await sidebar.evaluate((el) => el.getBoundingClientRect().width);
    expect(expandedWidth).toBeGreaterThan(100);
  });

  test("sidebar uses overlay mode at 1024px and below", async ({ page }) => {
    await page.setViewportSize({ width: 1024, height: 800 });
    await page.waitForTimeout(300);

    const toggle = page.locator("#sidebar-toggle");
    const sidebar = page.locator("#note-sidebar");
    const overlay = page.locator("#sidebar-overlay");

    // Sidebar should be off-screen (not visible in layout)
    await expect(sidebar).not.toHaveClass(/open/);

    // Click toggle — should open as overlay
    await toggle.click();
    await expect(sidebar).toHaveClass(/open/);
    await expect(overlay).toHaveClass(/visible/);

    // Click overlay — should close sidebar
    await overlay.click();
    await expect(sidebar).not.toHaveClass(/open/);
    await expect(overlay).not.toHaveClass(/visible/);
  });

  test("sidebar overlay works at 844px with full-width content", async ({ page }) => {
    await page.setViewportSize({ width: 844, height: 800 });
    await page.waitForTimeout(300);

    const toggle = page.locator("#sidebar-toggle");
    const sidebar = page.locator("#note-sidebar");

    // Content area should be full-width when sidebar is closed
    const contentWidth = await page.evaluate(() => {
      const notePage = document.querySelector(".note-page");
      return notePage ? notePage.getBoundingClientRect().width : 0;
    });
    expect(contentWidth).toBeGreaterThan(800);

    // Toggle opens overlay
    await toggle.click();
    await expect(sidebar).toHaveClass(/open/);

    // Close via overlay
    const overlay = page.locator("#sidebar-overlay");
    await overlay.click();
    await expect(sidebar).not.toHaveClass(/open/);
  });
});
