/**
 * PDF Anchor helpers.
 *
 * Anchors are stored in PDF user-space coordinates (zoom/rotation independent),
 * using the shape:
 *   { page: 1-indexed int, rects: [{x, y, w, h}, ...], text: string }
 *
 * - `viewport.convertToPdfPoint(x, y)` converts viewport coordinates → PDF user-space.
 * - `viewport.convertToViewportRectangle([x1, y1, x2, y2])` converts back.
 *
 * In PDF user-space the y-axis is flipped (origin at bottom-left) and 1 unit
 * = 1/72 inch. Storing in PDF user-space lets us re-render rectangles correctly
 * at any zoom or rotation.
 */

export const PDF_ANCHOR_MAX_RECTS = 50;
export const PDF_ANCHOR_TEXT_MAX_LENGTH = 4000;

/**
 * Build a pdf_anchor payload from a Selection on a PDF text layer.
 *
 * @param {Range} range — DOM Range (single-page only)
 * @param {number} pageNumber — 1-indexed PDF page number
 * @param {object} pageContainer — DOM element wrapping the canvas + text layer
 *   (used to translate client rects into the page's local coord space)
 * @param {import('pdfjs-dist').PageViewport} viewport — viewport used to render the page
 * @returns {{page:number, rects:Array<{x,y,w,h}>, text:string}|null}
 */
export function rangeToPdfAnchor(range, pageNumber, pageContainer, viewport) {
  if (!range || range.collapsed) return null;
  if (!pageContainer || !viewport) return null;

  const text = (range.toString() || "").trim();
  if (!text) return null;

  const containerRect = pageContainer.getBoundingClientRect();
  const clientRects = Array.from(range.getClientRects()).filter((r) => r.width > 0 && r.height > 0);
  if (clientRects.length === 0) return null;

  // Cap the number of rects we store; collapse extras into the bounding box.
  const rectsToConvert =
    clientRects.length <= PDF_ANCHOR_MAX_RECTS ? clientRects : [unionRect(clientRects)];

  const pdfRects = [];
  for (const r of rectsToConvert) {
    // Translate to local viewport coords
    const x1 = r.left - containerRect.left;
    const y1 = r.top - containerRect.top;
    const x2 = r.right - containerRect.left;
    const y2 = r.bottom - containerRect.top;

    // Convert to PDF user-space (flips y, scales by 1/scale).
    const [px1, py1] = viewport.convertToPdfPoint(x1, y1);
    const [px2, py2] = viewport.convertToPdfPoint(x2, y2);

    const x = Math.min(px1, px2);
    const y = Math.min(py1, py2);
    const w = Math.abs(px2 - px1);
    const h = Math.abs(py2 - py1);

    if (w > 0 && h > 0) {
      pdfRects.push({ x, y, w, h });
    }
  }

  if (pdfRects.length === 0) return null;

  return {
    page: pageNumber,
    rects: pdfRects,
    text: text.slice(0, PDF_ANCHOR_TEXT_MAX_LENGTH),
  };
}

/**
 * Convert stored PDF-space rects into viewport rects (in CSS pixels)
 * for overlay rendering at the current zoom.
 *
 * @param {{rects: Array<{x,y,w,h}>}} pdfAnchor
 * @param {import('pdfjs-dist').PageViewport} viewport
 * @returns {Array<{left:number, top:number, width:number, height:number}>}
 */
export function pdfAnchorToViewportRects(pdfAnchor, viewport) {
  if (!pdfAnchor || !Array.isArray(pdfAnchor.rects) || !viewport) return [];

  return pdfAnchor.rects.map((r) => {
    const [vx1, vy1, vx2, vy2] = viewport.convertToViewportRectangle([
      r.x,
      r.y,
      r.x + r.w,
      r.y + r.h,
    ]);
    const left = Math.min(vx1, vx2);
    const top = Math.min(vy1, vy2);
    const width = Math.abs(vx2 - vx1);
    const height = Math.abs(vy2 - vy1);
    return { left, top, width, height };
  });
}

/**
 * Returns true if the selection spans more than one PDF page.
 * The PDF text layer marks each page with a `data-pdf-page` attribute.
 */
export function rangeSpansMultiplePages(range) {
  if (!range) return false;
  const start = closestPageEl(range.startContainer);
  const end = closestPageEl(range.endContainer);
  if (!start || !end) return false;
  return start !== end;
}

function closestPageEl(node) {
  let el = node && node.nodeType === 1 ? node : node && node.parentElement;
  while (el && !el.dataset?.pdfPage) {
    el = el.parentElement;
  }
  return el || null;
}

function unionRect(rects) {
  let left = Infinity;
  let top = Infinity;
  let right = -Infinity;
  let bottom = -Infinity;
  for (const r of rects) {
    if (r.left < left) left = r.left;
    if (r.top < top) top = r.top;
    if (r.right > right) right = r.right;
    if (r.bottom > bottom) bottom = r.bottom;
  }
  return { left, top, right, bottom, width: right - left, height: bottom - top };
}
