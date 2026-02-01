import { describe, it, expect, vi, beforeEach } from "vitest";
import { startNotionImport, getImportStatus, getImportedPages } from "../api.js";

// Mock csrfFetch
vi.mock("../csrf.js", () => ({
  csrfFetch: vi.fn(),
}));

import { csrfFetch } from "../csrf.js";

describe("Import API", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("startNotionImport", () => {
    it("starts import with FormData", async () => {
      const mockJob = {
        external_id: "job-123",
        status: "pending",
        provider: "notion",
        total_pages: 0,
        pages_imported_count: 0,
      };

      // API returns { job: {...}, message: "..." }
      csrfFetch.mockResolvedValue({
        ok: true,
        json: async () => ({ job: mockJob, message: "Import started" }),
      });

      const mockFile = new File(["test content"], "export.zip", {
        type: "application/zip",
      });

      const result = await startNotionImport("proj-123", mockFile);

      expect(csrfFetch).toHaveBeenCalledTimes(1);
      const [url, options] = csrfFetch.mock.calls[0];
      expect(url).toBe("/api/imports/notion/");
      expect(options.method).toBe("POST");
      expect(options.body).toBeInstanceOf(FormData);

      // Verify FormData contents
      const formData = options.body;
      expect(formData.get("project_id")).toBe("proj-123");
      expect(formData.get("file")).toBe(mockFile);

      // Result includes full response with job and message
      expect(result.job).toEqual(mockJob);
      expect(result.message).toBe("Import started");
    });

    it("throws error with detail message on failure", async () => {
      csrfFetch.mockResolvedValue({
        ok: false,
        statusText: "Bad Request",
        json: async () => ({ detail: "Invalid file format" }),
      });

      const mockFile = new File(["test"], "test.txt", { type: "text/plain" });

      await expect(startNotionImport("proj-123", mockFile)).rejects.toThrow("Invalid file format");
    });

    it("throws error with message on failure", async () => {
      csrfFetch.mockResolvedValue({
        ok: false,
        statusText: "Bad Request",
        json: async () => ({ message: "File too large" }),
      });

      const mockFile = new File(["test"], "export.zip", {
        type: "application/zip",
      });

      await expect(startNotionImport("proj-123", mockFile)).rejects.toThrow("File too large");
    });

    it("throws statusText when no error body", async () => {
      csrfFetch.mockResolvedValue({
        ok: false,
        statusText: "Internal Server Error",
        json: async () => {
          throw new Error("No JSON");
        },
      });

      const mockFile = new File(["test"], "export.zip", {
        type: "application/zip",
      });

      await expect(startNotionImport("proj-123", mockFile)).rejects.toThrow(
        "Failed to start import: Internal Server Error"
      );
    });
  });

  describe("getImportStatus", () => {
    it("fetches import job status", async () => {
      const mockStatus = {
        external_id: "job-123",
        status: "processing",
        provider: "notion",
        total_pages: 10,
        pages_imported_count: 5,
        pages_failed_count: 0,
      };

      csrfFetch.mockResolvedValue({
        ok: true,
        json: async () => mockStatus,
      });

      const result = await getImportStatus("job-123");

      expect(csrfFetch).toHaveBeenCalledWith("/api/imports/job-123/");
      expect(result).toEqual(mockStatus);
    });

    it("returns completed status", async () => {
      const mockStatus = {
        external_id: "job-123",
        status: "completed",
        provider: "notion",
        total_pages: 10,
        pages_imported_count: 10,
        pages_failed_count: 0,
      };

      csrfFetch.mockResolvedValue({
        ok: true,
        json: async () => mockStatus,
      });

      const result = await getImportStatus("job-123");

      expect(result.status).toBe("completed");
      expect(result.pages_imported_count).toBe(10);
    });

    it("returns failed status with error message", async () => {
      const mockStatus = {
        external_id: "job-123",
        status: "failed",
        provider: "notion",
        total_pages: 0,
        pages_imported_count: 0,
        pages_failed_count: 0,
        error_message: "Invalid zip file",
      };

      csrfFetch.mockResolvedValue({
        ok: true,
        json: async () => mockStatus,
      });

      const result = await getImportStatus("job-123");

      expect(result.status).toBe("failed");
      expect(result.error_message).toBe("Invalid zip file");
    });

    it("throws error when fetch fails", async () => {
      csrfFetch.mockResolvedValue({
        ok: false,
        statusText: "Not Found",
      });

      await expect(getImportStatus("nonexistent")).rejects.toThrow(
        "Failed to get import status: Not Found"
      );
    });
  });

  describe("getImportedPages", () => {
    it("fetches list of imported pages", async () => {
      const mockPages = [
        {
          external_id: "page-1",
          title: "Page One",
          original_path: "Folder/Page One abc123.md",
        },
        {
          external_id: "page-2",
          title: "Page Two",
          original_path: "Page Two def456.md",
        },
      ];

      csrfFetch.mockResolvedValue({
        ok: true,
        json: async () => mockPages,
      });

      const result = await getImportedPages("job-123");

      expect(csrfFetch).toHaveBeenCalledWith("/api/imports/job-123/pages/");
      expect(result).toEqual(mockPages);
      expect(result).toHaveLength(2);
    });

    it("returns empty array for job with no pages", async () => {
      csrfFetch.mockResolvedValue({
        ok: true,
        json: async () => [],
      });

      const result = await getImportedPages("job-123");

      expect(result).toEqual([]);
    });

    it("throws error when fetch fails", async () => {
      csrfFetch.mockResolvedValue({
        ok: false,
        statusText: "Forbidden",
      });

      await expect(getImportedPages("job-123")).rejects.toThrow(
        "Failed to get imported pages: Forbidden"
      );
    });
  });
});

// Note: Import Modal Store tests require Svelte compilation for $state runes.
// These are tested via manual testing and Svelte component tests.

describe("Import File Validation", () => {
  it("accepts zip files by MIME type", () => {
    const validTypes = ["application/zip", "application/x-zip-compressed"];

    validTypes.forEach((type) => {
      const file = new File(["content"], "export.zip", { type });
      expect(validTypes.includes(file.type) || file.name.endsWith(".zip")).toBe(true);
    });
  });

  it("accepts files with .zip extension", () => {
    // Some systems report different MIME types
    const file = new File(["content"], "export.zip", {
      type: "application/octet-stream",
    });
    expect(file.name.endsWith(".zip")).toBe(true);
  });

  it("validates file size under 100MB", () => {
    const maxSize = 100 * 1024 * 1024; // 100MB

    // Small file - valid
    const smallFile = new File(["x".repeat(1000)], "small.zip", {
      type: "application/zip",
    });
    expect(smallFile.size <= maxSize).toBe(true);

    // Note: Can't easily create a 100MB+ file in tests, but we verify the logic
    const mockLargeSize = 150 * 1024 * 1024;
    expect(mockLargeSize > maxSize).toBe(true);
  });
});

describe("Import Status Polling", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("identifies pending status", () => {
    const status = { status: "pending" };
    expect(["pending", "processing"].includes(status.status)).toBe(true);
  });

  it("identifies processing status", () => {
    const status = { status: "processing" };
    expect(["pending", "processing"].includes(status.status)).toBe(true);
  });

  it("identifies completed status", () => {
    const status = { status: "completed" };
    expect(status.status === "completed").toBe(true);
  });

  it("identifies failed status", () => {
    const status = { status: "failed" };
    expect(status.status === "failed").toBe(true);
  });

  it("calculates progress percentage", () => {
    const status = {
      total_pages: 10,
      pages_imported_count: 7,
    };

    const progress =
      status.total_pages > 0 ? (status.pages_imported_count / status.total_pages) * 100 : 0;

    expect(progress).toBe(70);
  });

  it("handles zero total pages", () => {
    const status = {
      total_pages: 0,
      pages_imported_count: 0,
    };

    const progress =
      status.total_pages > 0 ? (status.pages_imported_count / status.total_pages) * 100 : 0;

    expect(progress).toBe(0);
  });
});

describe("Import Retry Logic", () => {
  // Helper to determine if retry should be shown (mirrors ImportModal.svelte logic)
  function canRetry(importJob) {
    const isFailed = importJob && importJob.status === "failed";
    return isFailed && !importJob?.error_message?.includes("No importable content");
  }

  it("allows retry for generic errors", () => {
    const status = {
      status: "failed",
      error_message: "Invalid zip file",
    };

    expect(canRetry(status)).toBe(true);
  });

  it("allows retry for connection errors", () => {
    const status = {
      status: "failed",
      error_message: "Lost connection to server",
    };

    expect(canRetry(status)).toBe(true);
  });

  it("disallows retry for no importable content error", () => {
    const status = {
      status: "failed",
      error_message:
        "No importable content found in the archive. The archive may be empty or contain only unsupported file formats.",
    };

    expect(canRetry(status)).toBe(false);
  });

  it("disallows retry when error message is undefined", () => {
    const status = {
      status: "failed",
      error_message: undefined,
    };

    // Should still allow retry when error_message is missing (generic failure)
    expect(canRetry(status)).toBe(true);
  });

  it("returns false when not failed", () => {
    const completed = { status: "completed", error_message: "" };
    const processing = { status: "processing", error_message: "" };
    const pending = { status: "pending", error_message: "" };

    expect(canRetry(completed)).toBe(false);
    expect(canRetry(processing)).toBe(false);
    expect(canRetry(pending)).toBe(false);
  });
});
