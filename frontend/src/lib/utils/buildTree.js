/**
 * Build a tree structure from flat folder and page arrays.
 *
 * @param {Array} folders - Flat array of { external_id, parent_id, name }
 * @param {Array} pages - Flat array of { external_id, folder_id, title, ... }
 * @returns {{ rootFolders: Array, rootPages: Array }}
 */
export function buildTree(folders, pages) {
  // 1. Index folders by external_id
  const folderMap = new Map(
    folders.map((f) => [f.external_id, { ...f, subfolders: [], pages: [] }])
  );

  // 2. Attach subfolders to parents
  for (const folder of folderMap.values()) {
    if (folder.parent_id) {
      const parent = folderMap.get(folder.parent_id);
      if (parent) parent.subfolders.push(folder);
    }
  }

  // 3. Attach pages to folders (or root)
  const rootPages = [];
  for (const page of pages) {
    if (page.folder_id) {
      const folder = folderMap.get(page.folder_id);
      if (folder) {
        folder.pages.push(page);
      } else {
        rootPages.push(page); // orphaned page, show at root
      }
    } else {
      rootPages.push(page);
    }
  }

  // 4. Sort: folders A-Z by name, pages A-Z by title
  const sortByName = (a, b) => a.name.localeCompare(b.name);
  const sortByTitle = (a, b) => (a.title || "").localeCompare(b.title || "");

  for (const folder of folderMap.values()) {
    folder.subfolders.sort(sortByName);
    folder.pages.sort(sortByTitle);
  }

  // 5. Top-level folders + root pages
  const rootFolders = folders
    .filter((f) => !f.parent_id)
    .map((f) => folderMap.get(f.external_id))
    .sort(sortByName);

  return { rootFolders, rootPages: rootPages.sort(sortByTitle), folderMap };
}

/**
 * Get the folder breadcrumb path for a page.
 * Returns an array of { external_id, name } from root to the page's folder.
 *
 * @param {string|null} folderId - The page's folder_id
 * @param {Map} folderMap - Map of folder external_id to folder objects (from buildTree)
 * @returns {Array<{ external_id: string, name: string }>}
 */
export function getFolderBreadcrumbs(folderId, folderMap) {
  if (!folderId || !folderMap) return [];

  const path = [];
  let current = folderMap.get(folderId);
  while (current) {
    path.unshift({ external_id: current.external_id, name: current.name });
    current = current.parent_id ? folderMap.get(current.parent_id) : null;
  }
  return path;
}
