/**
 * PdfCommentOverlay component test.
 *
 * Mounts the Svelte component with a fake PDF_PAGE_CONTEXT and a mocked
 * fetchComments API to verify the three behaviors that hold the overlay
 * together:
 *
 *   1. Paints a yellow rect for every root comment that carries a pdf_anchor
 *      after the page list becomes non-empty.
 *   2. Pages through the list-comments endpoint until every root comment has
 *      been collected (delegates to fetchAllRootComments).
 *   3. Clicking a painted rect dispatches the `pdfCommentSelected` window
 *      event with the corresponding `commentId` and `pdf_anchor`.
 */

import { describe, test, expect, vi, beforeEach, afterEach } from "vitest";
import { writable } from "svelte/store";

// Mock the comments API. Each test sets the implementation it needs.
vi.mock("../../api.js", () => ({
  fetchComments: vi.fn(),
}));

import { mount, unmount } from "svelte";
import PdfCommentOverlay from "../../pdf/PdfCommentOverlay.svelte";
import { PDF_PAGE_CONTEXT } from "../../pdf/pdfPageContext.js";
import { fetchComments } from "../../api.js";

function makePageWrapper(pageNumber) {
  const wrapper = document.createElement("div");
  wrapper.dataset.pdfPage = String(pageNumber);
  const overlay = document.createElement("div");
  overlay.className = "pdf-comment-overlay";
  wrapper.appendChild(overlay);
  document.body.appendChild(wrapper);
  return { wrapper, overlay };
}

function makeRootComment(id, pageNumber, rects = [{ x: 10, y: 20, w: 30, h: 12 }]) {
  return {
    external_id: id,
    parent: null,
    pdf_anchor: { page: pageNumber, rects, text: `text ${id}` },
  };
}

// PdfCommentOverlay calls pdfAnchorToViewportRects with the viewport stored
// in ctx.pages. We pass an identity-shaped viewport so the rects round-trip
// without coupling to PDF.js coord math.
const identityViewport = {
  convertToViewportRectangle([x1, y1, x2, y2]) {
    return [x1, y1, x2, y2];
  },
};

async function flush() {
  await new Promise((resolve) => setTimeout(resolve, 0));
  await new Promise((resolve) => setTimeout(resolve, 0));
}

function makeCtx() {
  return { pages: writable([]), selection: writable(null) };
}

describe("PdfCommentOverlay", () => {
  let target;

  beforeEach(() => {
    vi.clearAllMocks();
    document.body.innerHTML = "";
    target = document.createElement("div");
    document.body.appendChild(target);
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  test("paints a rect per anchored root comment once pages are published", async () => {
    const { overlay } = makePageWrapper(1);
    const ctx = makeCtx();

    fetchComments.mockResolvedValue({
      items: [makeRootComment("c1", 1), makeRootComment("c2", 1)],
      count: 2,
    });

    const component = mount(PdfCommentOverlay, {
      target,
      props: { pageId: "page-1" },
      context: new Map([[PDF_PAGE_CONTEXT, ctx]]),
    });

    // Publish the page metadata — this triggers loadComments() inside the
    // overlay's pages.subscribe callback.
    ctx.pages.set([{ pageNumber: 1, viewport: identityViewport }]);
    await flush();

    const rects = overlay.querySelectorAll(".pdf-comment-rect");
    expect(rects).toHaveLength(2);
    expect(rects[0].dataset.commentId).toBe("c1");
    expect(rects[1].dataset.commentId).toBe("c2");

    unmount(component);
  });

  test("pages through fetchComments until every root comment is collected", async () => {
    const { overlay } = makePageWrapper(1);
    const ctx = makeCtx();

    // 150 root comments split into two batches of 100, then a short final
    // batch of 50 — enough to verify multiple paginated calls happen.
    const all = Array.from({ length: 150 }, (_, i) => makeRootComment(`c${i}`, 1));
    fetchComments.mockImplementation(async (_pageId, limit, offset) => {
      const items = all.slice(offset, offset + limit);
      return { items, count: all.length };
    });

    const component = mount(PdfCommentOverlay, {
      target,
      props: { pageId: "page-1" },
      context: new Map([[PDF_PAGE_CONTEXT, ctx]]),
    });

    ctx.pages.set([{ pageNumber: 1, viewport: identityViewport }]);
    await flush();
    // Two ticks aren't always enough for 2 sequential awaits — give it a few
    // more turns to settle the pagination chain.
    await new Promise((resolve) => setTimeout(resolve, 20));

    expect(fetchComments).toHaveBeenCalledTimes(2);
    expect(fetchComments).toHaveBeenNthCalledWith(1, "page-1", 100, 0);
    expect(fetchComments).toHaveBeenNthCalledWith(2, "page-1", 100, 100);

    const rects = overlay.querySelectorAll(".pdf-comment-rect");
    expect(rects).toHaveLength(150);

    unmount(component);
  });

  test("clicking a painted rect dispatches pdfCommentSelected with the comment payload", async () => {
    const { overlay } = makePageWrapper(1);
    const ctx = makeCtx();

    const c1 = makeRootComment("c1", 1, [{ x: 5, y: 6, w: 7, h: 8 }]);
    fetchComments.mockResolvedValue({ items: [c1], count: 1 });

    const component = mount(PdfCommentOverlay, {
      target,
      props: { pageId: "page-1" },
      context: new Map([[PDF_PAGE_CONTEXT, ctx]]),
    });

    ctx.pages.set([{ pageNumber: 1, viewport: identityViewport }]);
    await flush();

    const rect = overlay.querySelector(".pdf-comment-rect");
    expect(rect).not.toBeNull();

    const detailEvents = [];
    const handler = (e) => detailEvents.push(e.detail);
    window.addEventListener("pdfCommentSelected", handler);
    rect.click();
    window.removeEventListener("pdfCommentSelected", handler);

    expect(detailEvents).toHaveLength(1);
    expect(detailEvents[0].commentId).toBe("c1");
    expect(detailEvents[0].pdf_anchor.page).toBe(1);
    expect(detailEvents[0].pdf_anchor.rects).toEqual([{ x: 5, y: 6, w: 7, h: 8 }]);

    unmount(component);
  });

  test("refetches comments when a commentsUpdated window event fires", async () => {
    makePageWrapper(1);
    const ctx = makeCtx();

    fetchComments.mockResolvedValue({ items: [], count: 0 });

    const component = mount(PdfCommentOverlay, {
      target,
      props: { pageId: "page-1" },
      context: new Map([[PDF_PAGE_CONTEXT, ctx]]),
    });

    ctx.pages.set([{ pageNumber: 1, viewport: identityViewport }]);
    await flush();
    expect(fetchComments).toHaveBeenCalledTimes(1);

    window.dispatchEvent(new CustomEvent("commentsUpdated", { detail: { pageId: "page-1" } }));
    await flush();
    expect(fetchComments).toHaveBeenCalledTimes(2);

    // Events targeted at a different page must be ignored.
    window.dispatchEvent(new CustomEvent("commentsUpdated", { detail: { pageId: "other-page" } }));
    await flush();
    expect(fetchComments).toHaveBeenCalledTimes(2);

    unmount(component);
  });
});
