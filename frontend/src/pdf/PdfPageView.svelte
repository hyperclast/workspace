<script>
  /**
   * PDF Page View — inline scrollable PDF rendering for filetype:"pdf" pages.
   *
   * Renders pages lazily as they enter the viewport so opening a long PDF
   * doesn't paint hundreds of canvases up front. Each page wrapper exposes a
   * `data-pdf-page="N"` attribute so selection-handling code can identify the
   * source page. Page metadata and selection events are exposed to child
   * components via Svelte context (see `pdfPageContext.js`); window events
   * are reserved for cross-tree signals like `pdfFocusAnchor`.
   */
  import { onMount, onDestroy, setContext } from "svelte";
  import { loadPdf, renderPage, getTextContent, renderTextLayer } from "./pdfLoader.js";
  import PdfCommentPopover from "./PdfCommentPopover.svelte";
  import PdfCommentOverlay from "./PdfCommentOverlay.svelte";
  import { PDF_PAGE_CONTEXT, createPdfPageContext } from "./pdfPageContext.js";

  const pdfPageCtx = createPdfPageContext();
  setContext(PDF_PAGE_CONTEXT, pdfPageCtx);

  let { fileDownloadUrl, pageId, maxScale = 2.0 } = $props();

  let containerRef = $state(null);
  let loading = $state(true);
  let error = $state(null);
  let pdfDoc = null;
  // Each entry: { wrapper, canvas, textLayer, overlay, pdfPage, viewport,
  //               pageNumber, rendered, renderingPromise }
  let pageEls = [];
  let currentScale = 1.0;
  let resizeRaf = null;
  let lastRenderedWidth = 0;
  let pageObserver = null;

  // Render pages within ~1 viewport above and below the visible area so
  // smooth scrolling doesn't reveal blank canvases.
  const OBSERVER_ROOT_MARGIN = "100% 0px";

  // Horizontal padding inside the .pdf-page-view container.
  const HORIZONTAL_PADDING_PX = 32;

  function computeFitScale(unscaledWidth) {
    if (!containerRef) return 1.0;
    const available = Math.max(200, containerRef.clientWidth - HORIZONTAL_PADDING_PX);
    return Math.min(maxScale, available / unscaledWidth);
  }

  async function load() {
    if (!fileDownloadUrl) {
      error = "PDF file is not available.";
      loading = false;
      dispatchFirstPaint({ status: "error", reason: "missing_file" });
      return;
    }

    loading = true;
    error = null;

    try {
      pdfDoc = await loadPdf(fileDownloadUrl);
      await buildLayout();
      loading = false;
    } catch (err) {
      console.error("[PdfPageView] failed to load PDF:", err);
      error = "Failed to load PDF.";
      loading = false;
      dispatchFirstPaint({ status: "error", reason: String(err) });
    }
  }

  // The page-load telemetry span in main.js needs to know when the first
  // page has actually painted (or when loading failed). Fire exactly once
  // per PdfPageView instance so the listener can settle the span.
  let firstPaintDispatched = false;
  function dispatchFirstPaint(detail) {
    if (firstPaintDispatched) return;
    firstPaintDispatched = true;
    window.dispatchEvent(
      new CustomEvent("pdfFirstPageRendered", {
        detail: { pageId, ...detail },
      }),
    );
  }

  function createPageWrapper(pageNumber, width, height) {
    const wrapper = document.createElement("div");
    wrapper.className = "pdf-page-wrapper";
    wrapper.dataset.pdfPage = String(pageNumber);
    wrapper.style.position = "relative";
    wrapper.style.margin = "0 auto 16px";
    wrapper.style.width = `${Math.floor(width)}px`;
    wrapper.style.height = `${Math.floor(height)}px`;
    wrapper.style.background = "white";
    wrapper.style.boxShadow = "0 2px 8px rgba(0, 0, 0, 0.15)";

    const canvas = document.createElement("canvas");
    canvas.className = "pdf-page-canvas";
    canvas.style.display = "block";
    wrapper.appendChild(canvas);

    const textLayer = document.createElement("div");
    textLayer.className = "pdf-text-layer";
    Object.assign(textLayer.style, {
      position: "absolute",
      inset: "0",
      overflow: "hidden",
      opacity: "0.2",
      lineHeight: "1",
    });
    wrapper.appendChild(textLayer);

    const overlay = document.createElement("div");
    overlay.className = "pdf-comment-overlay";
    Object.assign(overlay.style, {
      position: "absolute",
      inset: "0",
      pointerEvents: "none",
    });
    wrapper.appendChild(overlay);

    return { wrapper, canvas, textLayer, overlay };
  }

  async function buildLayout() {
    if (!pdfDoc || !containerRef) return;

    teardownObserver();
    containerRef.innerHTML = "";
    pageEls = [];

    // Compute scale from page 1's natural width so all pages render at the
    // same scale (typical PDFs have uniform page sizes).
    const firstPage = await pdfDoc.getPage(1);
    const baseViewport = firstPage.getViewport({ scale: 1 });
    currentScale = computeFitScale(baseViewport.width);
    lastRenderedWidth = containerRef.clientWidth;

    const firstViewport = firstPage.getViewport({ scale: currentScale });

    // Lay out wrappers for every page using page 1's dimensions as a
    // placeholder. Most PDFs have uniform page sizes; pages that differ get
    // their dimensions corrected when ensurePageRendered() runs.
    for (let i = 1; i <= pdfDoc.numPages; i++) {
      const { wrapper, canvas, textLayer, overlay } = createPageWrapper(
        i,
        firstViewport.width,
        firstViewport.height,
      );
      containerRef.appendChild(wrapper);
      pageEls.push({
        wrapper,
        canvas,
        textLayer,
        overlay,
        pdfPage: i === 1 ? firstPage : null,
        viewport: i === 1 ? firstViewport : firstViewport,
        pageNumber: i,
        rendered: false,
        renderingPromise: null,
      });
    }

    // Render page 1 eagerly so the first-paint telemetry can settle and the
    // user sees the document immediately. Subsequent pages render lazily.
    await ensurePageRendered(pageEls[0]);

    setupPageObserver();

    publishPages();
  }

  function publishPages() {
    pdfPageCtx.pages.set(
      pageEls.map((p) => ({ pageNumber: p.pageNumber, viewport: p.viewport })),
    );
  }

  async function ensurePageRendered(pe) {
    if (!pe || pe.rendered) return;
    if (pe.renderingPromise) return pe.renderingPromise;

    pe.renderingPromise = (async () => {
      try {
        if (!pe.pdfPage) {
          pe.pdfPage = await pdfDoc.getPage(pe.pageNumber);
        }
        const viewport = pe.pdfPage.getViewport({ scale: currentScale });
        const sizeChanged =
          !pe.viewport ||
          Math.abs(pe.viewport.width - viewport.width) > 0.5 ||
          Math.abs(pe.viewport.height - viewport.height) > 0.5;
        pe.viewport = viewport;
        if (sizeChanged) {
          pe.wrapper.style.width = `${Math.floor(viewport.width)}px`;
          pe.wrapper.style.height = `${Math.floor(viewport.height)}px`;
        }

        await renderPage(pe.pdfPage, pe.canvas, currentScale);
        if (pe.pageNumber === 1) {
          dispatchFirstPaint({ status: "success" });
        }
        const textContent = await getTextContent(pe.pdfPage);
        await renderTextLayer(textContent, pe.textLayer, viewport);

        pe.rendered = true;

        // Tell the overlay to (re)position rects on this page now that we
        // know its real viewport.
        pdfPageCtx.pages.update((arr) =>
          arr.map((p) =>
            p.pageNumber === pe.pageNumber ? { pageNumber: p.pageNumber, viewport } : p,
          ),
        );
      } finally {
        pe.renderingPromise = null;
      }
    })();

    return pe.renderingPromise;
  }

  function setupPageObserver() {
    teardownObserver();
    if (!containerRef || typeof IntersectionObserver === "undefined") {
      // No observer available — eagerly render everything as a fallback.
      for (const pe of pageEls) {
        ensurePageRendered(pe).catch((err) =>
          console.error("[PdfPageView] page render failed:", err),
        );
      }
      return;
    }

    pageObserver = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          const pageNum = Number(entry.target.dataset.pdfPage);
          const pe = pageEls.find((p) => p.pageNumber === pageNum);
          if (!pe) continue;
          ensurePageRendered(pe).catch((err) =>
            console.error("[PdfPageView] page render failed:", err),
          );
        }
      },
      { root: containerRef, rootMargin: OBSERVER_ROOT_MARGIN },
    );

    for (const pe of pageEls) {
      pageObserver.observe(pe.wrapper);
    }
  }

  function teardownObserver() {
    if (pageObserver) {
      pageObserver.disconnect();
      pageObserver = null;
    }
  }

  function handleSelectionChange() {
    const sel = document.getSelection();
    if (!sel || sel.rangeCount === 0 || sel.isCollapsed) return;

    const range = sel.getRangeAt(0);
    const node = range.startContainer;
    // Only react if selection started inside our text layer
    const wrapper = closestPageWrapper(node);
    if (!wrapper) return;

    pdfPageCtx.selection.set({
      range,
      pageNumber: Number(wrapper.dataset.pdfPage),
    });
  }

  function closestPageWrapper(node) {
    let el = node && node.nodeType === 1 ? node : node && node.parentElement;
    while (el && !el.dataset?.pdfPage) el = el.parentElement;
    return el;
  }

  function handleFocusAnchor(event) {
    const { pdf_anchor } = event.detail || {};
    if (!pdf_anchor) return;
    const target = pageEls.find((p) => p.pageNumber === pdf_anchor.page);
    if (!target) return;
    target.wrapper.scrollIntoView({ behavior: "smooth", block: "center" });
    target.wrapper.classList.remove("pdf-page-pulse");
    // Restart animation
    void target.wrapper.offsetWidth;
    target.wrapper.classList.add("pdf-page-pulse");
    // The observer will pick this up if the page wasn't rendered yet, but
    // smooth-scroll defers intersection updates by a frame — render now so
    // the destination is ready by the time the scroll lands.
    ensurePageRendered(target).catch((err) =>
      console.error("[PdfPageView] focus render failed:", err),
    );
  }

  function handleResize() {
    if (!containerRef || !pdfDoc) return;
    const w = containerRef.clientWidth;
    // Re-render only on meaningful width changes to avoid thrash.
    if (Math.abs(w - lastRenderedWidth) < 24) return;
    if (resizeRaf) cancelAnimationFrame(resizeRaf);
    resizeRaf = requestAnimationFrame(() => {
      resizeRaf = null;
      rescale().catch((err) => console.error("[PdfPageView] resize re-render failed:", err));
    });
  }

  async function rescale() {
    if (!containerRef || !pageEls.length || !pageEls[0]?.pdfPage) return;

    const firstPage = pageEls[0].pdfPage;
    const baseViewport = firstPage.getViewport({ scale: 1 });
    currentScale = computeFitScale(baseViewport.width);
    lastRenderedWidth = containerRef.clientWidth;

    const placeholder = firstPage.getViewport({ scale: currentScale });

    // Update layout for every wrapper without tearing the DOM down. Pages we
    // haven't resolved a PDFPageProxy for yet keep page 1's dimensions; their
    // real viewport is applied when ensurePageRendered() runs.
    for (const pe of pageEls) {
      const v = pe.pdfPage ? pe.pdfPage.getViewport({ scale: currentScale }) : placeholder;
      pe.viewport = v;
      pe.wrapper.style.width = `${Math.floor(v.width)}px`;
      pe.wrapper.style.height = `${Math.floor(v.height)}px`;
      pe.rendered = false;
      pe.textLayer.innerHTML = "";
      // Canvas pixels become stale at the new scale; renderPage() will reset
      // dimensions and repaint, but until then leave the canvas blank rather
      // than show a stretched bitmap.
      const ctx = pe.canvas.getContext("2d");
      if (ctx) ctx.clearRect(0, 0, pe.canvas.width, pe.canvas.height);
    }

    publishPages();

    // The IntersectionObserver doesn't refire for pages that stay visible
    // across the resize, so trigger renders for currently-visible pages
    // manually. The observer will lazily render others as they scroll in.
    const cR = containerRef.getBoundingClientRect();
    const margin = cR.height; // ~1 viewport above/below, matching the observer.
    for (const pe of pageEls) {
      const r = pe.wrapper.getBoundingClientRect();
      if (r.bottom >= cR.top - margin && r.top <= cR.bottom + margin) {
        ensurePageRendered(pe).catch((err) =>
          console.error("[PdfPageView] re-render after resize failed:", err),
        );
      }
    }
  }

  let resizeObserver = null;

  onMount(() => {
    load();
    document.addEventListener("selectionchange", handleSelectionChange);
    window.addEventListener("pdfFocusAnchor", handleFocusAnchor);
    if (containerRef && typeof ResizeObserver !== "undefined") {
      resizeObserver = new ResizeObserver(handleResize);
      resizeObserver.observe(containerRef);
    }
    return () => {
      document.removeEventListener("selectionchange", handleSelectionChange);
      window.removeEventListener("pdfFocusAnchor", handleFocusAnchor);
      if (resizeObserver) {
        resizeObserver.disconnect();
        resizeObserver = null;
      }
      if (resizeRaf) {
        cancelAnimationFrame(resizeRaf);
        resizeRaf = null;
      }
      teardownObserver();
    };
  });

  onDestroy(() => {
    if (pdfDoc) {
      try {
        pdfDoc.destroy();
      } catch (err) {
        console.warn("[PdfPageView] pdfDoc.destroy() failed:", err);
      }
      pdfDoc = null;
    }
  });
</script>

<div class="pdf-page-view">
  {#if loading}
    <div class="pdf-status">Loading PDF…</div>
  {:else if error}
    <div class="pdf-status pdf-status-error">
      {error}
      {#if fileDownloadUrl}
        <a href={fileDownloadUrl} target="_blank" rel="noopener">Download instead</a>
      {/if}
    </div>
  {/if}
  <div bind:this={containerRef} class="pdf-pages"></div>
  {#if pageId}
    <PdfCommentOverlay {pageId} />
    <PdfCommentPopover {pageId} />
  {/if}
</div>

<style>
  .pdf-page-view {
    width: 100%;
    height: 100%;
    overflow: auto;
    padding: 16px;
    background: var(--bg-secondary, #f5f5f5);
    /* Anchor absolutely-positioned children (PdfCommentPopover) so they
       scroll with the PDF content instead of staying pinned to the
       window. */
    position: relative;
  }

  .pdf-pages {
    display: block;
  }

  .pdf-status {
    text-align: center;
    color: var(--text-secondary, #666);
    font-size: 14px;
    padding: 24px;
  }

  .pdf-status-error {
    color: #c0392b;
  }

  /* Text layer styles mirror PdfPage.svelte */
  :global(.pdf-text-layer span) {
    color: transparent;
    position: absolute;
    white-space: pre;
    transform-origin: 0 0;
  }

  :global(.pdf-text-layer span::selection) {
    background: rgba(35, 131, 226, 0.5);
  }

  :global(.pdf-page-pulse) {
    animation: pdf-page-pulse 1.2s ease-out;
  }

  @keyframes pdf-page-pulse {
    0% {
      box-shadow: 0 0 0 0 rgba(255, 213, 80, 0.6);
    }
    100% {
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
    }
  }
</style>
