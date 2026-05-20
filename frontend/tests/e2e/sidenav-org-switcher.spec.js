/**
 * Sidenav org switcher regression test.
 *
 * Locks in the behavior of the organization picker that replaced the static
 * WORKSPACE label at the top of the sidenav:
 *
 *   - The trigger renders with the current org's name (resolved by the
 *     server-injected `window._userState.currentOrgId` — which for a
 *     `/pages/<id>/` route is the page's org).
 *   - Clicking the trigger opens a popover with the org list and a
 *     "New organization" action.
 *   - The popover dismisses on outside click and Escape.
 *
 * Note: the previous version of this spec asserted
 * `localStorage["current-org-id"]` values. That key was removed when we
 * made "the open page IS the current org" the canonical invariant — the
 * SPA template now injects `window._userState.currentOrgId` per request
 * and there's no client-side mirror.
 *
 * Run with:
 *   npx playwright test sidenav-org-switcher.spec.js --reporter=list
 */

import { test, expect } from "@playwright/test";
import { BASE_URL, login } from "./_helpers/orgSwitch.js";

test.describe("Sidenav org switcher", () => {
  test("trigger renders with the resolved current org, popover lists orgs + create row", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await login(page);

    const trigger = page.locator(".org-switcher-trigger");
    await expect(trigger).toBeVisible({ timeout: 10000 });

    // Closed: no popover yet. The server has injected currentOrgId (it's
    // the org of the page we just navigated to via the homepage redirect).
    await expect(page.locator(".org-switcher-popover")).toHaveCount(0);
    const injectedOrgId = await page.evaluate(() => window._userState?.currentOrgId);
    expect(injectedOrgId).toBeTruthy();

    // The trigger label should be non-empty (uppercase via CSS, but textContent
    // is the org's actual mixed-case name).
    const triggerText = (await trigger.textContent()).trim();
    expect(triggerText.length).toBeGreaterThan(0);

    // Open the popover
    await trigger.click();
    const popover = page.locator(".org-switcher-popover");
    await expect(popover).toBeVisible();

    // At least one org row (radio-style) with one marked active
    const items = page.locator(".org-switcher-item:not(.org-switcher-create)");
    await expect(items.first()).toBeVisible();
    const active = page.locator(".org-switcher-item.active");
    await expect(active).toHaveCount(1);

    // The create row is present
    await expect(page.locator(".org-switcher-create")).toBeVisible();
  });

  test("popover dismisses on outside click and Escape", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await login(page);
    const trigger = page.locator(".org-switcher-trigger");
    await expect(trigger).toBeVisible({ timeout: 10000 });

    // Outside click closes
    await trigger.click();
    await expect(page.locator(".org-switcher-popover")).toBeVisible();
    await page.locator("#editor-container").click({ position: { x: 200, y: 200 } });
    await expect(page.locator(".org-switcher-popover")).toHaveCount(0);

    // Escape closes
    await trigger.click();
    await expect(page.locator(".org-switcher-popover")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.locator(".org-switcher-popover")).toHaveCount(0);
  });

  test("clicking the create row opens the modal and Cancel dismisses it", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await login(page);
    await expect(page.locator(".org-switcher-trigger")).toBeVisible({ timeout: 10000 });

    await page.locator(".org-switcher-trigger").click();
    await page.locator(".org-switcher-create").click();

    const modal = page.locator(".modal");
    await expect(modal).toBeVisible();
    await expect(modal.locator('input[id="org-name-input"]')).toBeVisible();

    await modal.locator(".modal-btn-secondary").click();
    await expect(page.locator(".modal")).toHaveCount(0);
  });

  test("legacy localStorage current-org-id is silently cleared on load", async ({ page }) => {
    // The old store wrote a `current-org-id` key. We've since removed
    // client-side persistence of the current org — the open page is the
    // source of truth — and the store deletes the key on module init.
    // This test pins that cleanup so a residual value in a returning
    // user's browser can't accidentally drive behavior anymore.
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto(`${BASE_URL}/login`);
    await page.evaluate(() => localStorage.setItem("current-org-id", "stale-legacy-value"));
    await login(page);

    // After the SPA loads, the legacy key should be gone.
    const stillThere = await page.evaluate(() => localStorage.getItem("current-org-id"));
    expect(stillThere).toBeNull();

    // The trigger still renders correctly (driven by server inject).
    const trigger = page.locator(".org-switcher-trigger");
    await expect(trigger).toBeVisible();
    expect((await trigger.textContent()).trim().length).toBeGreaterThan(0);
  });

  test("selecting the active org closes the popover and leaves the trigger label intact", async ({
    page,
  }) => {
    // We can't safely create a second org in this test (would pollute the dev
    // DB), but we can still exercise the selection code path by clicking the
    // already-active row. The store skips its no-op update, the popover
    // closes, and the trigger stays put.
    await page.setViewportSize({ width: 1280, height: 900 });
    await login(page);
    const trigger = page.locator(".org-switcher-trigger");
    await expect(trigger).toBeVisible({ timeout: 10000 });

    const triggerBefore = (await trigger.textContent()).trim();

    await trigger.click();
    await page.locator(".org-switcher-item.active").click();

    await expect(page.locator(".org-switcher-popover")).toHaveCount(0);
    const triggerAfter = (await trigger.textContent()).trim();
    expect(triggerAfter).toBe(triggerBefore);
  });
});
