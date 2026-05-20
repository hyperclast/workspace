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
 * Wait for the SPA to finish mounting the post-login landing page.
 *
 * The backend redirects authenticated users to their most-recently-modified
 * page, which can be either a markdown page (CodeMirror, `.cm-content`) or a
 * PDF page (PdfPageView, `.pdf-page-view`). Waiting on `.cm-content` alone
 * times out whenever the landing page happens to be a PDF, since PDF pages
 * never mount CodeMirror.
 *
 * This helper waits for `#editor`, then for either readiness marker, then
 * dismisses the Socrates panel so subsequent UI interactions aren't blocked.
 *
 * @param {import('@playwright/test').Page} page
 * @param {object} [opts]
 * @param {number} [opts.editorTimeout=20000] - Timeout for `#editor` to mount
 * @param {number} [opts.readyTimeout=10000] - Timeout for the readiness marker
 */
export async function waitForLoggedIn(page, opts = {}) {
  const { editorTimeout = 20000, readyTimeout = 10000 } = opts;
  await page.waitForSelector("#editor", { timeout: editorTimeout });
  await page.waitForSelector(".cm-content, .pdf-page-view", { timeout: readyTimeout });
  await dismissSocratesPanel(page);
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
 * Pick the external_id of a project that lives in the SPA's current org.
 *
 * Folder operations are project-scoped, but the sidenav is org-scoped:
 * after a root reload the SPA renders only projects in the user's current
 * org (resolved from `Profile.current_org` via the homepage redirect, or
 * from the open page's org via the page-canonical invariant). A folder
 * created in some other org is therefore invisible on a subsequent `/`
 * reload, even though `GET /api/v1/projects/` (no `?org_id=`) returns
 * projects across all orgs.
 *
 * Returns the external_id of the first project the user can access in the
 * current org. If none exists, creates one and seeds it with a placeholder
 * page so the homepage redirect (`_pick_homepage_target` Path 2: newest
 * accessible page in the current org) has a target inside this org — without
 * the placeholder, the redirect can fall through to Path 3 (newest page
 * anywhere) and re-land the SPA in a different workspace.
 *
 * @param {import('@playwright/test').Page} page
 * @returns {Promise<string>} project external_id in the current org
 */
export async function pickProjectIdInCurrentOrg(page) {
  return page.evaluate(async () => {
    const orgId = window._userState?.currentOrgId;
    if (!orgId) {
      throw new Error("pickProjectIdInCurrentOrg: window._userState.currentOrgId is unset");
    }

    const csrfCookie = document.cookie.split("; ").find((c) => c.startsWith("csrftoken="));
    const csrfToken = csrfCookie ? csrfCookie.split("=")[1] : "";

    const listRes = await fetch(`/api/v1/projects/?org_id=${encodeURIComponent(orgId)}`, {
      credentials: "same-origin",
    });
    if (!listRes.ok) {
      throw new Error(`List projects failed: ${listRes.status}`);
    }
    const projects = await listRes.json();
    const existing = projects?.[0]?.external_id;
    if (existing) return existing;

    const createProjectRes = await fetch("/api/v1/projects/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken,
      },
      credentials: "same-origin",
      body: JSON.stringify({
        org_id: orgId,
        name: `E2E Project ${Date.now()}`,
        description: "Auto-created by E2E pickProjectIdInCurrentOrg",
      }),
    });
    if (!createProjectRes.ok) {
      throw new Error(`Create project failed: ${createProjectRes.status}`);
    }
    const project = await createProjectRes.json();

    const seedPageRes = await fetch("/api/v1/pages/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken,
      },
      credentials: "same-origin",
      body: JSON.stringify({
        project_id: project.external_id,
        title: `E2E Anchor ${Date.now()}`,
      }),
    });
    if (!seedPageRes.ok) {
      throw new Error(`Create anchor page failed: ${seedPageRes.status}`);
    }

    return project.external_id;
  });
}

/**
 * Ensure the SPA's homepage redirect lands on a hydratable page in the
 * current org.
 *
 * `editor-init.spec.js` (and any other spec that asserts
 * `editorView.state.doc.length > 0` after login) needs the post-login
 * `/` redirect to resolve to a page whose `details.content` is
 * non-empty. The redirect (`_pick_homepage_target`) prefers
 * `Profile.org_state[<org>].last_page_id`, then newest-in-org, then
 * newest-anywhere — so a stale pointer left by a previous test's
 * `+ New Page` click can route the user to an empty `Untitled`
 * created with `details.content = ""`, which makes the doc-length
 * assertion never resolve.
 *
 * This helper creates a page with stable non-empty content in the
 * current org and writes its `external_id` into the user's per-org
 * `last_page_id` so Path 1 of the homepage redirect lands there on
 * the next `/` visit.
 *
 * Requires that the page is already authenticated (i.e., call this
 * after `waitForLoggedIn` or the inline login flow).
 *
 * @param {import('@playwright/test').Page} page
 * @returns {Promise<string>} the seeded page's external_id
 */
export async function ensureNonEmptyHomepageTarget(page) {
  const projectId = await pickProjectIdInCurrentOrg(page);

  return page.evaluate(async (projectExternalId) => {
    const orgId = window._userState?.currentOrgId;
    if (!orgId) {
      throw new Error("ensureNonEmptyHomepageTarget: window._userState.currentOrgId is unset");
    }

    const csrfCookie = document.cookie.split("; ").find((c) => c.startsWith("csrftoken="));
    const csrfToken = csrfCookie ? csrfCookie.split("=")[1] : "";

    const createRes = await fetch("/api/v1/pages/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken,
      },
      credentials: "same-origin",
      body: JSON.stringify({
        project_id: projectExternalId,
        title: `E2E editor-init seed ${Date.now()}`,
      }),
    });
    if (!createRes.ok) {
      throw new Error(`Create seed page failed: ${createRes.status}`);
    }
    const created = await createRes.json();

    const putRes = await fetch(`/api/v1/pages/${created.external_id}/`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken,
      },
      credentials: "same-origin",
      body: JSON.stringify({
        title: created.title,
        details: {
          content: "E2E editor-init seed body — non-empty so doc.length > 0.",
          filetype: "md",
          schema_version: 1,
        },
        mode: "overwrite",
      }),
    });
    if (!putRes.ok) {
      throw new Error(`Write seed page content failed: ${putRes.status}`);
    }

    const stateRes = await fetch(`/api/v1/users/me/org-state/${encodeURIComponent(orgId)}/`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken,
      },
      credentials: "same-origin",
      body: JSON.stringify({ last_page_id: created.external_id }),
    });
    if (!stateRes.ok) {
      throw new Error(`Update last_page_id failed: ${stateRes.status}`);
    }

    return created.external_id;
  }, projectId);
}

/**
 * Fetch projects (with nested pages and files) scoped to the SPA's current
 * org.
 *
 * `GET /api/v1/projects/?details=full` without `?org_id=` returns projects
 * across every org the user can access — intentional for token-based
 * scripts and the legacy command palette, but a footgun for E2E tests
 * that then try to click a returned page in the now-org-scoped sidenav.
 * If the page lives outside the SPA's current org the sidebar item never
 * renders and the click times out.
 *
 * This helper narrows the fetch to the current org so the result set
 * matches what the sidenav actually displays.
 *
 * @param {import('@playwright/test').Page} page
 * @returns {Promise<Array>} projects with `pages` (and `files`) arrays
 */
export async function fetchProjectsInCurrentOrg(page) {
  return page.evaluate(async () => {
    const orgId = window._userState?.currentOrgId;
    if (!orgId) {
      throw new Error("fetchProjectsInCurrentOrg: window._userState.currentOrgId is unset");
    }
    const resp = await fetch(`/api/v1/projects/?details=full&org_id=${encodeURIComponent(orgId)}`, {
      credentials: "same-origin",
    });
    if (!resp.ok) {
      throw new Error(`fetchProjectsInCurrentOrg: ${resp.status}`);
    }
    return resp.json();
  });
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
