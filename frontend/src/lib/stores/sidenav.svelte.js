/**
 * Sidenav store - manages project list state
 */

const STORAGE_KEY_EXPANDED = "expanded-project-ids";
const STORAGE_KEY_CURRENT_PROJECT_OLD = "current-project-id"; // For migration
const STORAGE_KEY_FILES_EXPANDED = "expanded-files-project-ids";
const STORAGE_KEY_FOLDERS_PREFIX = "folders:"; // Per-project folder expand state
const STORAGE_KEY_LAST_PAGE_PER_ORG = "last-page-per-org"; // { orgId: pageId } for org-switch resume
// One-time migration cleanup: an earlier version of this store wrote a
// per-tab `current-org-id` key to localStorage. The open page is now the
// canonical source of truth for the current org, so the key is gone.
// Clear any value lingering from before so it doesn't quietly mislead
// debuggers looking at storage.
try {
  localStorage.removeItem("current-org-id");
} catch {}

// Load expanded projects from localStorage (with migration from old format)
function loadExpandedProjects() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY_EXPANDED);
    if (stored) {
      return new Set(JSON.parse(stored));
    }
    // Migration: if new key doesn't exist but old does, use old ID
    const oldProjectId = localStorage.getItem(STORAGE_KEY_CURRENT_PROJECT_OLD);
    if (oldProjectId) {
      localStorage.removeItem(STORAGE_KEY_CURRENT_PROJECT_OLD);
      const migrated = new Set([oldProjectId]);
      localStorage.setItem(STORAGE_KEY_EXPANDED, JSON.stringify([...migrated]));
      return migrated;
    }
    return new Set();
  } catch {
    return new Set();
  }
}

// Load expanded files sections from localStorage
function loadExpandedFilesSections() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY_FILES_EXPANDED);
    if (stored) {
      return new Set(JSON.parse(stored));
    }
    return new Set();
  } catch {
    return new Set();
  }
}

// Load expanded folders for a project from localStorage
function loadExpandedFolders(projectId) {
  try {
    const stored = localStorage.getItem(STORAGE_KEY_FOLDERS_PREFIX + projectId);
    if (stored) {
      return new Set(JSON.parse(stored));
    }
    return new Set();
  } catch {
    return new Set();
  }
}

// Save expanded folders for a project to localStorage
function saveExpandedFolders(projectId) {
  const folderSet = expandedFolderIds[projectId];
  if (folderSet && folderSet.size > 0) {
    localStorage.setItem(STORAGE_KEY_FOLDERS_PREFIX + projectId, JSON.stringify([...folderSet]));
  } else {
    localStorage.removeItem(STORAGE_KEY_FOLDERS_PREFIX + projectId);
  }
}

// Reactive state
let projects = $state([]);
let activePageId = $state(null);
let expandedProjectIds = $state(loadExpandedProjects());
let expandedFilesSections = $state(loadExpandedFilesSections());
let expandedFolderIds = $state({}); // Map of projectId -> Set of expanded folder external_ids
let showFilesSection = $state(false);
let projectFiles = $state({}); // Map of projectId -> files array

// Callbacks (set from vanilla JS)
let onNavigate = null;
let onNewPage = null;
let onProjectDeleted = null;
let onProjectRenamed = null;

// Re-export org-context functions for callers still importing them from
// this module. Org context isn't UI state — see lib/orgContext.js — but
// re-exporting here keeps the migration small and avoids touching every
// import site at once.
export {
  getCurrentOrgId,
  getAvailableOrgs,
  setAvailableOrgs,
  setCurrentOrgId,
  setOrgChangedHandler,
} from "../orgContext.js";

// Computed: whether to show org names (multiple orgs)
function getShowOrgNames() {
  const orgIds = new Set(projects.map((p) => p.org?.external_id).filter(Boolean));
  return orgIds.size > 1;
}

// Helper to save expanded projects to localStorage
function saveExpandedProjects() {
  localStorage.setItem(STORAGE_KEY_EXPANDED, JSON.stringify([...expandedProjectIds]));
}

// Helper to save expanded files sections to localStorage
function saveExpandedFilesSections() {
  localStorage.setItem(STORAGE_KEY_FILES_EXPANDED, JSON.stringify([...expandedFilesSections]));
}

// Actions
export function setProjects(newProjects, newActivePageId = null) {
  projects = [...newProjects];
  activePageId = newActivePageId;

  // Extract files from projects into projectFiles map
  // Use empty array as default when files is null/undefined
  const newProjectFiles = {};
  for (const project of newProjects) {
    newProjectFiles[project.external_id] = project.files || [];
  }
  projectFiles = newProjectFiles;

  // Auto-expand project containing active page (without collapsing others)
  if (newActivePageId) {
    const activeProject = projects.find((p) =>
      p.pages?.some((page) => page.external_id === newActivePageId)
    );
    if (activeProject) {
      expandProject(activeProject.external_id);

      // Auto-expand folder chain containing the active page
      const activePage = activeProject.pages?.find((p) => p.external_id === newActivePageId);
      if (activePage?.folder_id && activeProject.folders?.length > 0) {
        const folderById = new Map(activeProject.folders.map((f) => [f.external_id, f]));
        let folderId = activePage.folder_id;
        while (folderId) {
          expandFolder(activeProject.external_id, folderId);
          const folder = folderById.get(folderId);
          folderId = folder?.parent_id || null;
        }
      }
    }
  }

  // If no projects are expanded and we have projects, expand the first one
  if (expandedProjectIds.size === 0 && projects.length > 0) {
    expandProject(projects[0].external_id);
  }

  // Load folder expand state for each project
  for (const project of newProjects) {
    ensureFolderStateLoaded(project.external_id);
  }
}

export function setActivePageId(pageId) {
  activePageId = pageId;
}

export function toggleProjectExpanded(projectId) {
  if (expandedProjectIds.has(projectId)) {
    expandedProjectIds.delete(projectId);
  } else {
    expandedProjectIds.add(projectId);
  }
  expandedProjectIds = new Set(expandedProjectIds); // trigger reactivity
  saveExpandedProjects();
}

export function expandProject(projectId) {
  if (!expandedProjectIds.has(projectId)) {
    expandedProjectIds.add(projectId);
    expandedProjectIds = new Set(expandedProjectIds); // trigger reactivity
    saveExpandedProjects();
  }
}

export function collapseProject(projectId) {
  if (expandedProjectIds.has(projectId)) {
    expandedProjectIds.delete(projectId);
    expandedProjectIds = new Set(expandedProjectIds); // trigger reactivity
    saveExpandedProjects();
  }
}

export function isProjectExpanded(projectId) {
  return expandedProjectIds.has(projectId);
}

export function getExpandedProjectIds() {
  return expandedProjectIds;
}

// Keep for backwards compatibility (used by sidenav.js bridge)
export function getCurrentProjectId() {
  // Return first expanded project or null
  return expandedProjectIds.size > 0 ? [...expandedProjectIds][0] : null;
}

// Keep for backwards compatibility
export function setCurrentProject(projectId) {
  expandProject(projectId);
}

export function navigateToPage(pageId, projectId) {
  if (projectId) {
    expandProject(projectId);
  }
  if (onNavigate) {
    onNavigate(pageId);
  }
}

export function createNewPage(projectId, folderId = null) {
  if (projectId) {
    expandProject(projectId);
  }
  if (onNewPage) {
    onNewPage(projectId, folderId);
  }
}

export function notifyProjectDeleted(projectId) {
  if (onProjectDeleted) {
    onProjectDeleted(projectId);
  }
}

export function updateProjectName(projectId, newName) {
  const project = projects.find((p) => p.external_id === projectId);
  if (project) {
    project.name = newName;
    // Trigger reactivity by reassigning
    projects = [...projects];
    // Notify main.js to update breadcrumb etc
    if (onProjectRenamed) {
      onProjectRenamed(projectId, newName);
    }
  }
}

export function updatePageAccessCode(pageId, accessCode) {
  for (const project of projects) {
    const page = project.pages?.find((p) => p.external_id === pageId);
    if (page) {
      page.access_code = accessCode;
      // Trigger reactivity by reassigning
      projects = [...projects];
      break;
    }
  }
}

// Callback setters (called from vanilla JS bridge)
export function setNavigateHandler(handler) {
  onNavigate = handler;
}

export function setNewPageHandler(handler) {
  onNewPage = handler;
}

export function setProjectDeletedHandler(handler) {
  onProjectDeleted = handler;
}

export function setProjectRenamedHandler(handler) {
  onProjectRenamed = handler;
}

// Files section management
export function setShowFilesSection(show) {
  showFilesSection = show;
}

export function getShowFilesSection() {
  return showFilesSection;
}

export function toggleFilesSectionExpanded(projectId) {
  if (expandedFilesSections.has(projectId)) {
    expandedFilesSections.delete(projectId);
  } else {
    expandedFilesSections.add(projectId);
  }
  expandedFilesSections = new Set(expandedFilesSections); // trigger reactivity
  saveExpandedFilesSections();
}

export function isFilesSectionExpanded(projectId) {
  return expandedFilesSections.has(projectId);
}

export function getExpandedFilesSections() {
  return expandedFilesSections;
}

export function setProjectFiles(projectId, files) {
  projectFiles = { ...projectFiles, [projectId]: files };
}

export function getProjectFiles(projectId) {
  return projectFiles[projectId] || [];
}

export function getAllProjectFiles() {
  return projectFiles;
}

export function addFileToProject(projectId, file) {
  const files = projectFiles[projectId] || [];
  projectFiles = { ...projectFiles, [projectId]: [...files, file] };
}

export function removeFileFromProject(projectId, fileExternalId) {
  const files = projectFiles[projectId] || [];
  projectFiles = {
    ...projectFiles,
    [projectId]: files.filter((f) => f.external_id !== fileExternalId),
  };
}

// Folder expand/collapse management
export function toggleFolderExpanded(projectId, folderId) {
  const folderSet = expandedFolderIds[projectId] || loadExpandedFolders(projectId);
  if (folderSet.has(folderId)) {
    folderSet.delete(folderId);
  } else {
    folderSet.add(folderId);
  }
  expandedFolderIds = { ...expandedFolderIds, [projectId]: new Set(folderSet) };
  saveExpandedFolders(projectId);
}

export function expandFolder(projectId, folderId) {
  const folderSet = expandedFolderIds[projectId] || loadExpandedFolders(projectId);
  if (!folderSet.has(folderId)) {
    folderSet.add(folderId);
    expandedFolderIds = { ...expandedFolderIds, [projectId]: new Set(folderSet) };
    saveExpandedFolders(projectId);
  }
}

export function isFolderExpanded(projectId, folderId) {
  const folderSet = expandedFolderIds[projectId];
  return folderSet ? folderSet.has(folderId) : false;
}

export function getExpandedFolderIds(projectId) {
  return expandedFolderIds[projectId] || new Set();
}

// Ensure folder expand state is loaded for a project when projects are set
function ensureFolderStateLoaded(projectId) {
  if (!expandedFolderIds[projectId]) {
    const loaded = loadExpandedFolders(projectId);
    if (loaded.size > 0) {
      expandedFolderIds = { ...expandedFolderIds, [projectId]: loaded };
    }
  }
}

// Export reactive getters
export function getProjects() {
  return projects;
}

export function getActivePageId() {
  return activePageId;
}

export { getShowOrgNames };

// Per-org last-viewed-page map. Used to resume the user on their most recent
// page when they switch back to an org. The canonical source is the server
// (UserOrgState rows, injected into window._userState.lastPagePerOrg). On
// page load we seed localStorage from the server value (eagerly, at module
// load — see `seedLastPageMapFromServer` below); subsequent updates are
// mirrored to both localStorage AND the server (fire-and-forget PATCH).
function readLastPageMap() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY_LAST_PAGE_PER_ORG);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

// Pure merge: localStorage wins over the server snapshot key-by-key.
// Server snapshot is always a moment-old view; localStorage reflects
// what just happened in this tab. Exported for unit testing — the IIFE
// below is the only production caller.
export function mergeServerLastPageMap(fromServer, existing) {
  const okFromServer =
    fromServer && typeof fromServer === "object" && !Array.isArray(fromServer) ? fromServer : {};
  const okExisting =
    existing && typeof existing === "object" && !Array.isArray(existing) ? existing : {};
  return { ...okFromServer, ...okExisting };
}

// Eager seed: as soon as this module loads, copy the SPA-injected
// `window._userState.lastPagePerOrg` into localStorage so a fresh browser
// context picks up the user's per-org history without waiting for the
// first org switch.
(function seedLastPageMapFromServer() {
  try {
    const fromServer = window._userState?.lastPagePerOrg;
    if (!fromServer || typeof fromServer !== "object" || Object.keys(fromServer).length === 0) {
      return;
    }
    let existing = {};
    try {
      const raw = localStorage.getItem(STORAGE_KEY_LAST_PAGE_PER_ORG);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed && typeof parsed === "object") existing = parsed;
      }
    } catch {}
    const merged = mergeServerLastPageMap(fromServer, existing);
    try {
      localStorage.setItem(STORAGE_KEY_LAST_PAGE_PER_ORG, JSON.stringify(merged));
    } catch {}
    // Clear the server snapshot so future reads are deterministic from
    // localStorage (which we just brought up to date).
    try {
      window._userState.lastPagePerOrg = {};
    } catch {}
  } catch {
    // No-op: storage hygiene shouldn't block module init.
  }
})();

function writeLastPageMap(map) {
  try {
    localStorage.setItem(STORAGE_KEY_LAST_PAGE_PER_ORG, JSON.stringify(map));
  } catch {}
}

export function getLastPageForOrg(orgId) {
  if (!orgId) return null;
  const map = readLastPageMap();
  return map[orgId] || null;
}

export function setLastPageForOrg(orgId, pageId) {
  if (!orgId || !pageId) return;
  const map = readLastPageMap();
  if (map[orgId] === pageId) return;
  map[orgId] = pageId;
  writeLastPageMap(map);
}

export function clearLastPageForOrg(orgId, pageId = null) {
  if (!orgId) return;
  const map = readLastPageMap();
  // If a specific pageId is given, only clear if it matches (used when a
  // page is deleted so we don't accidentally clear a more recent value).
  if (pageId && map[orgId] !== pageId) return;
  if (!(orgId in map)) return;
  delete map[orgId];
  writeLastPageMap(map);
}
