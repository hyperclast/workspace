/**
 * Keyboard shortcuts configuration with user customization support.
 * Shortcuts are stored in user profile and synced across devices.
 */

import { API_BASE_URL } from "../config.js";
import { csrfFetch } from "../csrf.js";

// Default shortcuts - key is the action ID, value is the CodeMirror key notation
const DEFAULT_SHORTCUTS = {
  toggleCheckbox: "Mod-l",
  openCommandPalette: "Mod-k",
};

// Human-readable labels for actions
export const SHORTCUT_LABELS = {
  toggleCheckbox: "Toggle checkbox",
  openCommandPalette: "Open command palette",
};

// In-memory cache of custom shortcuts (loaded from user profile)
let customShortcuts = {};
let initialized = false;

// Listeners for shortcut changes
const listeners = new Set();

/**
 * Initialize shortcuts from user data (called when user data is loaded).
 * @param {Object} shortcuts - User's keyboard_shortcuts from profile
 */
export function initShortcuts(shortcuts) {
  customShortcuts = shortcuts || {};
  initialized = true;
  notifyListeners("*");
}

/**
 * Get the current shortcut for an action.
 * Returns "disabled" if the shortcut is disabled, or the key notation.
 * @param {string} actionId - The action identifier (e.g., "toggleCheckbox")
 * @returns {string} The key notation or "disabled"
 */
export function getShortcut(actionId) {
  if (actionId in customShortcuts) {
    return customShortcuts[actionId];
  }
  return DEFAULT_SHORTCUTS[actionId] || null;
}

/**
 * Get the default shortcut for an action.
 * @param {string} actionId - The action identifier
 * @returns {string|null} The default key notation
 */
export function getDefaultShortcut(actionId) {
  return DEFAULT_SHORTCUTS[actionId] || null;
}

/**
 * Set a custom shortcut for an action (local only, does not persist).
 * Use this for immediate UI feedback. Call saveShortcuts() to persist.
 * @param {string} actionId - The action identifier
 * @param {string|null} keyNotation - The new key notation, "disabled", or null to reset
 */
export function setShortcut(actionId, keyNotation) {
  if (keyNotation === null || keyNotation === DEFAULT_SHORTCUTS[actionId]) {
    // Reset to default
    delete customShortcuts[actionId];
  } else {
    customShortcuts[actionId] = keyNotation;
  }
  notifyListeners(actionId);
}

/**
 * Check if a shortcut is currently disabled.
 * @param {string} actionId - The action identifier
 * @returns {boolean}
 */
export function isShortcutDisabled(actionId) {
  return getShortcut(actionId) === "disabled";
}

/**
 * Check if a shortcut has been customized (differs from default).
 * @param {string} actionId - The action identifier
 * @returns {boolean}
 */
export function isShortcutCustomized(actionId) {
  return actionId in customShortcuts;
}

/**
 * Get all configurable shortcuts with their current values.
 * @returns {Array<{id: string, label: string, key: string, default: string, customized: boolean}>}
 */
export function getAllShortcuts() {
  return Object.keys(DEFAULT_SHORTCUTS).map((id) => ({
    id,
    label: SHORTCUT_LABELS[id] || id,
    key: getShortcut(id),
    default: DEFAULT_SHORTCUTS[id],
    customized: isShortcutCustomized(id),
  }));
}

/**
 * Subscribe to shortcut changes.
 * @param {Function} callback - Called with (actionId) when a shortcut changes
 * @returns {Function} Unsubscribe function
 */
export function onShortcutChange(callback) {
  listeners.add(callback);
  return () => listeners.delete(callback);
}

function notifyListeners(actionId) {
  listeners.forEach((cb) => cb(actionId));
}

/**
 * Convert CodeMirror key notation to display format.
 * @param {string} keyNotation - CodeMirror format (e.g., "Mod-l")
 * @returns {string} Display format (e.g., "Cmd+L" on Mac)
 */
export function formatShortcutForDisplay(keyNotation) {
  if (keyNotation === "disabled") {
    return "Disabled";
  }

  const isMac =
    typeof navigator !== "undefined" && navigator.platform.toUpperCase().indexOf("MAC") >= 0;

  return keyNotation
    .replace(/Mod/g, isMac ? "Cmd" : "Ctrl")
    .replace(/-/g, "+")
    .replace(/\b[a-z]\b/g, (c) => c.toUpperCase());
}

/**
 * Parse a display format shortcut back to CodeMirror notation.
 * @param {string} displayFormat - Display format (e.g., "Cmd+L")
 * @returns {string} CodeMirror format (e.g., "Mod-l")
 */
export function parseDisplayToKeyNotation(displayFormat) {
  if (displayFormat.toLowerCase() === "disabled") {
    return "disabled";
  }

  return displayFormat
    .replace(/Cmd|Ctrl/gi, "Mod")
    .replace(/\+/g, "-")
    .toLowerCase();
}
