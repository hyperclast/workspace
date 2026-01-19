const STORAGE_KEY = "hyperclast_recent_pages";
const MAX_RECENT = 10;

/**
 * Get the list of recently accessed pages from localStorage.
 * @returns {Array<{id: string, title: string, projectName: string, timestamp: number}>}
 */
export function getRecentPages() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
}

/**
 * Add a page to the recent pages list.
 * If the page already exists, it moves to the front.
 * @param {string} pageId - The page's external_id
 * @param {string} title - The page title
 * @param {string} projectName - The project name
 */
export function addRecentPage(pageId, title, projectName) {
  // Filter out existing entry for this page
  const recent = getRecentPages().filter((p) => p.id !== pageId);
  // Add to front of list
  recent.unshift({ id: pageId, title, projectName, timestamp: Date.now() });
  // Keep only the most recent MAX_RECENT pages
  localStorage.setItem(STORAGE_KEY, JSON.stringify(recent.slice(0, MAX_RECENT)));
}

/**
 * Clear all recent pages.
 */
export function clearRecentPages() {
  localStorage.removeItem(STORAGE_KEY);
}
