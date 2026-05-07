import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

const { getDocumentMock } = vi.hoisted(() => ({
  getDocumentMock: vi.fn(),
}));

vi.mock("pdfjs-dist", () => ({
  GlobalWorkerOptions: { workerSrc: "" },
  getDocument: getDocumentMock,
  TextLayer: class {},
}));

import { loadPdf, extractTextFromPdf } from "../pdf/pdfLoader.js";

describe("pdfLoader friendlyPdfError translation", () => {
  let consoleErrorSpy;

  beforeEach(() => {
    getDocumentMock.mockReset();
    consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    consoleErrorSpy.mockRestore();
  });

  it("translates 'fake worker' rejection from extractTextFromPdf", async () => {
    const original = new Error("Setting up fake worker failed: TypeError: Failed to fetch");
    getDocumentMock.mockReturnValue({
      promise: Promise.reject(original),
    });

    await expect(extractTextFromPdf(new ArrayBuffer(8))).rejects.toThrow(
      "Couldn't load PDF support. Please refresh the page and try again."
    );
    expect(consoleErrorSpy).toHaveBeenCalledWith("[PDF] Worker load failed:", original);
  });

  it("translates 'dynamically imported module' rejection from loadPdf", async () => {
    const original = new Error(
      "Failed to fetch dynamically imported module: https://example.com/static/core/spa/assets/pdf.worker.min.mjs"
    );
    getDocumentMock.mockReturnValue({
      promise: Promise.reject(original),
    });

    await expect(loadPdf("https://example.com/test.pdf")).rejects.toThrow(
      "Couldn't load PDF support. Please refresh the page and try again."
    );
    expect(consoleErrorSpy).toHaveBeenCalledWith("[PDF] Worker load failed:", original);
  });

  it("passes non-worker errors through unchanged", async () => {
    const original = new Error("Invalid PDF structure");
    getDocumentMock.mockReturnValue({
      promise: Promise.reject(original),
    });

    await expect(loadPdf("https://example.com/bad.pdf")).rejects.toBe(original);
    expect(consoleErrorSpy).not.toHaveBeenCalled();
  });
});
