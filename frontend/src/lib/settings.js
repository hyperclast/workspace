/**
 * Settings page bridge - mounts Svelte component
 */

import { mount } from "svelte";
import { setupCommandPalette } from "./commandPaletteSetup.js";
import { fetchProjectsWithPages } from "../api.js";

let mounted = false;
let cachedProjects = [];

/**
 * Initialize the settings page by mounting the Svelte component.
 */
export default async function initSettingsPage() {
  // Check if already mounted and DOM element exists with content
  const existingRoot = document.getElementById("settings-page-root");
  if (mounted && existingRoot && existingRoot.children.length > 0) {
    console.log("[Settings] Already mounted, skipping re-initialization");
    return;
  }

  try {
    console.log("[Settings] Starting initialization...");

    const app = document.getElementById("app");
    if (!app) {
      console.error("[Settings] App container #app not found");
      return;
    }

    // Clear any existing content
    app.innerHTML = "";

    // Create a wrapper div to track if we're mounted
    const wrapper = document.createElement("div");
    wrapper.id = "settings-page-root";
    app.appendChild(wrapper);

    // Dynamic import to isolate any import errors
    console.log("[Settings] Importing SettingsPage component...");
    const { default: SettingsPage } = await import("./components/SettingsPage.svelte");

    console.log("[Settings] Mounting component...");
    mount(SettingsPage, { target: wrapper });

    mounted = true;
    console.log("[Settings] Successfully initialized");

    // Setup command palette (Cmd+K / Ctrl+K)
    // Fetch projects for navigation
    try {
      cachedProjects = await fetchProjectsWithPages();
    } catch (e) {
      console.warn("[Settings] Could not fetch projects for command palette:", e);
      cachedProjects = [];
    }

    setupCommandPalette({
      getProjects: () => cachedProjects,
      // No current page/project on settings page
      getCurrentPageId: () => null,
      getCurrentProjectId: () => null,
      // Navigation goes to the page URL
      onNavigate: (pageId) => {
        window.location.href = `/pages/${pageId}/`;
      },
      // Other actions navigate to main app
      onCreatePage: null,
      onCreateProject: null,
      onDeletePage: null,
      onAsk: null,
    });
  } catch (error) {
    console.error("[Settings] Failed to initialize:", error);
    throw error;
  }
}
