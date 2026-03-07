/**
 * Rewind feature — state management, API integration, and setup.
 *
 * Manages the rewind timeline sidebar tab and the main-pane viewer.
 * Hides the live editor (doesn't destroy it) to preserve collaboration state.
 */

import { fetchRewindList, fetchRewindDetail } from "../api.js";
import { registerTabHandler, registerPageChangeHandler } from "../lib/stores/sidebar.svelte.js";

// Module state
let entries = [];
let totalCount = 0;
let currentPageId = null;
let selectedEntry = null;
let selectedContent = null;
let previousContent = null; // content of the preceding rewind (for diff)
let viewMode = "diff"; // 'diff' | 'preview'
let diffFormat = "formatted"; // 'plain' | 'formatted'
let isRewindMode = false;
let loading = false;
let loadingDetail = false;
let debounceTimer = null;

// Event listeners for UI updates
const listeners = new Set();

function notify() {
  for (const fn of listeners) fn(getState());
}

export function subscribe(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function getState() {
  return {
    entries,
    totalCount,
    currentPageId,
    selectedEntry,
    selectedContent,
    previousContent,
    viewMode,
    diffFormat,
    isRewindMode,
    loading,
    loadingDetail,
  };
}

/**
 * Load rewind entries for the current page.
 */
async function loadEntries() {
  if (!currentPageId) {
    entries = [];
    totalCount = 0;
    notify();
    return;
  }

  loading = true;
  notify();

  try {
    const data = await fetchRewindList(currentPageId);
    entries = data.items || [];
    totalCount = data.count || 0;
  } catch (e) {
    console.error("Failed to load rewind entries:", e);
    entries = [];
    totalCount = 0;
  }

  loading = false;
  notify();
}

/**
 * Load more entries (pagination).
 */
export async function loadMore() {
  if (!currentPageId || entries.length >= totalCount) return;

  loading = true;
  notify();

  try {
    const data = await fetchRewindList(currentPageId, 50, entries.length);
    entries = [...entries, ...(data.items || [])];
    totalCount = data.count || 0;
  } catch (e) {
    console.error("Failed to load more rewind entries:", e);
  }

  loading = false;
  notify();
}

/**
 * Select a rewind entry — debounced for rapid clicks.
 */
export function selectEntry(entry) {
  if (debounceTimer) clearTimeout(debounceTimer);

  debounceTimer = setTimeout(() => {
    doSelectEntry(entry);
  }, 150);
}

async function doSelectEntry(entry) {
  if (!currentPageId || !entry) return;

  selectedEntry = entry;
  loadingDetail = true;
  notify();

  // Enter rewind mode if not already
  if (!isRewindMode) {
    enterRewindMode();
  }

  try {
    // Find the previous entry (entries are ordered desc by rewind_number,
    // so the entry right after this one in the array is the predecessor).
    const idx = entries.findIndex((e) => e.external_id === entry.external_id);
    const prevEntry = idx >= 0 && idx < entries.length - 1 ? entries[idx + 1] : null;

    // Fetch selected detail (and previous detail in parallel if available)
    const fetches = [fetchRewindDetail(currentPageId, entry.external_id)];
    if (prevEntry) {
      fetches.push(fetchRewindDetail(currentPageId, prevEntry.external_id));
    }

    const results = await Promise.all(fetches);

    // Check if still the selected entry (user might have clicked another)
    if (selectedEntry?.external_id === entry.external_id) {
      selectedContent = results[0].content;
      previousContent = prevEntry ? results[1].content : "";
      loadingDetail = false;
      notify();
    }
  } catch (e) {
    console.error("Failed to fetch rewind detail:", e);
    loadingDetail = false;
    notify();
  }
}

/**
 * Enter rewind mode — hide editor, show viewer.
 */
export function enterRewindMode() {
  if (isRewindMode) return;
  isRewindMode = true;

  // Hide editor + toolbar, show rewind viewer
  const editorContainer = document.getElementById("editor-container");
  const toolbarWrapper = document.getElementById("toolbar-wrapper");
  const rewindViewer = document.getElementById("rewind-viewer");

  if (editorContainer) editorContainer.style.display = "none";
  if (toolbarWrapper) toolbarWrapper.style.display = "none";
  if (rewindViewer) rewindViewer.style.display = "flex";

  notify();
}

/**
 * Exit rewind mode — show editor, hide viewer.
 */
export function exitRewindMode() {
  if (!isRewindMode) return;
  isRewindMode = false;
  selectedEntry = null;
  selectedContent = null;
  previousContent = null;
  viewMode = "diff";
  diffFormat = "formatted";

  if (debounceTimer) clearTimeout(debounceTimer);

  // Show editor + toolbar, hide rewind viewer
  const editorContainer = document.getElementById("editor-container");
  const toolbarWrapper = document.getElementById("toolbar-wrapper");
  const rewindViewer = document.getElementById("rewind-viewer");

  if (editorContainer) editorContainer.style.display = "";
  if (toolbarWrapper) toolbarWrapper.style.display = "";
  if (rewindViewer) rewindViewer.style.display = "none";

  // Dispatch event so RewindViewer can cleanup its CodeMirror preview
  window.dispatchEvent(new CustomEvent("rewindExited"));

  notify();
}

/**
 * Set the view mode (diff or preview).
 */
export function setViewMode(mode) {
  viewMode = mode;
  notify();
}

/**
 * Set the diff format (plain or formatted).
 */
export function setDiffFormat(format) {
  diffFormat = format;
  notify();
}

/**
 * Setup rewind feature — register tab and page change handlers.
 */
export function setupRewind() {
  registerTabHandler("rewind", () => {
    loadEntries();
  });

  registerPageChangeHandler((pageId) => {
    // Exit rewind if switching pages
    if (isRewindMode) exitRewindMode();

    currentPageId = pageId;
    entries = [];
    totalCount = 0;
    selectedEntry = null;
    selectedContent = null;
    previousContent = null;
    notify();

    // Load entries for the new page
    if (pageId) loadEntries();
  });

  // Live-update timeline when a new rewind is created via WebSocket
  window.addEventListener("rewindCreated", (event) => {
    const { pageId, rewind } = event.detail;
    if (pageId !== currentPageId) return;
    if (entries.some((e) => e.external_id === rewind.external_id)) return;
    entries = [rewind, ...entries];
    totalCount += 1;
    notify();
  });

  // Expose on window for main.js cleanup
  window._rewindActive = () => isRewindMode;
  window._exitRewindMode = () => exitRewindMode();
}
