import { describe, test, expect, beforeEach } from "vitest";
import {
  rangeToPdfAnchor,
  rangeSpansMultiplePages,
  pdfAnchorToViewportRects,
  PDF_ANCHOR_MAX_RECTS,
  PDF_ANCHOR_TEXT_MAX_LENGTH,
} from "../../pdf/pdfAnchor.js";

// Identity viewport: convertToPdfPoint is the identity, convertToViewportRectangle
// is the identity. This isolates the test from the real PDF.js coord math
// (y-flip, scale) so we exercise the plumbing in pdfAnchor.js directly.
function makeIdentityViewport() {
  return {
    convertToPdfPoint(x, y) {
      return [x, y];
    },
    convertToViewportRectangle([x1, y1, x2, y2]) {
      return [x1, y1, x2, y2];
    },
  };
}

function makeContainer(pageNumber, originLeft = 0, originTop = 0) {
  const wrapper = document.createElement("div");
  wrapper.dataset.pdfPage = String(pageNumber);
  document.body.appendChild(wrapper);
  // happy-dom returns zeros from getBoundingClientRect by default; stub it.
  wrapper.getBoundingClientRect = () => ({
    left: originLeft,
    top: originTop,
    right: originLeft + 600,
    bottom: originTop + 800,
    width: 600,
    height: 800,
    x: originLeft,
    y: originTop,
  });
  return wrapper;
}

function makeRange({ text = "selected", clientRects = [], collapsed = false } = {}) {
  return {
    collapsed,
    toString() {
      return text;
    },
    getClientRects() {
      return clientRects;
    },
    getBoundingClientRect() {
      // Not exercised by rangeToPdfAnchor directly, but kept for completeness.
      return clientRects[0] || { left: 0, top: 0, right: 0, bottom: 0 };
    },
    startContainer: null,
    endContainer: null,
  };
}

function rect(left, top, width, height) {
  return {
    left,
    top,
    width,
    height,
    right: left + width,
    bottom: top + height,
    x: left,
    y: top,
  };
}

describe("rangeToPdfAnchor", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
  });

  test("returns null for a collapsed range", () => {
    const wrapper = makeContainer(1);
    const range = makeRange({ collapsed: true, clientRects: [rect(0, 0, 10, 10)] });
    expect(rangeToPdfAnchor(range, 1, wrapper, makeIdentityViewport())).toBeNull();
  });

  test("returns null when the range has no visible text", () => {
    const wrapper = makeContainer(1);
    const range = makeRange({ text: "   ", clientRects: [rect(0, 0, 10, 10)] });
    expect(rangeToPdfAnchor(range, 1, wrapper, makeIdentityViewport())).toBeNull();
  });

  test("returns null when there are no client rects", () => {
    const wrapper = makeContainer(1);
    const range = makeRange({ text: "hi", clientRects: [] });
    expect(rangeToPdfAnchor(range, 1, wrapper, makeIdentityViewport())).toBeNull();
  });

  test("returns null when missing pageContainer or viewport", () => {
    const range = makeRange({ clientRects: [rect(0, 0, 10, 10)] });
    expect(rangeToPdfAnchor(range, 1, null, makeIdentityViewport())).toBeNull();
    expect(rangeToPdfAnchor(range, 1, makeContainer(1), null)).toBeNull();
  });

  test("builds a single-rect anchor with container-relative coords", () => {
    const wrapper = makeContainer(2, 50, 100); // origin at (50, 100)
    const range = makeRange({
      text: "hello",
      clientRects: [rect(60, 110, 30, 12)], // 10px right and 10px down inside container
    });

    const anchor = rangeToPdfAnchor(range, 2, wrapper, makeIdentityViewport());

    expect(anchor).toEqual({
      page: 2,
      rects: [{ x: 10, y: 10, w: 30, h: 12 }],
      text: "hello",
    });
  });

  test("filters out zero-width / zero-height client rects before conversion", () => {
    const wrapper = makeContainer(1);
    const range = makeRange({
      text: "ok",
      clientRects: [
        rect(0, 0, 0, 10), // zero width
        rect(0, 20, 10, 0), // zero height
        rect(0, 40, 10, 10), // valid
      ],
    });
    const anchor = rangeToPdfAnchor(range, 1, wrapper, makeIdentityViewport());
    expect(anchor.rects).toHaveLength(1);
    expect(anchor.rects[0]).toEqual({ x: 0, y: 40, w: 10, h: 10 });
  });

  test("collapses to a union rect when client rects exceed PDF_ANCHOR_MAX_RECTS", () => {
    const wrapper = makeContainer(1);
    // PDF_ANCHOR_MAX_RECTS + 1 rects; bounding box should span (0,0) → (max, 12).
    const overflow = PDF_ANCHOR_MAX_RECTS + 1;
    const clientRects = Array.from({ length: overflow }, (_, i) => rect(i * 10, 0, 10, 12));
    const range = makeRange({ text: "long line", clientRects });

    const anchor = rangeToPdfAnchor(range, 1, wrapper, makeIdentityViewport());

    expect(anchor.rects).toHaveLength(1);
    expect(anchor.rects[0].x).toBe(0);
    expect(anchor.rects[0].y).toBe(0);
    expect(anchor.rects[0].w).toBe(overflow * 10);
    expect(anchor.rects[0].h).toBe(12);
  });

  test("truncates anchor text at PDF_ANCHOR_TEXT_MAX_LENGTH", () => {
    const wrapper = makeContainer(1);
    const longText = "a".repeat(PDF_ANCHOR_TEXT_MAX_LENGTH + 100);
    const range = makeRange({ text: longText, clientRects: [rect(0, 0, 10, 10)] });

    const anchor = rangeToPdfAnchor(range, 1, wrapper, makeIdentityViewport());

    expect(anchor.text.length).toBe(PDF_ANCHOR_TEXT_MAX_LENGTH);
  });
});

describe("rangeSpansMultiplePages", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
  });

  test("returns false when start and end are inside the same page", () => {
    const wrapper = makeContainer(1);
    const span = document.createElement("span");
    wrapper.appendChild(span);

    const range = { startContainer: span, endContainer: span };
    expect(rangeSpansMultiplePages(range)).toBe(false);
  });

  test("returns true when start and end live on different pages", () => {
    const p1 = makeContainer(1);
    const p2 = makeContainer(2);
    const a = document.createElement("span");
    const b = document.createElement("span");
    p1.appendChild(a);
    p2.appendChild(b);

    const range = { startContainer: a, endContainer: b };
    expect(rangeSpansMultiplePages(range)).toBe(true);
  });

  test("returns false when neither end is inside a PDF page wrapper", () => {
    const a = document.createElement("span");
    const b = document.createElement("span");
    document.body.appendChild(a);
    document.body.appendChild(b);

    const range = { startContainer: a, endContainer: b };
    expect(rangeSpansMultiplePages(range)).toBe(false);
  });

  test("returns false for a null/undefined range", () => {
    expect(rangeSpansMultiplePages(null)).toBe(false);
    expect(rangeSpansMultiplePages(undefined)).toBe(false);
  });

  test("walks up the parent chain to find the page wrapper", () => {
    const wrapper = makeContainer(3);
    const inner = document.createElement("span");
    const leaf = document.createTextNode("hi");
    inner.appendChild(leaf);
    wrapper.appendChild(inner);

    const range = { startContainer: leaf, endContainer: leaf };
    expect(rangeSpansMultiplePages(range)).toBe(false);
  });
});

describe("pdfAnchorToViewportRects", () => {
  test("converts each stored rect via convertToViewportRectangle", () => {
    const anchor = {
      page: 1,
      rects: [
        { x: 10, y: 20, w: 30, h: 40 },
        { x: 100, y: 200, w: 5, h: 6 },
      ],
      text: "irrelevant",
    };
    const result = pdfAnchorToViewportRects(anchor, makeIdentityViewport());

    expect(result).toEqual([
      { left: 10, top: 20, width: 30, height: 40 },
      { left: 100, top: 200, width: 5, height: 6 },
    ]);
  });

  test("normalizes flipped coordinates from the viewport conversion", () => {
    // Simulate a viewport that flips y (which real PDF.js does for PDF user-space).
    const flippingViewport = {
      convertToViewportRectangle([x1, y1, x2, y2]) {
        return [x1, -y2, x2, -y1];
      },
    };
    const anchor = {
      page: 1,
      rects: [{ x: 0, y: 10, w: 20, h: 30 }],
      text: "x",
    };
    const [r] = pdfAnchorToViewportRects(anchor, flippingViewport);
    expect(r.left).toBe(0);
    expect(r.width).toBe(20);
    expect(r.height).toBe(30);
  });

  test("returns [] when anchor is missing or malformed", () => {
    expect(pdfAnchorToViewportRects(null, makeIdentityViewport())).toEqual([]);
    expect(pdfAnchorToViewportRects({}, makeIdentityViewport())).toEqual([]);
    expect(pdfAnchorToViewportRects({ rects: "nope" }, makeIdentityViewport())).toEqual([]);
  });

  test("returns [] when viewport is missing", () => {
    const anchor = { page: 1, rects: [{ x: 0, y: 0, w: 1, h: 1 }], text: "" };
    expect(pdfAnchorToViewportRects(anchor, null)).toEqual([]);
  });
});
