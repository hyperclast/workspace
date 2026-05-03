import { describe, test, expect, beforeEach, vi } from "vitest";
import { paintPdfRects, clearPdfRects } from "../../pdf/paintPdfRects.js";

// Identity-style anchor → viewport rect converter so the math is irrelevant
// to these tests; we're verifying the upsert/diff behavior, not coordinate
// conversion.
function identityRects(anchor, _viewport) {
  return (anchor.rects || []).map((r) => ({
    left: r.x,
    top: r.y,
    width: r.w,
    height: r.h,
  }));
}

function makeWrapper(pageNumber) {
  const wrapper = document.createElement("div");
  wrapper.dataset.pdfPage = String(pageNumber);
  const overlay = document.createElement("div");
  overlay.className = "pdf-comment-overlay";
  wrapper.appendChild(overlay);
  document.body.appendChild(wrapper);
  return { wrapper, overlay };
}

function makeComment(id, page, rects = [{ x: 10, y: 20, w: 100, h: 12 }], extras = {}) {
  return {
    external_id: id,
    parent: null,
    pdf_anchor: { page, rects, text: `text-${id}` },
    ...extras,
  };
}

const fakeViewport = { name: "vp1" };

describe("paintPdfRects", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
  });

  test("paints rects for comments anchored to the page", () => {
    const { overlay } = makeWrapper(1);
    const rectsByPage = new Map();
    const comments = [
      makeComment("c1", 1, [{ x: 5, y: 6, w: 50, h: 10 }]),
      makeComment("c2", 1, [{ x: 80, y: 90, w: 30, h: 10 }]),
    ];

    paintPdfRects({
      pages: [{ pageNumber: 1, viewport: fakeViewport }],
      comments,
      rectsByPage,
      anchorToViewportRects: identityRects,
    });

    const els = overlay.querySelectorAll(".pdf-comment-rect");
    expect(els).toHaveLength(2);
    expect(els[0].dataset.commentId).toBe("c1");
    expect(els[0].style.left).toBe("5px");
    expect(els[0].style.top).toBe("6px");
    expect(els[0].style.width).toBe("50px");
    expect(els[1].dataset.commentId).toBe("c2");
  });

  test("skips replies and comments anchored to other pages", () => {
    const { overlay } = makeWrapper(1);
    const rectsByPage = new Map();
    const comments = [
      makeComment("c1", 1),
      makeComment("c2", 2), // wrong page
      { ...makeComment("c3", 1), parent: "c1" }, // reply
    ];

    paintPdfRects({
      pages: [{ pageNumber: 1, viewport: fakeViewport }],
      comments,
      rectsByPage,
      anchorToViewportRects: identityRects,
    });

    const els = overlay.querySelectorAll(".pdf-comment-rect");
    expect(els).toHaveLength(1);
    expect(els[0].dataset.commentId).toBe("c1");
  });

  test("re-uses existing DOM nodes when the same comment is painted again", () => {
    const { overlay } = makeWrapper(1);
    const rectsByPage = new Map();
    const c1 = makeComment("c1", 1);

    paintPdfRects({
      pages: [{ pageNumber: 1, viewport: fakeViewport }],
      comments: [c1],
      rectsByPage,
      anchorToViewportRects: identityRects,
    });

    const firstEl = overlay.querySelector(".pdf-comment-rect");
    expect(firstEl).not.toBeNull();

    paintPdfRects({
      pages: [{ pageNumber: 1, viewport: fakeViewport }],
      comments: [c1],
      rectsByPage,
      anchorToViewportRects: identityRects,
    });

    const els = overlay.querySelectorAll(".pdf-comment-rect");
    expect(els).toHaveLength(1);
    expect(els[0]).toBe(firstEl); // same node, not a re-created one
  });

  test("removes rects for comments that disappear", () => {
    const { overlay } = makeWrapper(1);
    const rectsByPage = new Map();
    const c1 = makeComment("c1", 1);
    const c2 = makeComment("c2", 1);

    paintPdfRects({
      pages: [{ pageNumber: 1, viewport: fakeViewport }],
      comments: [c1, c2],
      rectsByPage,
      anchorToViewportRects: identityRects,
    });
    expect(overlay.querySelectorAll(".pdf-comment-rect")).toHaveLength(2);

    paintPdfRects({
      pages: [{ pageNumber: 1, viewport: fakeViewport }],
      comments: [c1], // c2 deleted
      rectsByPage,
      anchorToViewportRects: identityRects,
    });

    const els = overlay.querySelectorAll(".pdf-comment-rect");
    expect(els).toHaveLength(1);
    expect(els[0].dataset.commentId).toBe("c1");
  });

  test("adds a new rect when a comment appears without rebuilding existing ones", () => {
    const { overlay } = makeWrapper(1);
    const rectsByPage = new Map();
    const c1 = makeComment("c1", 1);

    paintPdfRects({
      pages: [{ pageNumber: 1, viewport: fakeViewport }],
      comments: [c1],
      rectsByPage,
      anchorToViewportRects: identityRects,
    });
    const c1El = overlay.querySelector(`[data-comment-id="c1"]`);

    paintPdfRects({
      pages: [{ pageNumber: 1, viewport: fakeViewport }],
      comments: [c1, makeComment("c2", 1)],
      rectsByPage,
      anchorToViewportRects: identityRects,
    });

    expect(overlay.querySelector(`[data-comment-id="c1"]`)).toBe(c1El);
    expect(overlay.querySelector(`[data-comment-id="c2"]`)).not.toBeNull();
  });

  test("updates positions in place when the viewport changes", () => {
    const { overlay } = makeWrapper(1);
    const rectsByPage = new Map();
    const c1 = makeComment("c1", 1, [{ x: 10, y: 20, w: 30, h: 40 }]);

    paintPdfRects({
      pages: [{ pageNumber: 1, viewport: fakeViewport }],
      comments: [c1],
      rectsByPage,
      anchorToViewportRects: identityRects,
    });
    const el = overlay.querySelector(".pdf-comment-rect");
    expect(el.style.left).toBe("10px");

    // Different "viewport" — return scaled rects.
    paintPdfRects({
      pages: [{ pageNumber: 1, viewport: { name: "vp2" } }],
      comments: [c1],
      rectsByPage,
      anchorToViewportRects: (anchor) =>
        anchor.rects.map((r) => ({
          left: r.x * 2,
          top: r.y * 2,
          width: r.w * 2,
          height: r.h * 2,
        })),
    });

    expect(overlay.querySelectorAll(".pdf-comment-rect")).toHaveLength(1);
    expect(el.style.left).toBe("20px");
    expect(el.style.width).toBe("60px");
  });

  test("click on a rect dispatches pdfCommentSelected with the latest pdf_anchor", () => {
    const { overlay } = makeWrapper(1);
    const rectsByPage = new Map();
    const c1 = makeComment("c1", 1, [{ x: 1, y: 1, w: 1, h: 1 }]);

    paintPdfRects({
      pages: [{ pageNumber: 1, viewport: fakeViewport }],
      comments: [c1],
      rectsByPage,
      anchorToViewportRects: identityRects,
    });

    // Re-paint with an updated anchor on the same comment id (e.g. user
    // edited the anchor server-side and the websocket re-pushed comments).
    const c1Updated = makeComment("c1", 1, [{ x: 1, y: 1, w: 1, h: 1 }]);
    c1Updated.pdf_anchor.text = "edited";
    paintPdfRects({
      pages: [{ pageNumber: 1, viewport: fakeViewport }],
      comments: [c1Updated],
      rectsByPage,
      anchorToViewportRects: identityRects,
    });

    const handler = vi.fn();
    window.addEventListener("pdfCommentSelected", handler);
    overlay.querySelector(".pdf-comment-rect").click();
    window.removeEventListener("pdfCommentSelected", handler);

    expect(handler).toHaveBeenCalledTimes(1);
    const detail = handler.mock.calls[0][0].detail;
    expect(detail.commentId).toBe("c1");
    expect(detail.pdf_anchor.text).toBe("edited");
  });

  test("multi-rect comments fan out and shrink in place", () => {
    const { overlay } = makeWrapper(1);
    const rectsByPage = new Map();
    const c1 = makeComment("c1", 1, [
      { x: 0, y: 0, w: 10, h: 10 },
      { x: 0, y: 20, w: 10, h: 10 },
    ]);

    paintPdfRects({
      pages: [{ pageNumber: 1, viewport: fakeViewport }],
      comments: [c1],
      rectsByPage,
      anchorToViewportRects: identityRects,
    });
    expect(overlay.querySelectorAll(`[data-comment-id="c1"]`)).toHaveLength(2);

    // Now the same comment has only 1 rect — surplus elements must go away.
    const c1Smaller = makeComment("c1", 1, [{ x: 0, y: 0, w: 10, h: 10 }]);
    paintPdfRects({
      pages: [{ pageNumber: 1, viewport: fakeViewport }],
      comments: [c1Smaller],
      rectsByPage,
      anchorToViewportRects: identityRects,
    });
    expect(overlay.querySelectorAll(`[data-comment-id="c1"]`)).toHaveLength(1);
  });

  test("does nothing when the page wrapper isn't mounted yet", () => {
    const rectsByPage = new Map();
    expect(() =>
      paintPdfRects({
        pages: [{ pageNumber: 7, viewport: fakeViewport }],
        comments: [makeComment("c1", 7)],
        rectsByPage,
        anchorToViewportRects: identityRects,
      })
    ).not.toThrow();
    expect(rectsByPage.size).toBe(0);
  });

  test("clearPdfRects removes all elements and empties the cache", () => {
    const { overlay } = makeWrapper(1);
    const rectsByPage = new Map();
    paintPdfRects({
      pages: [{ pageNumber: 1, viewport: fakeViewport }],
      comments: [makeComment("c1", 1), makeComment("c2", 1)],
      rectsByPage,
      anchorToViewportRects: identityRects,
    });

    expect(overlay.querySelectorAll(".pdf-comment-rect")).toHaveLength(2);

    clearPdfRects(rectsByPage);

    expect(overlay.querySelectorAll(".pdf-comment-rect")).toHaveLength(0);
    expect(rectsByPage.size).toBe(0);
  });
});
