/**
 * PDF Viewer State Store
 *
 * Svelte 5 $state for managing the PDF viewer modal.
 * Handles open/close state, current page, zoom level, and loading/error states.
 */

let state = $state({
  open: false,
  url: "",
  filename: "",
  currentPage: 1,
  totalPages: 0,
  zoom: 1.0,
  loading: true,
  error: null,
});

/**
 * Open the PDF viewer modal with the given URL and filename.
 * @param {Object} options
 * @param {string} options.url - The URL of the PDF file
 * @param {string} options.filename - The filename to display
 */
export function openPdfViewer({ url, filename }) {
  state.url = url;
  state.filename = filename;
  state.currentPage = 1;
  state.totalPages = 0;
  state.zoom = 1.0;
  state.loading = true;
  state.error = null;
  state.open = true;
}

/**
 * Close the PDF viewer modal.
 */
export function closePdfViewer() {
  state.open = false;
}

/**
 * Get the current PDF viewer state.
 * @returns {Object} The current state object
 */
export function getPdfViewerState() {
  return state;
}

/**
 * Set the total number of pages in the PDF.
 * @param {number} pages - Total page count
 */
export function setTotalPages(pages) {
  state.totalPages = pages;
}

/**
 * Set the current page number.
 * @param {number} page - Page number (1-indexed)
 */
export function setCurrentPage(page) {
  if (page >= 1 && page <= state.totalPages) {
    state.currentPage = page;
  }
}

/**
 * Go to the next page.
 */
export function nextPage() {
  if (state.currentPage < state.totalPages) {
    state.currentPage++;
  }
}

/**
 * Go to the previous page.
 */
export function prevPage() {
  if (state.currentPage > 1) {
    state.currentPage--;
  }
}

/**
 * Go to the first page.
 */
export function firstPage() {
  state.currentPage = 1;
}

/**
 * Go to the last page.
 */
export function lastPage() {
  if (state.totalPages > 0) {
    state.currentPage = state.totalPages;
  }
}

/**
 * Set the zoom level.
 * @param {number} zoom - Zoom level (0.5 to 3.0)
 */
export function setZoom(zoom) {
  state.zoom = Math.max(0.5, Math.min(3.0, zoom));
}

/**
 * Zoom in by 25%.
 */
export function zoomIn() {
  setZoom(state.zoom + 0.25);
}

/**
 * Zoom out by 25%.
 */
export function zoomOut() {
  setZoom(state.zoom - 0.25);
}

/**
 * Reset zoom to 100%.
 */
export function resetZoom() {
  state.zoom = 1.0;
}

/**
 * Set loading state.
 * @param {boolean} loading
 */
export function setLoading(loading) {
  state.loading = loading;
}

/**
 * Set error state.
 * @param {string|null} error - Error message or null to clear
 */
export function setError(error) {
  state.error = error;
  state.loading = false;
}
