const STORAGE_KEY = "hyperclast_recent_pages";
const MAX_RECENT = 10;

/**
 * Get the list of recently accessed pages from localStorage.
 *
 * Entries carry an `orgId` field so the command palette can show only
 * pages from the user's current org. Pre-org entries (no `orgId`) are
 * silently dropped on first read — the cost of a one-time miss is lower
 * than the risk of a cross-org leak.
 *
 * @returns {Array<{id: string, title: string, projectName: string, orgId: string, timestamp: number}>}
 */
export function getRecentPages() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) return [];
    const parsed = JSON.parse(stored);
    if (!Array.isArray(parsed)) return [];
    // Drop legacy entries that don't carry an org id. The user will see
    // their recent list rebuild as they revisit pages.
    return parsed.filter((p) => p && typeof p === "object" && p.orgId);
  } catch {
    return [];
  }
}

/**
 * Get recent pages filtered to a specific org. The command palette uses
 * this so the recent list never crosses the org boundary.
 * @param {string} orgId - The current org's external_id
 */
export function getRecentPagesForOrg(orgId) {
  if (!orgId) return [];
  return getRecentPages().filter((p) => p.orgId === orgId);
}

/**
 * Add a page to the recent pages list.
 * If the page already exists, it moves to the front.
 *
 * @param {string} pageId - The page's external_id
 * @param {string} title - The page title
 * @param {string} projectName - The project name
 * @param {string} orgId - The page's org external_id (required; calls
 *   without an orgId are dropped so the boundary stays enforceable).
 */
export function addRecentPage(pageId, title, projectName, orgId) {
  if (!orgId) return;
  // Filter out existing entry for this page
  const recent = getRecentPages().filter((p) => p.id !== pageId);
  // Add to front of list
  recent.unshift({ id: pageId, title, projectName, orgId, timestamp: Date.now() });
  // Keep only the most recent MAX_RECENT pages
  localStorage.setItem(STORAGE_KEY, JSON.stringify(recent.slice(0, MAX_RECENT)));
}

/**
 * Clear all recent pages.
 */
export function clearRecentPages() {
  localStorage.removeItem(STORAGE_KEY);
}
