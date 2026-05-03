/**
 * PdfPageView component test.
 *
 * Mounts the Svelte component with PDF.js mocked out and asserts that the
 * `pdfFirstPageRendered` window event fires once the first page has been
 * rendered (the pages-ready signal that loadPdfPage relies on to settle the
 * page-load telemetry span). Also covers the missing-file error path.
 *
 * IntersectionObserver/ResizeObserver are not provided by happy-dom; the
 * component already has a "no observer → render eagerly" fallback, which is
 * what these tests exercise.
 */

import { describe, test, expect, vi, beforeEach, afterEach } from "vitest";

// Mock pdfLoader.js so we don't need a real PDF.js worker. Hoisted by Vitest.
vi.mock("../../pdf/pdfLoader.js", () => ({
  loadPdf: vi.fn(),
  renderPage: vi.fn().mockResolvedValue(undefined),
  getTextContent: vi.fn().mockResolvedValue({ items: [] }),
  renderTextLayer: vi.fn().mockResolvedValue(undefined),
}));

// Mock the comments API in case PdfCommentOverlay child mounts (it doesn't
// when pageId is omitted, but the safety belt keeps the test stable if the
// component template ever changes).
vi.mock("../../api.js", () => ({
  fetchComments: vi.fn().mockResolvedValue({ items: [], count: 0 }),
}));

import { mount, unmount } from "svelte";
import PdfPageView from "../../pdf/PdfPageView.svelte";
import { loadPdf } from "../../pdf/pdfLoader.js";

function makeViewport(scale = 1) {
  return { width: 100 * scale, height: 200 * scale, scale };
}

function makePdfDoc(numPages = 2) {
  const pages = [];
  for (let i = 1; i <= numPages; i++) {
    pages.push({
      getViewport: ({ scale }) => makeViewport(scale),
    });
  }
  return {
    numPages,
    getPage: vi.fn(async (n) => pages[n - 1]),
    destroy: vi.fn(),
  };
}

async function flushAsync(ms = 30) {
  // Let the load() chain (loadPdf → buildLayout → ensurePageRendered →
  // renderPage → getTextContent → renderTextLayer) run to completion.
  await new Promise((resolve) => setTimeout(resolve, ms));
}

describe("PdfPageView", () => {
  let target;
  let events;
  let handler;

  beforeEach(() => {
    vi.clearAllMocks();
    target = document.createElement("div");
    document.body.appendChild(target);
    events = [];
    handler = (e) => events.push(e.detail);
    window.addEventListener("pdfFirstPageRendered", handler);
  });

  afterEach(() => {
    window.removeEventListener("pdfFirstPageRendered", handler);
    target.remove();
  });

  test("dispatches pdfFirstPageRendered with status:success once the first page paints", async () => {
    loadPdf.mockResolvedValue(makePdfDoc(2));

    const component = mount(PdfPageView, {
      target,
      props: { fileDownloadUrl: "https://example.com/file.pdf", pageId: undefined },
    });

    await flushAsync();

    const successes = events.filter((d) => d.status === "success");
    expect(successes).toHaveLength(1);
    expect(successes[0].pageId).toBeUndefined();

    unmount(component);
  });

  test("includes the pageId on the dispatched event detail", async () => {
    loadPdf.mockResolvedValue(makePdfDoc(1));

    const component = mount(PdfPageView, {
      target,
      props: { fileDownloadUrl: "https://example.com/x.pdf", pageId: "page-abc" },
    });

    await flushAsync();

    const successes = events.filter((d) => d.status === "success");
    expect(successes).toHaveLength(1);
    expect(successes[0].pageId).toBe("page-abc");

    unmount(component);
  });

  test("dispatches only one pdfFirstPageRendered even with multiple pages", async () => {
    loadPdf.mockResolvedValue(makePdfDoc(3));

    const component = mount(PdfPageView, {
      target,
      props: { fileDownloadUrl: "https://example.com/file.pdf", pageId: undefined },
    });

    await flushAsync();

    expect(events).toHaveLength(1);

    unmount(component);
  });

  test("dispatches missing_file error when fileDownloadUrl is empty", async () => {
    const component = mount(PdfPageView, {
      target,
      props: { fileDownloadUrl: "", pageId: "page-1" },
    });

    await flushAsync(10);

    expect(events).toHaveLength(1);
    expect(events[0].status).toBe("error");
    expect(events[0].reason).toBe("missing_file");
    expect(events[0].pageId).toBe("page-1");
    // loadPdf must not be invoked when there's no URL.
    expect(loadPdf).not.toHaveBeenCalled();

    unmount(component);
  });

  test("dispatches an error event when loadPdf rejects", async () => {
    // Suppress the expected console.error from the catch branch so the test
    // output stays clean.
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    loadPdf.mockRejectedValue(new Error("network down"));

    const component = mount(PdfPageView, {
      target,
      props: { fileDownloadUrl: "https://example.com/missing.pdf", pageId: "page-2" },
    });

    await flushAsync();

    expect(events).toHaveLength(1);
    expect(events[0].status).toBe("error");
    expect(events[0].pageId).toBe("page-2");
    expect(events[0].reason).toContain("network down");

    errSpy.mockRestore();
    unmount(component);
  });
});
