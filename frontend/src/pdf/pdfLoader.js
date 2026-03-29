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
 * Extract text from a PDF file as markdown with page separators.
 * Runs entirely client-side — no server-side parsing needed.
 * @param {ArrayBuffer} data - The PDF file contents
 * @returns {Promise<{title: string, content: string}>}
 */
export async function extractTextFromPdf(data) {
  const pdfjs = await initPdfJs();

  const doc = await pdfjs.getDocument({
    data,
    cMapUrl: "https://cdn.jsdelivr.net/npm/pdfjs-dist@4.8.69/cmaps/",
    cMapPacked: true,
  }).promise;

  // Try to get title from PDF metadata
  const metadata = await doc.getMetadata().catch(() => null);
  const metaTitle = (metadata?.info?.Title || "").trim();

  const pageTexts = [];
  for (let i = 1; i <= doc.numPages; i++) {
    const page = await doc.getPage(i);
    const textContent = await page.getTextContent();

    // Join text items, preserving line breaks where items are on different lines.
    // When items are on the same line, insert a space between them if neither
    // side already has whitespace — many PDFs emit each word as a separate item.
    let lastY = null;
    let lastHadEOL = false;
    const parts = [];
    for (const item of textContent.items) {
      if (!item.str) continue;
      const y = item.transform[5];
      if (lastHadEOL || (lastY !== null && Math.abs(y - lastY) > 2)) {
        parts.push("\n");
      } else if (parts.length > 0) {
        const prev = parts[parts.length - 1];
        if (!/\s$/.test(prev) && !/^\s/.test(item.str)) {
          parts.push(" ");
        }
      }
      parts.push(item.str);
      lastY = y;
      lastHadEOL = !!item.hasEOL;
    }

    const text = parts.join("").trim();
    if (text) {
      pageTexts.push(`# Page ${i}\n\n${text}`);
    }
  }

  doc.destroy();

  return {
    title: metaTitle,
    content: pageTexts.join("\n\n"),
  };
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
