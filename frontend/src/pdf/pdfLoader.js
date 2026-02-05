/**
 * PDF.js Loader
 *
 * Handles lazy loading and configuration of PDF.js library.
 * Uses a web worker for PDF parsing to keep the main thread responsive.
 */

let pdfjsLib = null;
let initPromise = null;

/**
 * Initialize PDF.js library with worker configuration.
 * Lazy loads the library on first use.
 * @returns {Promise<typeof import('pdfjs-dist')>}
 */
async function initPdfJs() {
  if (pdfjsLib) {
    return pdfjsLib;
  }

  if (initPromise) {
    return initPromise;
  }

  initPromise = (async () => {
    const pdfjs = await import("pdfjs-dist");

    // Configure the worker - use the bundled worker file
    pdfjs.GlobalWorkerOptions.workerSrc = new URL(
      "pdfjs-dist/build/pdf.worker.min.mjs",
      import.meta.url
    ).toString();

    pdfjsLib = pdfjs;
    return pdfjsLib;
  })();

  return initPromise;
}

/**
 * Load a PDF document from a URL.
 * @param {string} url - The URL of the PDF file
 * @returns {Promise<import('pdfjs-dist').PDFDocumentProxy>}
 */
export async function loadPdf(url) {
  const pdfjs = await initPdfJs();

  const loadingTask = pdfjs.getDocument({
    url,
    // Enable text layer for selection
    cMapUrl: "https://cdn.jsdelivr.net/npm/pdfjs-dist@4.8.69/cmaps/",
    cMapPacked: true,
  });

  return loadingTask.promise;
}

/**
 * Render a PDF page to a canvas.
 * @param {import('pdfjs-dist').PDFPageProxy} page - The PDF page
 * @param {HTMLCanvasElement} canvas - The canvas element to render to
 * @param {number} scale - The scale/zoom level
 * @returns {Promise<{width: number, height: number}>} The rendered dimensions
 */
export async function renderPage(page, canvas, scale = 1.0) {
  const viewport = page.getViewport({ scale });

  // Set canvas dimensions for the given scale
  const outputScale = window.devicePixelRatio || 1;
  canvas.width = Math.floor(viewport.width * outputScale);
  canvas.height = Math.floor(viewport.height * outputScale);
  canvas.style.width = `${Math.floor(viewport.width)}px`;
  canvas.style.height = `${Math.floor(viewport.height)}px`;

  const ctx = canvas.getContext("2d");
  ctx.scale(outputScale, outputScale);

  const renderContext = {
    canvasContext: ctx,
    viewport,
  };

  await page.render(renderContext).promise;

  return {
    width: viewport.width,
    height: viewport.height,
  };
}

/**
 * Get the text content of a PDF page for the text layer.
 * @param {import('pdfjs-dist').PDFPageProxy} page - The PDF page
 * @returns {Promise<import('pdfjs-dist').TextContent>}
 */
export async function getTextContent(page) {
  return page.getTextContent();
}

/**
 * Create a text layer div with selectable text.
 * @param {import('pdfjs-dist').TextContent} textContent - Text content from getTextContent
 * @param {HTMLDivElement} container - Container div for the text layer
 * @param {import('pdfjs-dist').PageViewport} viewport - The viewport for positioning
 */
export async function renderTextLayer(textContent, container, viewport) {
  const pdfjs = await initPdfJs();

  // Clear existing content
  container.innerHTML = "";

  // Use PDF.js TextLayer for proper text positioning
  const textLayer = new pdfjs.TextLayer({
    textContentSource: textContent,
    container,
    viewport,
  });

  await textLayer.render();
}
