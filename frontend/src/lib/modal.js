import { mount } from 'svelte';
import GlobalConfirm from './components/GlobalConfirm.svelte';
import {
  openConfirm as _openConfirm,
  openPrompt as _openPrompt,
  openShareProject as _openShareProject,
  openSharePage as _openSharePage,
  openCreateProject as _openCreateProject,
} from './stores/modal.svelte.js';

let mounted = false;

export function initModals() {
  if (mounted) return;
  mounted = true;

  const container = document.createElement('div');
  container.id = 'svelte-modal-root';
  document.body.appendChild(container);

  mount(GlobalConfirm, { target: container });
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
 * Show a share page modal
 * @param {Object} options
 * @param {string} options.pageId - Page external ID
 * @param {string} options.pageTitle - Page title to display
 */
export function sharePage(options) {
  initModals();
  _openSharePage(options);
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
