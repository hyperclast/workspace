/**
 * Sidenav store - manages project list state
 */

const STORAGE_KEY_EXPANDED = "expanded-project-ids";
const STORAGE_KEY_CURRENT_PROJECT_OLD = "current-project-id"; // For migration

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

// Reactive state
let projects = $state([]);
let activePageId = $state(null);
let expandedProjectIds = $state(loadExpandedProjects());

// Callbacks (set from vanilla JS)
let onNavigate = null;
let onNewPage = null;
let onProjectDeleted = null;
let onProjectRenamed = null;

// Computed: whether to show org names (multiple orgs)
function getShowOrgNames() {
  const orgIds = new Set(projects.map((p) => p.org?.external_id).filter(Boolean));
  return orgIds.size > 1;
}

// Helper to save expanded projects to localStorage
function saveExpandedProjects() {
  localStorage.setItem(STORAGE_KEY_EXPANDED, JSON.stringify([...expandedProjectIds]));
}

// Actions
export function setProjects(newProjects, newActivePageId = null) {
  projects = [...newProjects];
  activePageId = newActivePageId;

  // Auto-expand project containing active page (without collapsing others)
  if (newActivePageId) {
    const activeProject = projects.find((p) =>
      p.pages?.some((page) => page.external_id === newActivePageId)
    );
    if (activeProject) {
      expandProject(activeProject.external_id);
    }
  }

  // If no projects are expanded and we have projects, expand the first one
  if (expandedProjectIds.size === 0 && projects.length > 0) {
    expandProject(projects[0].external_id);
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

export function createNewPage(projectId) {
  if (projectId) {
    expandProject(projectId);
  }
  if (onNewPage) {
    onNewPage(projectId);
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

// Export reactive getters
export function getProjects() {
  return projects;
}

export function getActivePageId() {
  return activePageId;
}

export { getShowOrgNames };
