/**
 * Command Palette Setup
 * Provides a reusable keyboard listener for the command palette.
 * Can be used on any page (main app, settings, etc.)
 */

import { commandPalette } from "./modal.js";
import { showToast } from "./toast.js";
import { getShortcut, onShortcutChange } from "./keyboardShortcuts.js";

let initialized = false;
let keydownHandler = null;
let shortcutUnsubscribe = null;

/**
 * Check if a keyboard event matches a shortcut notation (e.g., "Mod-k")
 */
function matchesShortcut(event, shortcutNotation) {
  if (!shortcutNotation || shortcutNotation === "disabled") {
    return false;
  }

  const parts = shortcutNotation.toLowerCase().split("-");
  const key = parts[parts.length - 1];
  const hasMod = parts.includes("mod");
  const hasShift = parts.includes("shift");
  const hasAlt = parts.includes("alt");

  const modPressed = event.metaKey || event.ctrlKey;

  return (
    event.key.toLowerCase() === key &&
    modPressed === hasMod &&
    event.shiftKey === hasShift &&
    event.altKey === hasAlt
  );
}

/**
 * Setup the command palette keyboard shortcut (customizable, default Cmd+K / Ctrl+K)
 * @param {Object} options
 * @param {Function} options.getProjects - Function that returns current projects array
 * @param {Function} options.getCurrentPageId - Function that returns current page ID (optional)
 * @param {Function} options.getCurrentProjectId - Function that returns current project ID (optional)
 * @param {Function} options.onNavigate - Called when user navigates to a page
 * @param {Function} options.onCreatePage - Called when user wants to create a page (optional)
 * @param {Function} options.onCreateProject - Called when user wants to create a project (optional)
 * @param {Function} options.onDeletePage - Called when user wants to delete current page (optional)
 * @param {Function} options.onAsk - Called when user wants to open Ask sidebar (optional)
 */
export function setupCommandPalette(options = {}) {
  if (initialized && keydownHandler) {
    // Remove existing handler before adding new one
    document.removeEventListener("keydown", keydownHandler);
  }

  keydownHandler = (e) => {
    const shortcut = getShortcut("openCommandPalette");
    if (matchesShortcut(e, shortcut)) {
      e.preventDefault();

      const projects = options.getProjects ? options.getProjects() : [];
      const currentPageId = options.getCurrentPageId ? options.getCurrentPageId() : null;
      const currentProjectId = options.getCurrentProjectId ? options.getCurrentProjectId() : null;

      commandPalette({
        projects,
        currentPageId,
        currentProjectId,
        onselect: (selection) => handleSelection(selection, options),
      });
    }
  };

  document.addEventListener("keydown", keydownHandler);
  initialized = true;
}

/**
 * Handle command palette selection
 */
function handleSelection(selection, options) {
  if (selection.type === "navigate" && selection.pageId) {
    if (options.onNavigate) {
      options.onNavigate(selection.pageId);
    } else {
      // Default: navigate via URL
      window.location.href = `/pages/${selection.pageId}/`;
    }
  } else if (selection.type === "action") {
    switch (selection.actionId) {
      case "create-page":
        if (options.onCreatePage) {
          options.onCreatePage();
        } else {
          showToast("Navigate to the editor to create a page", "info");
        }
        break;
      case "create-project":
        if (options.onCreateProject) {
          options.onCreateProject();
        } else {
          showToast("Navigate to the editor to create a project", "info");
        }
        break;
      case "delete-page":
        if (options.onDeletePage) {
          options.onDeletePage();
        } else {
          showToast("Navigate to a page to delete it", "info");
        }
        break;
      case "ask":
        if (options.onAsk) {
          options.onAsk();
        } else {
          // Default: navigate to main app (Ask is only available there)
          window.location.href = "/";
        }
        break;
      case "settings":
        window.location.href = "/settings/";
        break;
      case "developer-portal":
        window.location.href = "/dev/";
        break;
    }
  }
}

/**
 * Remove the command palette keyboard listener
 */
export function teardownCommandPalette() {
  if (keydownHandler) {
    document.removeEventListener("keydown", keydownHandler);
    keydownHandler = null;
    initialized = false;
  }
}
