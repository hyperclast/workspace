/**
 * Incremental upsert of PDF comment rectangles into per-page overlay divs.
 *
 * The overlay holds a `Map<pageNumber, Map<commentId, HTMLElement[]>>` and
 * reuses existing `<div class="pdf-comment-rect">` nodes instead of clearing
 * the overlay's `innerHTML` on every paint. A rectangle is created only when
 * a new comment appears, removed only when its comment goes away, and
 * repositioned in place when the viewport changes (e.g. on resize/zoom).
 *
 * Each rect element carries a live `_commentRef` pointing at the latest
 * comment object, so the click handler always dispatches the up-to-date
 * `pdf_anchor` even after a comment is edited.
 *
 * @param {{
 *   pages: Array<{pageNumber: number, viewport: import('pdfjs-dist').PageViewport}>,
 *   comments: Array<{external_id: string, parent: any, pdf_anchor: any}>,
 *   rectsByPage: Map<number, Map<string, HTMLElement[]>>,
 *   anchorToViewportRects: (pdfAnchor: any, viewport: any) =>
 *     Array<{left: number, top: number, width: number, height: number}>,
 *   doc?: Document,
 * }} args
 */
export function paintPdfRects({
  pages,
  comments,
  rectsByPage,
  anchorToViewportRects,
  doc = typeof document !== "undefined" ? document : null,
}) {
  if (!doc || !pages || !pages.length) return;

  for (const { pageNumber, viewport } of pages) {
    const wrapper = doc.querySelector(`[data-pdf-page="${pageNumber}"]`);
    if (!wrapper) continue;
    const overlayEl = wrapper.querySelector(".pdf-comment-overlay");
    if (!overlayEl) continue;

    let pageMap = rectsByPage.get(pageNumber);
    if (!pageMap) {
      pageMap = new Map();
      rectsByPage.set(pageNumber, pageMap);
    }

    const onPage = comments.filter(
      (c) => c.pdf_anchor && c.pdf_anchor.page === pageNumber && !c.parent
    );
    const desiredIds = new Set(onPage.map((c) => c.external_id));

    for (const [cid, els] of pageMap) {
      if (desiredIds.has(cid)) continue;
      for (const el of els) el.remove();
      pageMap.delete(cid);
    }

    for (const c of onPage) {
      const vRects = viewport ? anchorToViewportRects(c.pdf_anchor, viewport) : [];
      let els = pageMap.get(c.external_id);
      if (!els) {
        els = [];
        pageMap.set(c.external_id, els);
      }

      while (els.length > vRects.length) {
        const extra = els.pop();
        if (extra) extra.remove();
      }

      for (let i = 0; i < vRects.length; i++) {
        const r = vRects[i];
        let el = els[i];
        if (!el) {
          el = createRectElement(c, doc);
          overlayEl.appendChild(el);
          els[i] = el;
        }
        el._commentRef = c;
        el.style.left = `${r.left}px`;
        el.style.top = `${r.top}px`;
        el.style.width = `${r.width}px`;
        el.style.height = `${r.height}px`;
      }

      if (els.length === 0) pageMap.delete(c.external_id);
    }
  }
}

/**
 * Tear down rect elements stored in `rectsByPage` (e.g. on unmount or when
 * the page list is replaced wholesale by a different document).
 *
 * @param {Map<number, Map<string, HTMLElement[]>>} rectsByPage
 */
export function clearPdfRects(rectsByPage) {
  for (const pageMap of rectsByPage.values()) {
    for (const els of pageMap.values()) {
      for (const el of els) el.remove();
    }
  }
  rectsByPage.clear();
}

function createRectElement(c, doc) {
  const el = doc.createElement("div");
  el.className = "pdf-comment-rect";
  el.dataset.commentId = c.external_id;
  Object.assign(el.style, {
    position: "absolute",
    background: "rgba(255, 213, 80, 0.45)",
    cursor: "pointer",
    pointerEvents: "auto",
    borderRadius: "1px",
  });
  el._commentRef = c;
  el.addEventListener("click", (event) => {
    event.stopPropagation();
    const ref = el._commentRef;
    if (!ref) return;
    const view = doc.defaultView || (typeof window !== "undefined" ? window : null);
    if (!view) return;
    view.dispatchEvent(
      new view.CustomEvent("pdfCommentSelected", {
        detail: { commentId: ref.external_id, pdf_anchor: ref.pdf_anchor },
      })
    );
  });
  return el;
}
