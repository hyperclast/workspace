/**
 * Sidenav bridge - mounts Svelte component and exposes API for vanilla JS
 */

import { mount } from "svelte";
import { SIDEBAR_OVERLAY_BREAKPOINT } from "../config.js";
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
  setShowFilesSection,
  getShowFilesSection,
  setProjectFiles,
  getProjectFiles,
  addFileToProject,
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
 * Enable/disable the files section display.
 */
export { setShowFilesSection };

/**
 * Check if files section is enabled.
 */
export { getShowFilesSection };

/**
 * Set files for a specific project.
 */
export { setProjectFiles };

/**
 * Get files for a specific project.
 */
export { getProjectFiles };

/**
 * Add a file to a project's file list.
 */
export { addFileToProject };

const LEFT_COLLAPSED_KEY = "ws-left-sidebar-collapsed";

/**
 * Setup sidebar toggle behavior.
 * - At <=1024px (overlay mode): toggle opens/closes sidebar as fixed overlay with backdrop.
 * - At >1024px (inline mode): toggle collapses/expands sidebar inline. State saved to localStorage.
 */
function setupToggle() {
  const toggle = document.getElementById("sidebar-toggle");
  const sidebar = document.getElementById("note-sidebar");
  const overlay = document.getElementById("sidebar-overlay");

  if (!toggle || !sidebar) return;

  const isOverlayMode = () => window.innerWidth <= SIDEBAR_OVERLAY_BREAKPOINT;

  function openOverlay() {
    sidebar.classList.add("open");
    overlay?.classList.add("visible");
  }

  function closeOverlay() {
    sidebar.classList.remove("open");
    overlay?.classList.remove("visible");
  }

  function collapseInline() {
    sidebar.classList.add("collapsed");
    // Clear inline width set by resize handler — otherwise it overrides .collapsed { width: 0 }
    sidebar.style.width = "";
    localStorage.setItem(LEFT_COLLAPSED_KEY, "true");
  }

  function expandInline() {
    sidebar.classList.remove("collapsed");
    // Restore saved resize width if any
    const savedWidth = localStorage.getItem("ws-left-sidebar-width");
    if (savedWidth) {
      sidebar.style.width = `${savedWidth}px`;
    }
    localStorage.setItem(LEFT_COLLAPSED_KEY, "false");
  }

  // Toggle click handler
  toggle.addEventListener("click", () => {
    if (isOverlayMode()) {
      if (sidebar.classList.contains("open")) {
        closeOverlay();
      } else {
        openOverlay();
      }
    } else {
      if (sidebar.classList.contains("collapsed")) {
        expandInline();
      } else {
        collapseInline();
      }
    }
  });

  // Overlay click closes sidebar
  overlay?.addEventListener("click", closeOverlay);

  // Handle resize: transition between overlay and inline modes
  window.addEventListener("resize", () => {
    if (!isOverlayMode()) {
      // Moved to desktop: close overlay if open, restore inline state
      if (sidebar.classList.contains("open")) {
        closeOverlay();
      }
    } else {
      // Moved to overlay mode: remove inline collapsed state and restore width
      if (sidebar.classList.contains("collapsed")) {
        sidebar.classList.remove("collapsed");
        const savedWidth = localStorage.getItem("ws-left-sidebar-width");
        if (savedWidth) {
          sidebar.style.width = `${savedWidth}px`;
        }
      }
    }
  });

  // On load at >1024px: restore collapsed state from localStorage
  if (!isOverlayMode()) {
    const saved = localStorage.getItem(LEFT_COLLAPSED_KEY);
    if (saved === "true") {
      sidebar.classList.add("collapsed");
      sidebar.style.width = "";
    }
  }
}
