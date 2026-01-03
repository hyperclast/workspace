/**
 * Standalone Command Palette
 * Can be loaded on any page (including server-rendered Django pages)
 * to enable the Cmd+K / Ctrl+K shortcut.
 */

import { initModals } from "./lib/modal.js";
import { setupCommandPalette } from "./lib/commandPaletteSetup.js";
import { fetchProjectsWithPages } from "./api.js";

let initialized = false;
let cachedProjects = [];

/**
 * Initialize the standalone command palette.
 * This should be called once when the page loads.
 */
export async function initCommandPalette() {
  if (initialized) return;

  // Initialize the modal system (mounts GlobalConfirm which includes CommandPalette)
  initModals();

  // Fetch projects for navigation
  try {
    cachedProjects = await fetchProjectsWithPages();
  } catch (e) {
    console.warn("[CommandPalette] Could not fetch projects:", e);
    cachedProjects = [];
  }

  // Setup the keyboard shortcut
  setupCommandPalette({
    getProjects: () => cachedProjects,
    getCurrentPageId: () => null,
    getCurrentProjectId: () => null,
    onNavigate: (pageId) => {
      window.location.href = `/pages/${pageId}/`;
    },
    // These actions navigate to the main app since they're not available here
    onCreatePage: null,
    onCreateProject: null,
    onDeletePage: null,
    onAsk: null,
  });

  initialized = true;
  console.log("[CommandPalette] Initialized standalone mode");
}

// Auto-initialize when the DOM is ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initCommandPalette);
} else {
  initCommandPalette();
}
