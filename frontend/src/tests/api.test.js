import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  fetchProjectsWithPages,
  createProject,
  createPage,
  fetchOrgs,
  fetchPage,
  resolveComment,
  unresolveComment,
  importPdf,
} from "../api.js";

// Mock csrfFetch
vi.mock("../csrf.js", () => ({
  csrfFetch: vi.fn(),
}));

import { csrfFetch } from "../csrf.js";

describe("API Service", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("fetchProjectsWithPages", () => {
    it("fetches projects with full details", async () => {
      const mockProjects = [
        {
          external_id: "proj1",
          name: "Project 1",
          org: { external_id: "org1", name: "Org 1" },
          pages: [{ external_id: "page1", title: "Page 1" }],
        },
      ];

      csrfFetch.mockResolvedValue({
        ok: true,
        json: async () => mockProjects,
      });

      const result = await fetchProjectsWithPages();

      expect(csrfFetch).toHaveBeenCalledWith("/api/v1/projects/?details=full");
      expect(result).toEqual(mockProjects);
    });

    it("throws error when response is not ok", async () => {
      csrfFetch.mockResolvedValue({
        ok: false,
        statusText: "Not Found",
      });

      await expect(fetchProjectsWithPages()).rejects.toThrow("Failed to fetch projects: Not Found");
    });
  });

  describe("createProject", () => {
    it("creates a project successfully", async () => {
      const mockProject = {
        external_id: "proj1",
        name: "New Project",
        creator: { external_id: "user1", email: "user@example.com" },
        org: { external_id: "org1", name: "Org 1" },
      };

      csrfFetch.mockResolvedValue({
        ok: true,
        json: async () => mockProject,
      });

      const result = await createProject("org1", "New Project", "Description");

      expect(csrfFetch).toHaveBeenCalledWith("/api/v1/projects/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          org_id: "org1",
          name: "New Project",
          description: "Description",
          org_members_can_access: true,
        }),
      });
      expect(result).toEqual(mockProject);
    });

    it("throws error when project creation fails", async () => {
      csrfFetch.mockResolvedValue({
        ok: false,
        statusText: "Bad Request",
      });

      await expect(createProject("org1", "New Project")).rejects.toThrow(
        "Failed to create project"
      );
    });
  });

  describe("createPage", () => {
    it("creates a page successfully", async () => {
      const mockPage = {
        external_id: "page1",
        title: "New Page",
        project_id: "proj1",
      };

      csrfFetch.mockResolvedValue({
        ok: true,
        json: async () => mockPage,
      });

      const result = await createPage("proj1", "New Page");

      expect(csrfFetch).toHaveBeenCalledWith("/api/v1/pages/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          project_id: "proj1",
          title: "New Page",
        }),
      });
      expect(result).toEqual(mockPage);
    });

    it("throws error when page creation fails", async () => {
      csrfFetch.mockResolvedValue({
        ok: false,
        statusText: "Forbidden",
      });

      await expect(createPage("proj1", "New Page")).rejects.toThrow("Failed to create page");
    });
  });

  describe("fetchPage", () => {
    it("fetches a page successfully", async () => {
      const mockPage = {
        external_id: "page1",
        title: "Test Page",
        details: { content: "Hello world" },
      };

      csrfFetch.mockResolvedValue({
        ok: true,
        json: async () => mockPage,
      });

      const result = await fetchPage("page1");

      expect(csrfFetch).toHaveBeenCalledWith("/api/v1/pages/page1/", {});
      expect(result).toEqual(mockPage);
    });

    it("passes options through to csrfFetch", async () => {
      const controller = new AbortController();
      csrfFetch.mockResolvedValue({
        ok: true,
        json: async () => ({ external_id: "page1" }),
      });

      await fetchPage("page1", { signal: controller.signal });

      expect(csrfFetch).toHaveBeenCalledWith("/api/v1/pages/page1/", {
        signal: controller.signal,
      });
    });

    it("throws AbortError when signal is aborted", async () => {
      const controller = new AbortController();
      csrfFetch.mockImplementation(() => {
        throw new DOMException("The operation was aborted.", "AbortError");
      });

      await expect(fetchPage("page1", { signal: controller.signal })).rejects.toThrow(
        "The operation was aborted."
      );
    });

    it("throws error when page not found (404)", async () => {
      csrfFetch.mockResolvedValue({
        ok: false,
        statusText: "Not Found",
      });

      await expect(fetchPage("nonexistent")).rejects.toThrow("Failed to fetch page: Not Found");
    });

    it("throws error when access forbidden (403)", async () => {
      csrfFetch.mockResolvedValue({
        ok: false,
        statusText: "Forbidden",
      });

      await expect(fetchPage("restricted")).rejects.toThrow("Failed to fetch page: Forbidden");
    });

    it("throws error on server error (500)", async () => {
      csrfFetch.mockResolvedValue({
        ok: false,
        statusText: "Internal Server Error",
      });

      await expect(fetchPage("page1")).rejects.toThrow(
        "Failed to fetch page: Internal Server Error"
      );
    });
  });

  describe("fetchOrgs", () => {
    it("fetches organizations successfully", async () => {
      const mockOrgs = [
        { external_id: "org1", name: "Org 1" },
        { external_id: "org2", name: "Org 2" },
      ];

      csrfFetch.mockResolvedValue({
        ok: true,
        json: async () => mockOrgs,
      });

      const result = await fetchOrgs();

      expect(csrfFetch).toHaveBeenCalledWith("/api/v1/orgs/");
      expect(result).toEqual(mockOrgs);
    });

    it("throws error when fetch fails", async () => {
      csrfFetch.mockResolvedValue({
        ok: false,
        statusText: "Unauthorized",
      });

      await expect(fetchOrgs()).rejects.toThrow("Failed to fetch organizations");
    });
  });

  describe("resolveComment", () => {
    it("resolves a comment successfully", async () => {
      const mockComment = { external_id: "c1", is_resolved: true };

      csrfFetch.mockResolvedValue({
        ok: true,
        json: async () => mockComment,
      });

      const result = await resolveComment("page1", "c1");

      expect(csrfFetch).toHaveBeenCalledWith("/api/v1/pages/page1/comments/c1/resolve/", {
        method: "POST",
      });
      expect(result).toEqual(mockComment);
    });

    it("throws error with status on 403", async () => {
      csrfFetch.mockResolvedValue({
        ok: false,
        status: 403,
        statusText: "Forbidden",
      });

      try {
        await resolveComment("page1", "c1");
        expect.fail("Should have thrown");
      } catch (e) {
        expect(e.message).toContain("Failed to resolve comment");
        expect(e.status).toBe(403);
      }
    });

    it("throws error with status on other failures", async () => {
      csrfFetch.mockResolvedValue({
        ok: false,
        status: 500,
        statusText: "Internal Server Error",
      });

      try {
        await unresolveComment("page1", "c1");
        expect.fail("Should have thrown");
      } catch (e) {
        expect(e.status).toBe(500);
      }
    });
  });

  describe("unresolveComment", () => {
    it("unresolves a comment successfully", async () => {
      const mockComment = { external_id: "c1", is_resolved: false };

      csrfFetch.mockResolvedValue({
        ok: true,
        json: async () => mockComment,
      });

      const result = await unresolveComment("page1", "c1");

      expect(csrfFetch).toHaveBeenCalledWith("/api/v1/pages/page1/comments/c1/unresolve/", {
        method: "POST",
      });
      expect(result).toEqual(mockComment);
    });

    it("throws error with status on 403", async () => {
      csrfFetch.mockResolvedValue({
        ok: false,
        status: 403,
        statusText: "Forbidden",
      });

      try {
        await unresolveComment("page1", "c1");
        expect.fail("Should have thrown");
      } catch (e) {
        expect(e.message).toContain("Failed to unresolve comment");
        expect(e.status).toBe(403);
      }
    });
  });

  describe("importPdf", () => {
    it("rejects files exceeding 20MB before extraction", async () => {
      const oversizedFile = new File(["x"], "huge.pdf", { type: "application/pdf" });
      // Override size since File constructor sets it from content
      Object.defineProperty(oversizedFile, "size", { value: 21 * 1024 * 1024 });

      await expect(importPdf("proj1", oversizedFile)).rejects.toThrow(
        "PDF exceeds maximum size of 20MB"
      );

      // csrfFetch should never be called — rejected before network request
      expect(csrfFetch).not.toHaveBeenCalled();
    });

    it("allows files at exactly 20MB", async () => {
      const file = new File(["x"], "exact.pdf", { type: "application/pdf" });
      Object.defineProperty(file, "size", { value: 20 * 1024 * 1024 });

      // Mock the dynamic import of pdfLoader
      vi.mock("../pdf/pdfLoader.js", () => ({
        extractTextFromPdf: vi.fn().mockResolvedValue({
          title: "Test",
          content: "Some text",
        }),
      }));

      csrfFetch.mockResolvedValue({
        ok: true,
        json: async () => ({ page_external_id: "p1" }),
      });

      // Should not throw — 20MB is exactly at the limit, not over
      const result = await importPdf("proj1", file);
      expect(result).toEqual({ page_external_id: "p1" });
    });
  });
});
