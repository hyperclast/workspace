<script>
  /**
   * Yellow rectangle overlay for PDF comments.
   *
   * Reads page metadata from the `PDF_PAGE_CONTEXT` store published by
   * PdfPageView. The store updates whenever:
   *   - the page list is (re)laid out (initial load, resize/zoom), or
   *   - a single page's real viewport becomes known after lazy render.
   *
   * Listens for `commentsUpdated` window events (cross-tree — fired from the
   * sidebar's CommentsTab) to refetch comments.
   *
   * For each comment with a `pdf_anchor`, paints rectangles into the
   * per-page overlay div (`.pdf-comment-overlay`) that PdfPageView created.
   * Rectangles are upserted incrementally (see `paintPdfRects`) so a
   * `commentsUpdated` storm doesn't tear down and rebuild every yellow box.
   *
   * Click on a rect → dispatches `pdfCommentSelected` so the sidebar can
   * scroll to that comment thread.
   */
  import { getContext, onMount } from "svelte";
  import { fetchComments } from "../api.js";
  import { pdfAnchorToViewportRects } from "./pdfAnchor.js";
  import { fetchAllRootComments } from "./fetchAllPdfComments.js";
  import { paintPdfRects, clearPdfRects } from "./paintPdfRects.js";
  import { PDF_PAGE_CONTEXT } from "./pdfPageContext.js";

  let { pageId } = $props();

  const ctx = getContext(PDF_PAGE_CONTEXT);

  let pages = []; // [{pageNumber, viewport}]
  let comments = [];
  // Map<pageNumber, Map<commentId, HTMLElement[]>>. Reused across paints so
  // unchanged rectangles aren't re-created on every commentsUpdated event.
  const rectsByPage = new Map();
  // Sequence token: a newer loadComments() call must invalidate older ones
  // so a slow earlier pagination chain can't overwrite the latest paint.
  let loadSeq = 0;

  async function loadComments() {
    if (!pageId) return;
    const mySeq = ++loadSeq;
    try {
      const all = await fetchAllRootComments(pageId, fetchComments);
      if (mySeq !== loadSeq) return;
      comments = all;
      paint();
    } catch (err) {
      console.error("[PdfCommentOverlay] failed to load comments:", err);
    }
  }

  function paint() {
    paintPdfRects({
      pages,
      comments,
      rectsByPage,
      anchorToViewportRects: pdfAnchorToViewportRects,
    });
  }

  function handleCommentsUpdated(event) {
    if (event.detail?.pageId && event.detail.pageId !== pageId) return;
    loadComments();
  }

  onMount(() => {
    const unsubscribe = ctx.pages.subscribe((value) => {
      pages = value || [];
      paint();
      // Kick off comment fetch the first time we see real pages.
      if (pages.length > 0 && comments.length === 0) loadComments();
    });

    window.addEventListener("commentsUpdated", handleCommentsUpdated);
    return () => {
      unsubscribe();
      window.removeEventListener("commentsUpdated", handleCommentsUpdated);
      clearPdfRects(rectsByPage);
    };
  });
</script>
