/**
 * Sidenav Folder State Tests
 *
 * Tests for folder expand/collapse state management, localStorage persistence,
 * and auto-expand of ancestor folders when navigating to a nested page.
 *
 * These mirror the approach in sidenav-interactions.test.js: we re-implement
 * the core logic from sidenav.svelte.js because Svelte 5 $state runes
 * cannot be directly imported in vitest.
 */

import { describe, test, expect, beforeEach } from "vitest";

// ---------------------------------------------------------------------------
// localStorage mock (shared across tests)
// ---------------------------------------------------------------------------

const localStorageMock = (() => {
  let store = {};
  return {
    getItem: (key) => store[key] || null,
    setItem: (key, value) => {
      store[key] = value;
    },
    removeItem: (key) => {
      delete store[key];
    },
    clear: () => {
      store = {};
    },
  };
})();

Object.defineProperty(globalThis, "localStorage", { value: localStorageMock });

// ---------------------------------------------------------------------------
// Constants (mirrored from sidenav.svelte.js)
// ---------------------------------------------------------------------------

const STORAGE_KEY_FOLDERS_PREFIX = "folders:";

// ---------------------------------------------------------------------------
// Simulated folder state (mirrors sidenav.svelte.js logic)
// ---------------------------------------------------------------------------

function createFolderState() {
  let expandedFolderIds = {};

  function loadExpandedFolders(projectId) {
    try {
      const stored = localStorage.getItem(STORAGE_KEY_FOLDERS_PREFIX + projectId);
      if (stored) {
        return new Set(JSON.parse(stored));
      }
      return new Set();
    } catch {
      return new Set();
    }
  }

  function saveExpandedFolders(projectId) {
    const folderSet = expandedFolderIds[projectId];
    if (folderSet && folderSet.size > 0) {
      localStorage.setItem(STORAGE_KEY_FOLDERS_PREFIX + projectId, JSON.stringify([...folderSet]));
    } else {
      localStorage.removeItem(STORAGE_KEY_FOLDERS_PREFIX + projectId);
    }
  }

  function ensureFolderStateLoaded(projectId) {
    if (!expandedFolderIds[projectId]) {
      const loaded = loadExpandedFolders(projectId);
      if (loaded.size > 0) {
        expandedFolderIds = { ...expandedFolderIds, [projectId]: loaded };
      }
    }
  }

  return {
    toggleFolderExpanded(projectId, folderId) {
      const folderSet = expandedFolderIds[projectId] || loadExpandedFolders(projectId);
      if (folderSet.has(folderId)) {
        folderSet.delete(folderId);
      } else {
        folderSet.add(folderId);
      }
      expandedFolderIds = { ...expandedFolderIds, [projectId]: new Set(folderSet) };
      saveExpandedFolders(projectId);
    },

    expandFolder(projectId, folderId) {
      const folderSet = expandedFolderIds[projectId] || loadExpandedFolders(projectId);
      if (!folderSet.has(folderId)) {
        folderSet.add(folderId);
        expandedFolderIds = { ...expandedFolderIds, [projectId]: new Set(folderSet) };
        saveExpandedFolders(projectId);
      }
    },

    isFolderExpanded(projectId, folderId) {
      const folderSet = expandedFolderIds[projectId];
      return folderSet ? folderSet.has(folderId) : false;
    },

    getExpandedFolderIds(projectId) {
      return expandedFolderIds[projectId] || new Set();
    },

    ensureFolderStateLoaded,

    // Simulate the auto-expand logic from setProjects()
    autoExpandAncestors(projectId, activePage, folders) {
      if (activePage?.folder_id && folders?.length > 0) {
        const folderById = new Map(folders.map((f) => [f.external_id, f]));
        let folderId = activePage.folder_id;
        while (folderId) {
          this.expandFolder(projectId, folderId);
          const folder = folderById.get(folderId);
          folderId = folder?.parent_id || null;
        }
      }
    },
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("Sidenav Folder State - Toggle / Expand / Query", () => {
  beforeEach(() => {
    localStorageMock.clear();
  });

  test("toggleFolderExpanded expands a collapsed folder", () => {
    const state = createFolderState();

    expect(state.isFolderExpanded("proj1", "f1")).toBe(false);

    state.toggleFolderExpanded("proj1", "f1");

    expect(state.isFolderExpanded("proj1", "f1")).toBe(true);
  });

  test("toggleFolderExpanded collapses an expanded folder", () => {
    const state = createFolderState();

    state.toggleFolderExpanded("proj1", "f1");
    expect(state.isFolderExpanded("proj1", "f1")).toBe(true);

    state.toggleFolderExpanded("proj1", "f1");
    expect(state.isFolderExpanded("proj1", "f1")).toBe(false);
  });

  test("expandFolder opens a folder without toggling", () => {
    const state = createFolderState();

    state.expandFolder("proj1", "f1");
    expect(state.isFolderExpanded("proj1", "f1")).toBe(true);

    // Calling expandFolder again should NOT collapse it
    state.expandFolder("proj1", "f1");
    expect(state.isFolderExpanded("proj1", "f1")).toBe(true);
  });

  test("isFolderExpanded returns false for unknown project", () => {
    const state = createFolderState();
    expect(state.isFolderExpanded("unknown_project", "f1")).toBe(false);
  });

  test("isFolderExpanded returns false for unknown folder in known project", () => {
    const state = createFolderState();
    state.expandFolder("proj1", "f1");
    expect(state.isFolderExpanded("proj1", "f_other")).toBe(false);
  });

  test("folder state is isolated between projects", () => {
    const state = createFolderState();

    state.expandFolder("proj1", "f1");
    state.expandFolder("proj2", "f2");

    expect(state.isFolderExpanded("proj1", "f1")).toBe(true);
    expect(state.isFolderExpanded("proj1", "f2")).toBe(false);
    expect(state.isFolderExpanded("proj2", "f2")).toBe(true);
    expect(state.isFolderExpanded("proj2", "f1")).toBe(false);
  });

  test("multiple folders can be expanded in the same project", () => {
    const state = createFolderState();

    state.expandFolder("proj1", "f1");
    state.expandFolder("proj1", "f2");
    state.expandFolder("proj1", "f3");

    expect(state.isFolderExpanded("proj1", "f1")).toBe(true);
    expect(state.isFolderExpanded("proj1", "f2")).toBe(true);
    expect(state.isFolderExpanded("proj1", "f3")).toBe(true);
  });

  test("collapsing one folder does not affect others in the same project", () => {
    const state = createFolderState();

    state.expandFolder("proj1", "f1");
    state.expandFolder("proj1", "f2");

    state.toggleFolderExpanded("proj1", "f1");

    expect(state.isFolderExpanded("proj1", "f1")).toBe(false);
    expect(state.isFolderExpanded("proj1", "f2")).toBe(true);
  });

  test("getExpandedFolderIds returns empty Set for unknown project", () => {
    const state = createFolderState();
    const ids = state.getExpandedFolderIds("unknown");
    expect(ids.size).toBe(0);
  });

  test("getExpandedFolderIds returns the expanded set", () => {
    const state = createFolderState();
    state.expandFolder("proj1", "f1");
    state.expandFolder("proj1", "f2");

    const ids = state.getExpandedFolderIds("proj1");
    expect(ids.has("f1")).toBe(true);
    expect(ids.has("f2")).toBe(true);
    expect(ids.size).toBe(2);
  });
});

describe("Sidenav Folder State - localStorage Persistence", () => {
  beforeEach(() => {
    localStorageMock.clear();
  });

  test("expanded folders are saved to localStorage", () => {
    const state = createFolderState();

    state.expandFolder("proj1", "f1");
    state.expandFolder("proj1", "f2");

    const stored = JSON.parse(localStorage.getItem("folders:proj1"));
    expect(stored).toContain("f1");
    expect(stored).toContain("f2");
  });

  test("collapsing all folders removes the localStorage key", () => {
    const state = createFolderState();

    state.expandFolder("proj1", "f1");
    expect(localStorage.getItem("folders:proj1")).not.toBeNull();

    state.toggleFolderExpanded("proj1", "f1");
    expect(localStorage.getItem("folders:proj1")).toBeNull();
  });

  test("expanded folders restore from localStorage via ensureFolderStateLoaded", () => {
    // Pre-seed localStorage
    localStorage.setItem("folders:proj1", JSON.stringify(["f1", "f2"]));

    const state = createFolderState();
    state.ensureFolderStateLoaded("proj1");

    expect(state.isFolderExpanded("proj1", "f1")).toBe(true);
    expect(state.isFolderExpanded("proj1", "f2")).toBe(true);
    expect(state.isFolderExpanded("proj1", "f3")).toBe(false);
  });

  test("ensureFolderStateLoaded does not overwrite existing in-memory state", () => {
    const state = createFolderState();

    // Expand a folder in-memory
    state.expandFolder("proj1", "f_new");

    // Pre-seed localStorage with different data (simulating stale storage)
    localStorage.setItem("folders:proj1", JSON.stringify(["f_old"]));

    // ensureFolderStateLoaded should not overwrite because state already exists
    state.ensureFolderStateLoaded("proj1");

    expect(state.isFolderExpanded("proj1", "f_new")).toBe(true);
  });

  test("corrupted localStorage data is handled gracefully", () => {
    localStorage.setItem("folders:proj1", "not-valid-json");

    const state = createFolderState();
    state.ensureFolderStateLoaded("proj1");

    // Should not throw, returns false for all
    expect(state.isFolderExpanded("proj1", "f1")).toBe(false);
  });

  test("localStorage is scoped per project", () => {
    const state = createFolderState();

    state.expandFolder("proj1", "f1");
    state.expandFolder("proj2", "f2");

    const stored1 = JSON.parse(localStorage.getItem("folders:proj1"));
    const stored2 = JSON.parse(localStorage.getItem("folders:proj2"));

    expect(stored1).toEqual(["f1"]);
    expect(stored2).toEqual(["f2"]);
  });
});

describe("Sidenav Folder State - Auto-Expand Ancestors", () => {
  beforeEach(() => {
    localStorageMock.clear();
  });

  test("auto-expands all ancestor folders for a deeply nested page", () => {
    const state = createFolderState();

    const folders = [
      { external_id: "f1", parent_id: null, name: "Engineering" },
      { external_id: "f2", parent_id: "f1", name: "Backend" },
      { external_id: "f3", parent_id: "f2", name: "API" },
    ];
    const activePage = { external_id: "p1", folder_id: "f3" };

    state.autoExpandAncestors("proj1", activePage, folders);

    expect(state.isFolderExpanded("proj1", "f1")).toBe(true);
    expect(state.isFolderExpanded("proj1", "f2")).toBe(true);
    expect(state.isFolderExpanded("proj1", "f3")).toBe(true);
  });

  test("auto-expands only the root folder for a page in a root folder", () => {
    const state = createFolderState();

    const folders = [
      { external_id: "f1", parent_id: null, name: "Notes" },
      { external_id: "f2", parent_id: null, name: "Other" },
    ];
    const activePage = { external_id: "p1", folder_id: "f1" };

    state.autoExpandAncestors("proj1", activePage, folders);

    expect(state.isFolderExpanded("proj1", "f1")).toBe(true);
    expect(state.isFolderExpanded("proj1", "f2")).toBe(false);
  });

  test("does nothing when page has no folder_id", () => {
    const state = createFolderState();

    const folders = [{ external_id: "f1", parent_id: null, name: "Notes" }];
    const activePage = { external_id: "p1", folder_id: null };

    state.autoExpandAncestors("proj1", activePage, folders);

    expect(state.isFolderExpanded("proj1", "f1")).toBe(false);
  });

  test("does nothing when folders array is empty", () => {
    const state = createFolderState();

    const activePage = { external_id: "p1", folder_id: "f1" };

    state.autoExpandAncestors("proj1", activePage, []);

    expect(state.isFolderExpanded("proj1", "f1")).toBe(false);
  });

  test("does nothing when activePage is null", () => {
    const state = createFolderState();

    const folders = [{ external_id: "f1", parent_id: null, name: "Notes" }];

    state.autoExpandAncestors("proj1", null, folders);

    expect(state.isFolderExpanded("proj1", "f1")).toBe(false);
  });

  test("does not collapse other already-expanded folders", () => {
    const state = createFolderState();

    // Pre-expand an unrelated folder
    state.expandFolder("proj1", "f_other");

    const folders = [
      { external_id: "f1", parent_id: null, name: "Design" },
      { external_id: "f_other", parent_id: null, name: "Other" },
    ];
    const activePage = { external_id: "p1", folder_id: "f1" };

    state.autoExpandAncestors("proj1", activePage, folders);

    expect(state.isFolderExpanded("proj1", "f1")).toBe(true);
    expect(state.isFolderExpanded("proj1", "f_other")).toBe(true);
  });
});
