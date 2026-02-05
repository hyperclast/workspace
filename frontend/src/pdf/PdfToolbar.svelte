<script>
  /**
   * PDF Toolbar Component
   *
   * Navigation controls, zoom, download, and close button for the PDF viewer.
   */
  import {
    getPdfViewerState,
    closePdfViewer,
    prevPage,
    nextPage,
    firstPage,
    lastPage,
    zoomIn,
    zoomOut,
    resetZoom,
  } from "../lib/stores/pdfViewer.svelte.js";

  let state = getPdfViewerState();

  function handleDownload() {
    window.open(state.url, "_blank");
  }

  function handleClose() {
    closePdfViewer();
  }

  function formatZoom(zoom) {
    return `${Math.round(zoom * 100)}%`;
  }
</script>

<div class="pdf-toolbar">
  <div class="pdf-toolbar-left">
    <button
      class="pdf-toolbar-btn"
      onclick={prevPage}
      disabled={state.currentPage <= 1}
      title="Previous page (Left arrow)"
    >
      <svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <polyline points="15 18 9 12 15 6"></polyline>
      </svg>
    </button>
    <span class="pdf-page-indicator">
      {state.currentPage} / {state.totalPages}
    </span>
    <button
      class="pdf-toolbar-btn"
      onclick={nextPage}
      disabled={state.currentPage >= state.totalPages}
      title="Next page (Right arrow)"
    >
      <svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <polyline points="9 18 15 12 9 6"></polyline>
      </svg>
    </button>
  </div>

  <div class="pdf-toolbar-center">
    <span class="pdf-filename" title={state.filename}>{state.filename}</span>
  </div>

  <div class="pdf-toolbar-right">
    <button class="pdf-toolbar-btn" onclick={zoomOut} disabled={state.zoom <= 0.5} title="Zoom out">
      <svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <circle cx="11" cy="11" r="8"></circle>
        <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
        <line x1="8" y1="11" x2="14" y2="11"></line>
      </svg>
    </button>
    <button class="pdf-zoom-indicator" onclick={resetZoom} title="Reset zoom">
      {formatZoom(state.zoom)}
    </button>
    <button class="pdf-toolbar-btn" onclick={zoomIn} disabled={state.zoom >= 3.0} title="Zoom in">
      <svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <circle cx="11" cy="11" r="8"></circle>
        <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
        <line x1="11" y1="8" x2="11" y2="14"></line>
        <line x1="8" y1="11" x2="14" y2="11"></line>
      </svg>
    </button>

    <div class="pdf-toolbar-divider"></div>

    <button class="pdf-toolbar-btn" onclick={handleDownload} title="Download PDF">
      <svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
        <polyline points="7 10 12 15 17 10"></polyline>
        <line x1="12" y1="15" x2="12" y2="3"></line>
      </svg>
    </button>

    <button class="pdf-toolbar-btn pdf-close-btn" onclick={handleClose} title="Close (Escape)">
      <svg
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <line x1="18" y1="6" x2="6" y2="18"></line>
        <line x1="6" y1="6" x2="18" y2="18"></line>
      </svg>
    </button>
  </div>
</div>

<style>
  .pdf-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 16px;
    background: rgba(30, 30, 30, 0.95);
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    user-select: none;
  }

  .pdf-toolbar-left,
  .pdf-toolbar-right {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .pdf-toolbar-center {
    flex: 1;
    display: flex;
    justify-content: center;
    min-width: 0;
  }

  .pdf-toolbar-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    border: none;
    background: transparent;
    color: rgba(255, 255, 255, 0.8);
    border-radius: 4px;
    cursor: pointer;
    transition: background 0.15s, color 0.15s;
  }

  .pdf-toolbar-btn:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.1);
    color: white;
  }

  .pdf-toolbar-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .pdf-close-btn {
    margin-left: 8px;
  }

  .pdf-close-btn:hover:not(:disabled) {
    background: rgba(220, 38, 38, 0.3);
    color: #f87171;
  }

  .pdf-page-indicator {
    color: rgba(255, 255, 255, 0.8);
    font-size: 13px;
    font-weight: 500;
    padding: 0 8px;
    min-width: 60px;
    text-align: center;
  }

  .pdf-filename {
    color: rgba(255, 255, 255, 0.9);
    font-size: 13px;
    font-weight: 500;
    max-width: 300px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .pdf-zoom-indicator {
    color: rgba(255, 255, 255, 0.8);
    font-size: 12px;
    font-weight: 500;
    padding: 4px 8px;
    min-width: 50px;
    text-align: center;
    background: transparent;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    transition: background 0.15s;
  }

  .pdf-zoom-indicator:hover {
    background: rgba(255, 255, 255, 0.1);
  }

  .pdf-toolbar-divider {
    width: 1px;
    height: 20px;
    background: rgba(255, 255, 255, 0.2);
    margin: 0 8px;
  }
</style>
