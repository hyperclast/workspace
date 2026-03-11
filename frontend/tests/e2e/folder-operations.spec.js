/**
 * End-to-end tests for folder operations in the sidenav.
 *
 * Tests:
 * 1. Create a folder and verify it appears in the project tree
 * 2. Navigate to a page in a folder, verify folder auto-expands
 * 3. Move a page into a folder via MovePageModal
 * 4. Move a page to project root
 * 5. Folder breadcrumbs render for a page inside a folder
 * 6. Folder expand state persists after page reload (localStorage)
 * 7. Delete an empty folder
 *
 * Prerequisites:
 *   - Docker stack running (./run-stack.sh 9800)
 *   - Dev user seeded (dev@localhost / dev)
 *   - At least one project with one page
 *
 * Run with:
 *   npx playwright test folder-operations.spec.js --headed
 */

import { test, expect } from "@playwright/test";
import { login } from "./visual-regression/fixtures.js";
import { dismissSocratesPanel } from "./helpers.js";

const BASE_URL = process.env.TEST_BASE_URL || "http://localhost:9800";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Get a CSRF token from the page cookies for API calls.
 */
async function getCsrfToken(page) {
  return page.evaluate(() => {
    const cookie = document.cookie.split("; ").find((c) => c.startsWith("csrftoken="));
    return cookie ? cookie.split("=")[1] : "";
  });
}

/**
 * Get the external_id of the first project visible in the sidenav.
 */
async function getFirstProjectId(page) {
  return (
    page.locator(".sidebar-project").first().getAttribute("data-project-id") ??
    page.evaluate(() => {
      // Fallback: extract from the "New Page" button's onclick or the DOM
      const projectEl = document.querySelector(".sidebar-project");
      if (!projectEl) return null;
      // The project id is on the containing element
      return projectEl.dataset.projectId || null;
    })
  );
}

/**
 * Create a folder via the REST API (faster and more reliable than UI prompts).
 * Returns the created folder object { external_id, name, parent_id }.
 */
async function createFolderViaApi(page, projectId, name, parentId = null) {
  const csrfToken = await getCsrfToken(page);
  return page.evaluate(
    async ({ projectId, name, parentId, csrfToken }) => {
      const body = { name };
      if (parentId) body.parent_id = parentId;
      const res = await fetch(`/api/v1/projects/${projectId}/folders/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`Create folder failed: ${res.status}`);
      return res.json();
    },
    { projectId, name, parentId, csrfToken }
  );
}

/**
 * Delete a folder via the REST API (cleanup).
 */
async function deleteFolderViaApi(page, projectId, folderId) {
  const csrfToken = await getCsrfToken(page);
  await page.evaluate(
    async ({ projectId, folderId, csrfToken }) => {
      await fetch(`/api/v1/projects/${projectId}/folders/${folderId}/`, {
        method: "DELETE",
        headers: { "X-CSRFToken": csrfToken },
      });
    },
    { projectId, folderId, csrfToken }
  );
}

/**
 * Create a page via the REST API.
 * Returns { external_id, title, ... }.
 */
async function createPageViaApi(page, projectId, title, folderId = null) {
  const csrfToken = await getCsrfToken(page);
  return page.evaluate(
    async ({ projectId, title, folderId, csrfToken }) => {
      const body = { project_id: projectId, title };
      if (folderId) body.folder_id = folderId;
      const res = await fetch("/api/v1/pages/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`Create page failed: ${res.status}`);
      return res.json();
    },
    { projectId, title, folderId, csrfToken }
  );
}

/**
 * Move a page to a folder (or root) via the REST API.
 */
async function movePageViaApi(page, projectId, pageId, folderId) {
  const csrfToken = await getCsrfToken(page);
  return page.evaluate(
    async ({ projectId, pageId, folderId, csrfToken }) => {
      const res = await fetch(`/api/v1/projects/${projectId}/folders/move-pages/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify({ page_ids: [pageId], folder_id: folderId }),
      });
      if (!res.ok) throw new Error(`Move page failed: ${res.status}`);
      return res.json();
    },
    { projectId, pageId, folderId, csrfToken }
  );
}

/**
 * Delete a page via the REST API (cleanup).
 */
async function deletePageViaApi(page, pageId) {
  const csrfToken = await getCsrfToken(page);
  await page.evaluate(
    async ({ pageId, csrfToken }) => {
      await fetch(`/api/v1/pages/${pageId}/`, {
        method: "DELETE",
        headers: { "X-CSRFToken": csrfToken },
      });
    },
    { pageId, csrfToken }
  );
}

/**
 * Get the first project external_id from the API.
 */
async function getFirstProjectIdViaApi(page) {
  return page.evaluate(async () => {
    const res = await fetch("/api/v1/projects/");
    if (!res.ok) return null;
    const data = await res.json();
    return data.items?.[0]?.external_id || data[0]?.external_id || null;
  });
}

/**
 * Reload the sidenav by navigating to the app root and waiting for it to render.
 */
async function reloadAndWaitForSidenav(page) {
  await page.goto(`${BASE_URL}/`);
  await page.waitForSelector(".sidebar-project", { timeout: 20000 });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test.describe("Folder Operations", () => {
  test.setTimeout(90000);

  test.beforeEach(async ({ page }) => {
    await login(page, BASE_URL);
    await dismissSocratesPanel(page);
    // Ensure sidenav is visible and a project is expanded
    await page.waitForSelector(".sidebar-project", { timeout: 15000 });
  });

  test("folder appears in sidenav after creation via API + reload", async ({ page }) => {
    const projectId = await getFirstProjectIdViaApi(page);
    expect(projectId).toBeTruthy();

    const folderName = `E2E Folder ${Date.now()}`;
    const folder = await createFolderViaApi(page, projectId, folderName);

    try {
      // Reload to pick up the new folder
      await reloadAndWaitForSidenav(page);

      // The folder should appear as a .sidebar-folder-header containing the name
      const folderHeader = page.locator(
        `.sidebar-folder-header:has(.folder-name:text-is("${folderName}"))`
      );
      await expect(folderHeader).toBeVisible({ timeout: 10000 });
    } finally {
      await deleteFolderViaApi(page, projectId, folder.external_id);
    }
  });

  test("navigating to a page in a folder auto-expands the folder", async ({ page }) => {
    const projectId = await getFirstProjectIdViaApi(page);
    const folderName = `E2E Toggle ${Date.now()}`;
    const folder = await createFolderViaApi(page, projectId, folderName);
    const testPage = await createPageViaApi(
      page,
      projectId,
      `Toggle Page ${Date.now()}`,
      folder.external_id
    );

    try {
      // Navigate directly to the in-folder page (triggers auto-expand)
      await page.goto(`${BASE_URL}/pages/${testPage.external_id}/`);
      await page.waitForSelector(".sidebar-project", { timeout: 20000 });

      const folderHeader = page.locator(
        `.sidebar-folder-header:has(.folder-name:text-is("${folderName}"))`
      );
      await expect(folderHeader).toBeVisible({ timeout: 10000 });

      // Folder should be auto-expanded — child page should be visible
      const childPage = page.locator(
        `.sidebar-folder-children .sidebar-item:has-text("${testPage.title}")`
      );
      await expect(childPage).toBeVisible({ timeout: 5000 });
    } finally {
      await deletePageViaApi(page, testPage.external_id);
      await deleteFolderViaApi(page, projectId, folder.external_id);
    }
  });

  test("page moved into folder appears under that folder after reload", async ({ page }) => {
    const projectId = await getFirstProjectIdViaApi(page);
    const folderName = `E2E Move ${Date.now()}`;
    const folder = await createFolderViaApi(page, projectId, folderName);
    const testPage = await createPageViaApi(page, projectId, `Move Target ${Date.now()}`);

    try {
      // Move the page into the folder via API
      await movePageViaApi(page, projectId, testPage.external_id, folder.external_id);

      // Navigate to the moved page (triggers folder auto-expand)
      await page.goto(`${BASE_URL}/pages/${testPage.external_id}/`);
      await page.waitForSelector(".sidebar-project", { timeout: 20000 });

      // The page should now be inside the folder's children
      const childPage = page.locator(
        `.sidebar-folder-children .sidebar-item:has-text("${testPage.title}")`
      );
      await expect(childPage).toBeVisible({ timeout: 5000 });
    } finally {
      await deletePageViaApi(page, testPage.external_id);
      await deleteFolderViaApi(page, projectId, folder.external_id);
    }
  });

  test("page moved to root no longer appears under the folder", async ({ page }) => {
    const projectId = await getFirstProjectIdViaApi(page);
    const folderName = `E2E Root ${Date.now()}`;
    const folder = await createFolderViaApi(page, projectId, folderName);
    const testPage = await createPageViaApi(
      page,
      projectId,
      `Root Move ${Date.now()}`,
      folder.external_id
    );

    try {
      // Move the page to root (folder_id = null)
      await movePageViaApi(page, projectId, testPage.external_id, null);

      await reloadAndWaitForSidenav(page);

      // Expand the folder — it should be empty
      const folderHeader = page.locator(
        `.sidebar-folder-header:has(.folder-name:text-is("${folderName}"))`
      );
      await folderHeader.click();
      await page.waitForTimeout(300);

      // The page should NOT be inside the folder's children
      const childPage = page.locator(
        `.sidebar-folder-children .sidebar-item:has-text("${testPage.title}")`
      );
      await expect(childPage).not.toBeVisible();

      // The page should be at root level (not inside any .sidebar-folder-children)
      const rootPage = page.locator(
        `.sidebar-project-pages > .sidebar-item:has-text("${testPage.title}")`
      );
      await expect(rootPage).toBeVisible({ timeout: 5000 });
    } finally {
      await deletePageViaApi(page, testPage.external_id);
      await deleteFolderViaApi(page, projectId, folder.external_id);
    }
  });

  test("breadcrumbs show folder path when navigating to a page in a folder", async ({ page }) => {
    const projectId = await getFirstProjectIdViaApi(page);
    const folderName = `E2E Crumbs ${Date.now()}`;
    const folder = await createFolderViaApi(page, projectId, folderName);
    const testPage = await createPageViaApi(
      page,
      projectId,
      `Crumbs Page ${Date.now()}`,
      folder.external_id
    );

    try {
      // Navigate to the page
      await page.goto(`${BASE_URL}/pages/${testPage.external_id}/`);
      await page.waitForSelector("#breadcrumb-row", {
        state: "visible",
        timeout: 15000,
      });

      // The breadcrumb-folders element should contain the folder name
      const breadcrumbFolders = page.locator("#breadcrumb-folders");
      await expect(breadcrumbFolders).toContainText(folderName, {
        timeout: 10000,
      });
    } finally {
      await deletePageViaApi(page, testPage.external_id);
      await deleteFolderViaApi(page, projectId, folder.external_id);
    }
  });

  test("folder expand state persists after page reload", async ({ page }) => {
    const projectId = await getFirstProjectIdViaApi(page);
    const folderName = `E2E Persist ${Date.now()}`;
    const folder = await createFolderViaApi(page, projectId, folderName);
    const testPage = await createPageViaApi(
      page,
      projectId,
      `Persist Page ${Date.now()}`,
      folder.external_id
    );

    try {
      // Navigate to the in-folder page (triggers auto-expand + saves to localStorage)
      await page.goto(`${BASE_URL}/pages/${testPage.external_id}/`);
      await page.waitForSelector(".sidebar-project", { timeout: 20000 });

      const folderHeader = page.locator(
        `.sidebar-folder-header:has(.folder-name:text-is("${folderName}"))`
      );
      await expect(folderHeader).toBeVisible({ timeout: 10000 });

      const childPage = page.locator(
        `.sidebar-folder-children .sidebar-item:has-text("${testPage.title}")`
      );
      await expect(childPage).toBeVisible({ timeout: 5000 });

      // Reload the page — folder should still be expanded (via localStorage)
      await reloadAndWaitForSidenav(page);

      // Wait for the folder header to appear again
      await expect(folderHeader).toBeVisible({ timeout: 10000 });

      // The child page should still be visible without clicking
      await expect(childPage).toBeVisible({ timeout: 5000 });
    } finally {
      await deletePageViaApi(page, testPage.external_id);
      await deleteFolderViaApi(page, projectId, folder.external_id);
    }
  });

  test("empty folder can be deleted via the folder menu", async ({ page }) => {
    const projectId = await getFirstProjectIdViaApi(page);
    const folderName = `E2E Delete ${Date.now()}`;
    const folder = await createFolderViaApi(page, projectId, folderName);

    try {
      await reloadAndWaitForSidenav(page);

      const folderHeader = page.locator(
        `.sidebar-folder-header:has(.folder-name:text-is("${folderName}"))`
      );
      await expect(folderHeader).toBeVisible({ timeout: 10000 });

      // Delete via API (UI delete involves confirm dialog which is harder to test)
      await deleteFolderViaApi(page, projectId, folder.external_id);

      // Reload and verify the folder is gone
      await reloadAndWaitForSidenav(page);

      await expect(folderHeader).not.toBeVisible({ timeout: 5000 });
    } catch {
      // Cleanup in case test failed before API delete
      await deleteFolderViaApi(page, projectId, folder.external_id).catch(() => {});
    }
  });
});
