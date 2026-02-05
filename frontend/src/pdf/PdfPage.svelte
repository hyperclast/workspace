<script>
  /**
   * PDF Page Component
   *
   * Renders a single PDF page with canvas and optional text layer.
   * The text layer is invisible but allows text selection.
   */
  import { onMount } from "svelte";
  import { renderPage, getTextContent, renderTextLayer } from "./pdfLoader.js";

  /** @type {import('pdfjs-dist').PDFPageProxy} */
  let { page, scale = 1.0 } = $props();

  let canvasRef = $state(null);
  let textLayerRef = $state(null);
  let dimensions = $state({ width: 0, height: 0 });

  async function render() {
    if (!page || !canvasRef) return;

    try {
      // Render the page to canvas
      const viewport = page.getViewport({ scale });
      dimensions = await renderPage(page, canvasRef, scale);

      // Render text layer for selection
      if (textLayerRef) {
        const textContent = await getTextContent(page);
        await renderTextLayer(textContent, textLayerRef, viewport);
      }
    } catch (err) {
      console.error("Error rendering PDF page:", err);
    }
  }

  // Re-render when page or scale changes
  $effect(() => {
    if (page && canvasRef) {
      render();
    }
  });

  onMount(() => {
    render();
  });
</script>

<div class="pdf-page" class:pdf-page-ready={dimensions.width > 0}>
  <canvas bind:this={canvasRef} class="pdf-page-canvas"></canvas>
  <div bind:this={textLayerRef} class="pdf-text-layer"></div>
</div>

<style>
  .pdf-page {
    position: relative;
    margin: 0 auto;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
    background: white;
    /* Hidden until rendered to prevent grow-from-corner effect */
    opacity: 0;
  }

  .pdf-page-ready {
    opacity: 1;
  }

  .pdf-page-canvas {
    display: block;
  }

  .pdf-text-layer {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    overflow: hidden;
    opacity: 0.2;
    line-height: 1;
    pointer-events: auto;
  }

  /* PDF.js text layer styles */
  .pdf-text-layer :global(span) {
    color: transparent;
    position: absolute;
    white-space: pre;
    transform-origin: 0 0;
  }

  .pdf-text-layer :global(span::selection) {
    background: rgba(35, 131, 226, 0.5);
  }
</style>
