<script>
  /**
   * PDF Viewer Component
   *
   * Full-screen modal overlay for viewing PDFs in-app.
   * Features:
   * - Page navigation (arrows, j/k, Home/End)
   * - Zoom controls (+/-)
   * - Text selection
   * - Download option
   * - Keyboard shortcuts
   * - Touch support for mobile
   */
  import { onMount } from "svelte";
  import { loadPdf } from "./pdfLoader.js";
  import PdfPage from "./PdfPage.svelte";
  import PdfToolbar from "./PdfToolbar.svelte";
  import {
    getPdfViewerState,
    closePdfViewer,
    setTotalPages,
    setCurrentPage,
    setLoading,
    setError,
    prevPage,
    nextPage,
    firstPage,
    lastPage,
    zoomIn,
    zoomOut,
  } from "../lib/stores/pdfViewer.svelte.js";

  let viewerState = getPdfViewerState();
  let pdfDoc = $state(null);
  let currentPageObj = $state(null);
  let containerRef = $state(null);
  let touchStartX = $state(0);
  let touchStartY = $state(0);

  // Load PDF when URL changes
  $effect(() => {
    if (viewerState.open && viewerState.url) {
      loadDocument();
    }
  });

  // Load page when current page changes
  $effect(() => {
    if (pdfDoc && viewerState.currentPage) {
      loadPage(viewerState.currentPage);
    }
  });

  async function loadDocument() {
    setLoading(true);
    setError(null);
    pdfDoc = null;
    currentPageObj = null;

    try {
      const doc = await loadPdf(viewerState.url);
      pdfDoc = doc;
      setTotalPages(doc.numPages);
      setLoading(false);

      // Load first page
      await loadPage(1);
    } catch (err) {
      console.error("Error loading PDF:", err);
      setError("Failed to load PDF. The file may be corrupted or inaccessible.");
    }
  }

  async function loadPage(pageNum) {
    if (!pdfDoc) return;

    try {
      const page = await pdfDoc.getPage(pageNum);
      currentPageObj = page;
    } catch (err) {
      console.error("Error loading page:", err);
      setError(`Failed to load page ${pageNum}.`);
    }
  }

  function handleKeydown(event) {
    if (!viewerState.open) return;

    switch (event.key) {
      case "Escape":
        closePdfViewer();
        break;
      case "ArrowLeft":
      case "k":
        event.preventDefault();
        prevPage();
        break;
      case "ArrowRight":
      case "j":
        event.preventDefault();
        nextPage();
        break;
      case "Home":
        event.preventDefault();
        firstPage();
        break;
      case "End":
        event.preventDefault();
        lastPage();
        break;
      case "+":
      case "=":
        event.preventDefault();
        zoomIn();
        break;
      case "-":
        event.preventDefault();
        zoomOut();
        break;
    }
  }

  function handleBackdropClick(event) {
    // Close only if clicking the backdrop itself, not the content
    if (event.target === containerRef) {
      closePdfViewer();
    }
  }

  // Touch navigation for mobile
  function handleTouchStart(event) {
    touchStartX = event.touches[0].clientX;
    touchStartY = event.touches[0].clientY;
  }

  function handleTouchEnd(event) {
    const touchEndX = event.changedTouches[0].clientX;
    const touchEndY = event.changedTouches[0].clientY;
    const deltaX = touchEndX - touchStartX;
    const deltaY = touchEndY - touchStartY;

    // Only handle horizontal swipes (ignore if mostly vertical)
    if (Math.abs(deltaX) > Math.abs(deltaY) && Math.abs(deltaX) > 50) {
      if (deltaX > 0) {
        prevPage();
      } else {
        nextPage();
      }
    }
  }

  onMount(() => {
    // Attach event listeners manually (Svelte 5 mount() issue workaround)
    const handleGlobalKeydown = (e) => handleKeydown(e);
    document.addEventListener("keydown", handleGlobalKeydown);

    return () => {
      document.removeEventListener("keydown", handleGlobalKeydown);
      // Clean up PDF document when unmounting
      if (pdfDoc) {
        pdfDoc.destroy();
      }
    };
  });
</script>

{#if viewerState.open}
  <!-- svelte-ignore a11y_no_noninteractive_element_interactions a11y_click_events_have_key_events -->
  <div
    class="pdf-viewer-overlay"
    bind:this={containerRef}
    onclick={handleBackdropClick}
    ontouchstart={handleTouchStart}
    ontouchend={handleTouchEnd}
    role="dialog"
    aria-label="PDF Viewer"
    aria-modal="true"
    tabindex="-1"
  >
    <div class="pdf-viewer-container">
      <PdfToolbar />

      <div class="pdf-viewer-content">
        {#if viewerState.loading}
          <div class="pdf-loading">
            <div class="pdf-loading-spinner"></div>
            <span>Loading PDF...</span>
          </div>
        {:else if viewerState.error}
          <div class="pdf-error">
            <svg
              width="48"
              height="48"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <circle cx="12" cy="12" r="10"></circle>
              <line x1="12" y1="8" x2="12" y2="12"></line>
              <line x1="12" y1="16" x2="12.01" y2="16"></line>
            </svg>
            <p>{viewerState.error}</p>
            <button class="pdf-error-btn" onclick={() => window.open(viewerState.url, "_blank")}>
              Download PDF instead
            </button>
          </div>
        {:else if currentPageObj}
          <div class="pdf-page-wrapper">
            <PdfPage page={currentPageObj} scale={viewerState.zoom} />
          </div>
        {/if}
      </div>
    </div>
  </div>
{/if}

<style>
  .pdf-viewer-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.95);
    z-index: 10000;
    display: flex;
    align-items: center;
    justify-content: center;
    animation: pdf-fade-in 0.15s ease-out;
  }

  @keyframes pdf-fade-in {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }

  .pdf-viewer-container {
    display: flex;
    flex-direction: column;
    width: 100%;
    height: 100%;
    max-width: 100vw;
    max-height: 100vh;
  }

  .pdf-viewer-content {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: auto;
    padding: 20px;
  }

  .pdf-page-wrapper {
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .pdf-loading {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 16px;
    color: rgba(255, 255, 255, 0.8);
    font-size: 14px;
  }

  .pdf-loading-spinner {
    width: 40px;
    height: 40px;
    border: 3px solid rgba(255, 255, 255, 0.2);
    border-top-color: rgba(255, 255, 255, 0.8);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  .pdf-error {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 16px;
    color: #f87171;
    text-align: center;
    max-width: 400px;
    padding: 40px;
  }

  .pdf-error p {
    color: rgba(255, 255, 255, 0.7);
    font-size: 14px;
    margin: 0;
  }

  .pdf-error-btn {
    padding: 10px 20px;
    background: rgba(255, 255, 255, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.2);
    color: white;
    border-radius: 6px;
    cursor: pointer;
    font-size: 14px;
    transition: background 0.15s;
  }

  .pdf-error-btn:hover {
    background: rgba(255, 255, 255, 0.2);
  }
</style>
