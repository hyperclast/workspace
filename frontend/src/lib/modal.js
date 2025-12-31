import { mount } from "svelte";
import GlobalConfirm from "./components/GlobalConfirm.svelte";
import {
  openConfirm as _openConfirm,
  openPrompt as _openPrompt,
  openShareProject as _openShareProject,
  openCreateProject as _openCreateProject,
  openNewPage as _openNewPage,
  openChangePageType as _openChangePageType,
} from "./stores/modal.svelte.js";

let mounted = false;

export function initModals() {
  // Check if container already exists on body
  let container = document.getElementById("svelte-modal-root");
  if (mounted && container) return;

  // Create container if it doesn't exist
  if (!container) {
    container = document.createElement("div");
    container.id = "svelte-modal-root";
    document.body.appendChild(container);
  } else {
    container.innerHTML = "";
  }

  mount(GlobalConfirm, { target: container });
  mounted = true;
}

/**
 * Show a confirmation dialog
 * @param {Object} options
 * @param {string} options.title - Modal title
 * @param {string} options.message - Main message
 * @param {string} options.description - Secondary description/warning
 * @param {string} options.confirmText - Confirm button text (default: "Confirm")
 * @param {string} options.cancelText - Cancel button text (default: "Cancel")
 * @param {boolean} options.danger - Show as dangerous action (red styling)
 * @returns {Promise<boolean>} - Resolves true if confirmed, false if cancelled
 */
export async function confirm(options) {
  initModals();
  return _openConfirm(options);
}

/**
 * Show a prompt dialog with text input
 * @param {Object} options
 * @param {string} options.title - Modal title
 * @param {string} options.label - Input label
 * @param {string} options.placeholder - Input placeholder
 * @param {string} options.value - Initial input value
 * @param {string} options.confirmText - Confirm button text (default: "Save")
 * @param {string} options.cancelText - Cancel button text (default: "Cancel")
 * @param {number} options.maxlength - Max input length (default: 255)
 * @param {boolean} options.required - Whether input is required (default: true)
 * @returns {Promise<string|null>} - Resolves with input value, or null if cancelled
 */
export async function prompt(options) {
  initModals();
  return _openPrompt(options);
}

/**
 * Show a share project modal
 * @param {Object} options
 * @param {string} options.projectId - Project external ID
 * @param {string} options.projectName - Project name to display
 */
export function shareProject(options) {
  initModals();
  _openShareProject(options);
}

/**
 * Show a create project modal
 * @param {Object} options
 * @param {Function} options.oncreated - Callback when project is created, receives the new project
 */
export function createProjectModal(options = {}) {
  initModals();
  _openCreateProject(options);
}

/**
 * Show a new page modal with title format buttons and copy-from dropdown
 * @param {Object} options
 * @param {string} options.projectId - Project external ID
 * @param {Array} options.pages - List of pages in the project for copy-from dropdown
 * @param {Function} options.oncreated - Callback when page info is submitted, receives { title, copyFrom }
 */
export function newPageModal(options = {}) {
  initModals();
  _openNewPage(options);
}

/**
 * Show a change page type modal
 * @param {Object} options
 * @param {string} options.pageId - Page external ID
 * @param {string} options.pageTitle - Page title
 * @param {string} options.currentType - Current filetype (md, txt, etc.)
 * @param {Function} options.onchanged - Callback when type is changed, receives new type
 */
export function changePageType(options = {}) {
  initModals();
  _openChangePageType(options);
}
