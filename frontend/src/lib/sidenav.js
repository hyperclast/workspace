/**
 * Sidenav bridge - mounts Svelte component and exposes API for vanilla JS
 */

import { mount } from "svelte";
import Sidenav from "./components/Sidenav.svelte";
import {
  setProjects,
  setActivePageId,
  setNavigateHandler,
  setNewPageHandler,
  setProjectDeletedHandler,
  setProjectRenamedHandler,
  getCurrentProjectId,
  setCurrentProject,
  toggleProjectExpanded,
  expandProject,
  collapseProject,
  isProjectExpanded,
  getExpandedProjectIds,
} from "./stores/sidenav.svelte.js";

let mounted = false;

/**
 * Initialize the sidenav by mounting the Svelte component.
 */
function initSidenav() {
  const container = document.getElementById("sidebar-list");
  if (!container) {
    console.error("Sidenav container #sidebar-list not found");
    return;
  }

  // Check if already mounted and DOM element has content
  if (mounted && container.children.length > 0) return;

  // Clear any existing content and (re)mount
  container.innerHTML = "";
  mount(Sidenav, { target: container });
  mounted = true;
}

/**
 * Render the sidenav with projects and active page.
 * @param {Array} projects - Array of projects with pages
 * @param {string|null} activePageId - Currently active page external_id
 */
export function renderSidenav(projects, activePageId = null) {
  initSidenav();
  setProjects(projects, activePageId);
}

/**
 * Update the active page highlight without full re-render.
 * @param {string} activePageId - Currently active page external_id
 */
export function updateSidenavActive(activePageId) {
  setActivePageId(activePageId);
}

/**
 * Set the navigation callback for when pages are clicked.
 * @param {Function} handler - Handler for page navigation, receives pageId
 */
export function setNavigateCallback(handler) {
  setNavigateHandler(handler);
}

/**
 * Setup sidenav with new page handler.
 * @param {Function} onNewPage - Handler for "New Page" button clicks, receives projectId
 */
export function setupSidenav(onNewPage) {
  setNewPageHandler(onNewPage);
  setupToggle();
}

/**
 * Set the project deleted callback.
 * @param {Function} handler - Handler for project deletion, receives projectId
 */
export { setProjectDeletedHandler };

/**
 * Set the project renamed callback.
 * @param {Function} handler - Handler for project rename, receives (projectId, newName)
 */
export { setProjectRenamedHandler };

/**
 * Get the current project ID (backwards compatibility - returns first expanded).
 */
export { getCurrentProjectId };

/**
 * Set the current project ID (backwards compatibility - expands project).
 */
export { setCurrentProject };

/**
 * Toggle a project's expand/collapse state.
 */
export { toggleProjectExpanded };

/**
 * Expand a specific project (no-op if already expanded).
 */
export { expandProject };

/**
 * Collapse a specific project.
 */
export { collapseProject };

/**
 * Check if a project is expanded.
 */
export { isProjectExpanded };

/**
 * Get all expanded project IDs as a Set.
 */
export { getExpandedProjectIds };

/**
 * Setup sidebar toggle behavior for mobile.
 */
function setupToggle() {
  const toggle = document.getElementById("sidebar-toggle");
  const sidebar = document.getElementById("note-sidebar");
  const overlay = document.getElementById("sidebar-overlay");

  function open() {
    sidebar?.classList.add("open");
    overlay?.classList.add("visible");
  }

  function close() {
    sidebar?.classList.remove("open");
    overlay?.classList.remove("visible");
  }

  toggle?.addEventListener("click", open);
  overlay?.addEventListener("click", close);
}
