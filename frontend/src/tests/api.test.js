import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { fetchProjectsWithPages, createProject, createPage, fetchOrgs, fetchPage } from "../api.js";

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

      expect(csrfFetch).toHaveBeenCalledWith("/api/projects/?details=full");
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

      expect(csrfFetch).toHaveBeenCalledWith("/api/projects/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          org_id: "org1",
          name: "New Project",
          description: "Description",
        }),
      });
      expect(result).toEqual(mockProject);
    });

    it("throws error when project creation fails", async () => {
      csrfFetch.mockResolvedValue({
        ok: false,
        statusText: "Bad Request",
      });

      await expect(createProject("org1", "New Project")).rejects.toThrow("Failed to create project");
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

      expect(csrfFetch).toHaveBeenCalledWith("/api/pages/", {
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

      expect(csrfFetch).toHaveBeenCalledWith("/api/pages/page1/");
      expect(result).toEqual(mockPage);
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

      await expect(fetchPage("page1")).rejects.toThrow("Failed to fetch page: Internal Server Error");
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

      expect(csrfFetch).toHaveBeenCalledWith("/api/orgs/");
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
});
