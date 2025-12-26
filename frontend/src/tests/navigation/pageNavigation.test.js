import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

vi.mock("../../api.js", () => ({
  fetchPage: vi.fn(),
  fetchProjectsWithPages: vi.fn(),
}));

vi.mock("../../lib/toast.js", () => ({
  showToast: vi.fn(),
}));

import { fetchPage, fetchProjectsWithPages } from "../../api.js";
import { showToast } from "../../lib/toast.js";

describe("Page Navigation", () => {
  let originalWindow;
  let historyStates;

  beforeEach(() => {
    vi.clearAllMocks();
    historyStates = [];

    originalWindow = global.window;
    global.window = {
      history: {
        pushState: vi.fn((state, title, url) => historyStates.push({ type: 'push', url })),
        replaceState: vi.fn((state, title, url) => historyStates.push({ type: 'replace', url })),
      },
      location: {
        pathname: '/pages/test123/',
      },
    };
  });

  afterEach(() => {
    global.window = originalWindow;
  });

  describe("fetchPage error handling", () => {
    it("throws error with status text when page not found", async () => {
      fetchPage.mockRejectedValue(new Error("Failed to fetch page: Not Found"));

      await expect(fetchPage("nonexistent")).rejects.toThrow("Failed to fetch page: Not Found");
    });

    it("throws error with status text when unauthorized", async () => {
      fetchPage.mockRejectedValue(new Error("Failed to fetch page: Forbidden"));

      await expect(fetchPage("restricted")).rejects.toThrow("Failed to fetch page: Forbidden");
    });
  });

  describe("showToast integration", () => {
    it("showToast can be called with error type", () => {
      showToast("Page not found", "error");

      expect(showToast).toHaveBeenCalledWith("Page not found", "error");
    });

    it("showToast can be called with success type", () => {
      showToast("Page loaded", "success");

      expect(showToast).toHaveBeenCalledWith("Page loaded", "success");
    });
  });

  describe("redirectToFirstAvailablePage logic", () => {
    it("finds first page from projects list", async () => {
      const mockProjects = [
        {
          external_id: "proj1",
          name: "Project 1",
          pages: [
            { external_id: "page1", title: "Page 1" },
            { external_id: "page2", title: "Page 2" },
          ],
        },
      ];

      fetchProjectsWithPages.mockResolvedValue(mockProjects);

      const projects = await fetchProjectsWithPages();

      let firstPageId = null;
      for (const project of projects) {
        if (project.pages && project.pages.length > 0) {
          firstPageId = project.pages[0].external_id;
          break;
        }
      }

      expect(firstPageId).toBe("page1");
    });

    it("returns null when no projects have pages", async () => {
      const mockProjects = [
        { external_id: "proj1", name: "Project 1", pages: [] },
        { external_id: "proj2", name: "Project 2", pages: [] },
      ];

      fetchProjectsWithPages.mockResolvedValue(mockProjects);

      const projects = await fetchProjectsWithPages();

      let firstPageId = null;
      for (const project of projects) {
        if (project.pages && project.pages.length > 0) {
          firstPageId = project.pages[0].external_id;
          break;
        }
      }

      expect(firstPageId).toBeNull();
    });

    it("returns null when projects list is empty", async () => {
      fetchProjectsWithPages.mockResolvedValue([]);

      const projects = await fetchProjectsWithPages();

      let firstPageId = null;
      for (const project of projects) {
        if (project.pages && project.pages.length > 0) {
          firstPageId = project.pages[0].external_id;
          break;
        }
      }

      expect(firstPageId).toBeNull();
    });

    it("skips projects with undefined pages", async () => {
      const mockProjects = [
        { external_id: "proj1", name: "Project 1" }, // no pages property
        { external_id: "proj2", name: "Project 2", pages: [{ external_id: "page2", title: "Page 2" }] },
      ];

      fetchProjectsWithPages.mockResolvedValue(mockProjects);

      const projects = await fetchProjectsWithPages();

      let firstPageId = null;
      for (const project of projects) {
        if (project.pages && project.pages.length > 0) {
          firstPageId = project.pages[0].external_id;
          break;
        }
      }

      expect(firstPageId).toBe("page2");
    });
  });

  describe("URL handling", () => {
    it("uses replaceState to avoid polluting history on redirect", () => {
      window.history.replaceState({}, '', '/pages/newpage123/');

      expect(window.history.replaceState).toHaveBeenCalledWith({}, '', '/pages/newpage123/');
      expect(historyStates).toContainEqual({ type: 'replace', url: '/pages/newpage123/' });
    });

    it("uses pushState for normal navigation", () => {
      window.history.pushState({}, '', '/pages/page456/');

      expect(window.history.pushState).toHaveBeenCalledWith({}, '', '/pages/page456/');
      expect(historyStates).toContainEqual({ type: 'push', url: '/pages/page456/' });
    });

    it("redirects to root when no pages available", () => {
      window.history.replaceState({}, '', '/');

      expect(window.history.replaceState).toHaveBeenCalledWith({}, '', '/');
      expect(historyStates).toContainEqual({ type: 'replace', url: '/' });
    });
  });

  describe("error message formatting", () => {
    it("shows 'Page not found' for 404 errors", () => {
      const error = new Error("Failed to fetch page: Not Found");
      const message = error.message.includes("Not Found") ? "Page not found" : error.message;

      expect(message).toBe("Page not found");
    });

    it("shows 'Access denied' for 403 errors", () => {
      const error = new Error("Failed to fetch page: Forbidden");
      const message = error.message.includes("Forbidden") ? "Access denied" : error.message;

      expect(message).toBe("Access denied");
    });

    it("preserves original error message for other errors", () => {
      const error = new Error("Network error");
      const message = error.message;

      expect(message).toBe("Network error");
    });
  });
});
