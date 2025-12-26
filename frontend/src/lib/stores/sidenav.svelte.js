/**
 * Sidenav store - manages project list state
 */

const STORAGE_KEY_CURRENT_PROJECT = "current-project-id";

// Reactive state
let projects = $state([]);
let activePageId = $state(null);
let currentProjectId = $state(localStorage.getItem(STORAGE_KEY_CURRENT_PROJECT) || null);

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

// Actions
export function setProjects(newProjects, newActivePageId = null) {
  projects = [...newProjects];
  activePageId = newActivePageId;

  // Auto-select current project based on active page
  const activeProject = projects.find((p) =>
    p.pages?.some((page) => page.external_id === newActivePageId)
  );

  if (activeProject && activeProject.external_id !== currentProjectId) {
    setCurrentProject(activeProject.external_id);
  } else if (!currentProjectId && projects.length > 0) {
    // Restore from localStorage or default to first project
    const savedProjectId = localStorage.getItem(STORAGE_KEY_CURRENT_PROJECT);
    if (savedProjectId && projects.find((p) => p.external_id === savedProjectId)) {
      currentProjectId = savedProjectId;
    } else {
      setCurrentProject(projects[0].external_id);
    }
  }
}

export function setActivePageId(pageId) {
  activePageId = pageId;
}

export function setCurrentProject(projectId) {
  currentProjectId = projectId;
  if (projectId) {
    localStorage.setItem(STORAGE_KEY_CURRENT_PROJECT, projectId);
  } else {
    localStorage.removeItem(STORAGE_KEY_CURRENT_PROJECT);
  }
}

export function getCurrentProjectId() {
  return currentProjectId;
}

export function expandProject(projectId) {
  if (projectId !== currentProjectId) {
    setCurrentProject(projectId);
  }
}

export function navigateToPage(pageId, projectId) {
  if (projectId && projectId !== currentProjectId) {
    setCurrentProject(projectId);
  }
  if (onNavigate) {
    onNavigate(pageId);
  }
}

export function createNewPage(projectId) {
  if (projectId && projectId !== currentProjectId) {
    setCurrentProject(projectId);
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
