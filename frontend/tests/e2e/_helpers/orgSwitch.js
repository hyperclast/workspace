/**
 * Shared helpers for org-related e2e specs.
 *
 * The three specs (org-boundary, profile-persistence, sidenav-org-switcher)
 * previously each defined their own login + switcher-ready helpers. This
 * module is the single home for them so a change to login flow or
 * switcher hydration is a one-place edit.
 */

export const BASE_URL = process.env.TEST_BASE_URL || "http://localhost:9800";
export const TEST_EMAIL = process.env.TEST_EMAIL || "dev@localhost";
export const TEST_PASSWORD = process.env.TEST_PASSWORD || "dev";

export async function login(page) {
  await page.goto(`${BASE_URL}/login`);
  await page.waitForSelector("#login-email", { timeout: 10000 });
  await page.fill("#login-email", TEST_EMAIL);
  await page.fill("#login-password", TEST_PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForSelector("#editor", { timeout: 20000 });
}

export async function waitForSwitcherReady(page) {
  await page.waitForSelector(".org-switcher-trigger", { timeout: 10000 });
  // hydrateOrgs() is async — wait for the trigger to have a non-empty label.
  await page.waitForFunction(
    () => {
      const t = document.querySelector(".org-switcher-trigger");
      return t && t.textContent && t.textContent.trim().length > 0;
    },
    null,
    { timeout: 10000 }
  );
}

export function uniqueOrgName(suffix) {
  return `T${Date.now().toString(36)}-${suffix}`;
}

/**
 * Create a brand-new org through the OrgSwitcher modal. Returns the new
 * org's external id (read from the live store rune after the create resolves).
 *
 * IMPORTANT: modal-close is the signal that POST /orgs/ succeeded, but
 * `handleCreated` then `await`s `fetchOrgs()` BEFORE calling
 * `setCurrentOrgId(newOrg.external_id)`. If we read `window._currentOrgId`
 * the instant the modal detaches we get the OLD org id and the rest of the
 * test races against the rune flip. Wait for the rune to actually change
 * before returning.
 */
export async function createOrgViaModal(page, name) {
  const prevOrgId = await page.evaluate(() => window._currentOrgId);
  await page.locator(".org-switcher-trigger").click();
  await page.locator(".org-switcher-create").click();
  await page.waitForSelector(".modal");
  await page.locator("input#org-name-input").fill(name);
  await page.locator(".modal-btn-primary").click();
  await page.waitForSelector(".modal", { state: "detached", timeout: 10000 });
  await page.waitForFunction(
    (prev) => window._currentOrgId && window._currentOrgId !== prev,
    prevOrgId,
    { timeout: 10000 }
  );
  return page.evaluate(() => window._currentOrgId);
}

/**
 * Read the live URL pathname from the page. We use this instead of
 * page.url() because the SPA navigates via history.pushState — page.url()
 * sometimes lags the actual location until a real navigation occurs.
 */
export async function getCurrentUrlPath(page) {
  return page.evaluate(() => window.location.pathname);
}
