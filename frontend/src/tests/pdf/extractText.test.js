/**
 * Tests for client-side PDF text extraction via PDF.js.
 *
 * Mocks pdfjs-dist to test the extraction logic (line-break detection,
 * page separators, metadata title) without needing a real PDF binary.
 */

import { describe, test, expect, vi, beforeEach } from "vitest";

// Mock pdfjs-dist before importing the module under test
vi.mock("pdfjs-dist", () => {
  const GlobalWorkerOptions = { workerSrc: "" };

  function mockGetDocument({ data }) {
    // The mock reads _pdfTestPages from the data to build the fake document
    const pages = data?._pdfTestPages || [];
    const metadata = data?._pdfTestMetadata || {};

    const doc = {
      numPages: pages.length,
      getPage: async (num) => ({
        getTextContent: async () => ({
          items: pages[num - 1] || [],
        }),
      }),
      getMetadata: async () => ({ info: metadata }),
      destroy: vi.fn(),
    };

    return { promise: Promise.resolve(doc) };
  }

  return { GlobalWorkerOptions, getDocument: mockGetDocument };
});

import { extractTextFromPdf } from "../../pdf/pdfLoader.js";

/**
 * Build a fake "ArrayBuffer" that carries test page data through to the mock.
 */
function makeFakeData(pages, metadata = {}) {
  return { _pdfTestPages: pages, _pdfTestMetadata: metadata };
}

/** Build a text item at a given Y position. */
function textItem(str, y = 100) {
  return { str, transform: [1, 0, 0, 1, 72, y] };
}

describe("extractTextFromPdf", () => {
  test("extracts text from a single page", async () => {
    const pages = [[textItem("Hello world", 700)]];
    const result = await extractTextFromPdf(makeFakeData(pages));

    expect(result.content).toContain("# Page 1");
    expect(result.content).toContain("Hello world");
  });

  test("extracts text from multiple pages with separators", async () => {
    const pages = [
      [textItem("Page one text", 700)],
      [textItem("Page two text", 700)],
      [textItem("Page three text", 700)],
    ];
    const result = await extractTextFromPdf(makeFakeData(pages));

    expect(result.content).toContain("# Page 1");
    expect(result.content).toContain("Page one text");
    expect(result.content).toContain("# Page 2");
    expect(result.content).toContain("Page two text");
    expect(result.content).toContain("# Page 3");
    expect(result.content).toContain("Page three text");
  });

  test("inserts line breaks when Y position changes", async () => {
    const pages = [
      [
        textItem("First line", 700),
        textItem("Second line", 680), // different Y → line break
      ],
    ];
    const result = await extractTextFromPdf(makeFakeData(pages));

    expect(result.content).toContain("First line\nSecond line");
  });

  test("no line break when Y position is similar", async () => {
    const pages = [
      [
        textItem("Hello ", 700),
        textItem("world", 700), // same Y → no break
      ],
    ];
    const result = await extractTextFromPdf(makeFakeData(pages));

    expect(result.content).toContain("Hello world");
  });

  test("skips empty pages", async () => {
    const pages = [
      [textItem("Page one", 700)],
      [], // empty page
      [textItem("Page three", 700)],
    ];
    const result = await extractTextFromPdf(makeFakeData(pages));

    expect(result.content).toContain("# Page 1");
    expect(result.content).not.toContain("# Page 2");
    expect(result.content).toContain("# Page 3");
  });

  test("skips items with empty str", async () => {
    const pages = [[textItem("", 700), textItem("Real text", 680)]];
    const result = await extractTextFromPdf(makeFakeData(pages));

    expect(result.content).toContain("Real text");
  });

  test("returns metadata title when available", async () => {
    const pages = [[textItem("content", 700)]];
    const metadata = { Title: "My Research Paper" };
    const result = await extractTextFromPdf(makeFakeData(pages, metadata));

    expect(result.title).toBe("My Research Paper");
  });

  test("returns empty title when no metadata", async () => {
    const pages = [[textItem("content", 700)]];
    const result = await extractTextFromPdf(makeFakeData(pages));

    expect(result.title).toBe("");
  });

  test("returns empty content for PDF with no text", async () => {
    const pages = [[]];
    const result = await extractTextFromPdf(makeFakeData(pages));

    expect(result.content).toBe("");
  });

  test("inserts space between split-word items on the same line", async () => {
    const pages = [
      [
        textItem("Machine", 700),
        textItem("learning", 700),
        textItem("is", 700),
        textItem("great", 700),
      ],
    ];
    const result = await extractTextFromPdf(makeFakeData(pages));

    expect(result.content).toContain("Machine learning is great");
  });

  test("does not double-space when item already has trailing space", async () => {
    const pages = [[textItem("Hello ", 700), textItem("world", 700)]];
    const result = await extractTextFromPdf(makeFakeData(pages));

    expect(result.content).toContain("Hello world");
    expect(result.content).not.toContain("Hello  world");
  });

  test("does not double-space when item has leading space", async () => {
    const pages = [[textItem("Hello", 700), textItem(" world", 700)]];
    const result = await extractTextFromPdf(makeFakeData(pages));

    expect(result.content).toContain("Hello world");
    expect(result.content).not.toContain("Hello  world");
  });

  test("respects hasEOL flag for line breaks", async () => {
    const pages = [
      [
        { str: "First line", transform: [1, 0, 0, 1, 72, 700], hasEOL: true },
        { str: "Second line", transform: [1, 0, 0, 1, 72, 700] },
      ],
    ];
    const result = await extractTextFromPdf(makeFakeData(pages));

    expect(result.content).toContain("First line\nSecond line");
  });

  test("trims whitespace from page text", async () => {
    const pages = [[textItem("  ", 720), textItem("Actual content", 700), textItem("  ", 680)]];
    const result = await extractTextFromPdf(makeFakeData(pages));

    expect(result.content).toContain("# Page 1");
    expect(result.content).toContain("Actual content");
  });
});
