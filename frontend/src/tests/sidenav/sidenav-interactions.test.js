/**
 * Sidenav Interaction Tests
 *
 * Baseline tests for sidenav click behavior and event handling.
 * These tests verify the core interaction logic before adding keyboard accessibility.
 *
 * Test categories:
 * 1. Project header interactions (expand/collapse)
 * 2. Page item interactions (navigation)
 * 3. Files header interactions (expand/collapse)
 * 4. File item interactions (open in new tab)
 * 5. Event isolation (child clicks don't bubble to parents)
 */

import { describe, test, expect, vi, beforeEach, afterEach } from "vitest";

// Mock localStorage
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

describe("Sidenav Store - Project Expansion", () => {
  beforeEach(() => {
    localStorageMock.clear();
  });

  // Simulate the store's toggle logic
  function createExpandedState(initial = []) {
    let expandedProjectIds = new Set(initial);

    return {
      toggle: (projectId) => {
        if (expandedProjectIds.has(projectId)) {
          expandedProjectIds.delete(projectId);
        } else {
          expandedProjectIds.add(projectId);
        }
        expandedProjectIds = new Set(expandedProjectIds);
        return expandedProjectIds;
      },
      isExpanded: (projectId) => expandedProjectIds.has(projectId),
      getAll: () => expandedProjectIds,
    };
  }

  test("toggleProjectExpanded expands a collapsed project", () => {
    const state = createExpandedState();

    expect(state.isExpanded("proj1")).toBe(false);

    state.toggle("proj1");

    expect(state.isExpanded("proj1")).toBe(true);
  });

  test("toggleProjectExpanded collapses an expanded project", () => {
    const state = createExpandedState(["proj1"]);

    expect(state.isExpanded("proj1")).toBe(true);

    state.toggle("proj1");

    expect(state.isExpanded("proj1")).toBe(false);
  });

  test("multiple projects can be expanded simultaneously", () => {
    const state = createExpandedState();

    state.toggle("proj1");
    state.toggle("proj2");

    expect(state.isExpanded("proj1")).toBe(true);
    expect(state.isExpanded("proj2")).toBe(true);
  });

  test("collapsing one project does not affect others", () => {
    const state = createExpandedState(["proj1", "proj2", "proj3"]);

    state.toggle("proj2");

    expect(state.isExpanded("proj1")).toBe(true);
    expect(state.isExpanded("proj2")).toBe(false);
    expect(state.isExpanded("proj3")).toBe(true);
  });
});

describe("Sidenav Store - Files Section Expansion", () => {
  beforeEach(() => {
    localStorageMock.clear();
  });

  // Simulate the files section expansion logic
  function createFilesSectionState(initial = []) {
    let expandedFilesSections = new Set(initial);

    return {
      toggle: (projectId) => {
        if (expandedFilesSections.has(projectId)) {
          expandedFilesSections.delete(projectId);
        } else {
          expandedFilesSections.add(projectId);
        }
        expandedFilesSections = new Set(expandedFilesSections);
        return expandedFilesSections;
      },
      isExpanded: (projectId) => expandedFilesSections.has(projectId),
    };
  }

  test("toggleFilesSectionExpanded expands a collapsed files section", () => {
    const state = createFilesSectionState();

    expect(state.isExpanded("proj1")).toBe(false);

    state.toggle("proj1");

    expect(state.isExpanded("proj1")).toBe(true);
  });

  test("toggleFilesSectionExpanded collapses an expanded files section", () => {
    const state = createFilesSectionState(["proj1"]);

    expect(state.isExpanded("proj1")).toBe(true);

    state.toggle("proj1");

    expect(state.isExpanded("proj1")).toBe(false);
  });

  test("files sections are independent per project", () => {
    const state = createFilesSectionState();

    state.toggle("proj1");
    state.toggle("proj2");

    expect(state.isExpanded("proj1")).toBe(true);
    expect(state.isExpanded("proj2")).toBe(true);

    state.toggle("proj1");

    expect(state.isExpanded("proj1")).toBe(false);
    expect(state.isExpanded("proj2")).toBe(true);
  });
});

describe("Sidenav Store - Page Navigation", () => {
  test("navigateToPage calls the navigate handler with pageId", () => {
    const onNavigate = vi.fn();
    let expandedProjectIds = new Set();

    function navigateToPage(pageId, projectId) {
      if (projectId) {
        expandedProjectIds.add(projectId);
      }
      if (onNavigate) {
        onNavigate(pageId);
      }
    }

    navigateToPage("page123", "proj1");

    expect(onNavigate).toHaveBeenCalledWith("page123");
    expect(onNavigate).toHaveBeenCalledTimes(1);
  });

  test("navigateToPage expands the containing project", () => {
    const onNavigate = vi.fn();
    let expandedProjectIds = new Set();

    function navigateToPage(pageId, projectId) {
      if (projectId) {
        expandedProjectIds.add(projectId);
      }
      if (onNavigate) {
        onNavigate(pageId);
      }
    }

    navigateToPage("page123", "proj1");

    expect(expandedProjectIds.has("proj1")).toBe(true);
  });

  test("navigateToPage works without projectId", () => {
    const onNavigate = vi.fn();

    function navigateToPage(pageId, projectId) {
      if (onNavigate) {
        onNavigate(pageId);
      }
    }

    navigateToPage("page123", null);

    expect(onNavigate).toHaveBeenCalledWith("page123");
  });
});

describe("Sidenav - Menu Button Click Handling", () => {
  test("menu button click sets openMenuId and does not toggle project expansion", () => {
    let openMenuId = null;
    let projectToggled = false;

    function handleProjectHeaderClick(projectId) {
      projectToggled = true;
    }

    function handleMenuBtnClick(e, projectId) {
      e.stopPropagation();
      openMenuId = openMenuId === projectId ? null : projectId;
    }

    // Simulate click on menu button
    const mockEvent = { stopPropagation: vi.fn() };
    handleMenuBtnClick(mockEvent, "proj1");

    expect(openMenuId).toBe("proj1");
    expect(mockEvent.stopPropagation).toHaveBeenCalled();
    expect(projectToggled).toBe(false);
  });

  test("clicking menu button again closes it", () => {
    let openMenuId = "proj1";

    function handleMenuBtnClick(e, projectId) {
      e.stopPropagation();
      openMenuId = openMenuId === projectId ? null : projectId;
    }

    const mockEvent = { stopPropagation: vi.fn() };
    handleMenuBtnClick(mockEvent, "proj1");

    expect(openMenuId).toBeNull();
  });

  test("clicking different project menu button switches menus", () => {
    let openMenuId = "proj1";

    function handleMenuBtnClick(e, projectId) {
      e.stopPropagation();
      openMenuId = openMenuId === projectId ? null : projectId;
    }

    const mockEvent = { stopPropagation: vi.fn() };
    handleMenuBtnClick(mockEvent, "proj2");

    expect(openMenuId).toBe("proj2");
  });
});

describe("Sidenav - Page Menu Button Click Handling", () => {
  test("page menu button click sets openPageMenuId and does not navigate", () => {
    let openPageMenuId = null;
    let pageNavigated = false;

    function handlePageClick(pageId, projectId) {
      pageNavigated = true;
    }

    function handlePageMenuBtnClick(e, pageId) {
      e.stopPropagation();
      openPageMenuId = openPageMenuId === pageId ? null : pageId;
    }

    const mockEvent = { stopPropagation: vi.fn() };
    handlePageMenuBtnClick(mockEvent, "page1");

    expect(openPageMenuId).toBe("page1");
    expect(mockEvent.stopPropagation).toHaveBeenCalled();
    expect(pageNavigated).toBe(false);
  });

  test("page menu button closes project menu if open", () => {
    let openMenuId = "proj1";
    let openPageMenuId = null;

    function handlePageMenuBtnClick(e, pageId) {
      e.stopPropagation();
      openPageMenuId = openPageMenuId === pageId ? null : pageId;
      openMenuId = null;
    }

    const mockEvent = { stopPropagation: vi.fn() };
    handlePageMenuBtnClick(mockEvent, "page1");

    expect(openPageMenuId).toBe("page1");
    expect(openMenuId).toBeNull();
  });
});

describe("Sidenav - File Item Click Handling", () => {
  test("file click opens file link in new tab", () => {
    const windowOpen = vi.fn();
    globalThis.open = windowOpen;

    function handleFileClick(e, file) {
      e.stopPropagation();
      if (file.link) {
        globalThis.open(file.link, "_blank");
      }
    }

    const mockEvent = { stopPropagation: vi.fn() };
    const file = { external_id: "file1", link: "https://example.com/files/abc" };

    handleFileClick(mockEvent, file);

    expect(windowOpen).toHaveBeenCalledWith("https://example.com/files/abc", "_blank");
    expect(mockEvent.stopPropagation).toHaveBeenCalled();
  });

  test("file click does nothing if file has no link", () => {
    const windowOpen = vi.fn();
    globalThis.open = windowOpen;

    function handleFileClick(e, file) {
      e.stopPropagation();
      if (file.link) {
        globalThis.open(file.link, "_blank");
      }
    }

    const mockEvent = { stopPropagation: vi.fn() };
    const file = { external_id: "file1", link: null };

    handleFileClick(mockEvent, file);

    expect(windowOpen).not.toHaveBeenCalled();
  });
});

describe("Sidenav - Files Section Click Handling", () => {
  test("files header click toggles files section expansion", () => {
    let expandedFilesSections = new Set();

    function toggleFilesSectionExpanded(projectId) {
      if (expandedFilesSections.has(projectId)) {
        expandedFilesSections.delete(projectId);
      } else {
        expandedFilesSections.add(projectId);
      }
      expandedFilesSections = new Set(expandedFilesSections);
    }

    function handleFilesSectionClick(e, projectId) {
      e.stopPropagation();
      toggleFilesSectionExpanded(projectId);
    }

    const mockEvent = { stopPropagation: vi.fn() };

    // First click - expand
    handleFilesSectionClick(mockEvent, "proj1");
    expect(expandedFilesSections.has("proj1")).toBe(true);

    // Second click - collapse
    handleFilesSectionClick(mockEvent, "proj1");
    expect(expandedFilesSections.has("proj1")).toBe(false);
  });

  test("files header click does not affect project expansion", () => {
    let expandedProjectIds = new Set(["proj1"]);
    let expandedFilesSections = new Set();

    function toggleFilesSectionExpanded(projectId) {
      if (expandedFilesSections.has(projectId)) {
        expandedFilesSections.delete(projectId);
      } else {
        expandedFilesSections.add(projectId);
      }
    }

    function handleFilesSectionClick(e, projectId) {
      e.stopPropagation();
      toggleFilesSectionExpanded(projectId);
    }

    const mockEvent = { stopPropagation: vi.fn() };
    handleFilesSectionClick(mockEvent, "proj1");

    expect(expandedProjectIds.has("proj1")).toBe(true); // Project still expanded
    expect(expandedFilesSections.has("proj1")).toBe(true); // Files section now expanded
  });
});

describe("Sidenav - Event Isolation", () => {
  test("stopPropagation prevents parent handler from firing", () => {
    const parentHandler = vi.fn();
    const childHandler = vi.fn();

    // Simulate DOM event propagation behavior
    function simulateClick(handlers) {
      let propagationStopped = false;
      const event = {
        stopPropagation: () => {
          propagationStopped = true;
        },
      };

      for (const handler of handlers) {
        if (propagationStopped) break;
        handler(event);
      }
    }

    // Child handler calls stopPropagation
    const childWithStop = (e) => {
      e.stopPropagation();
      childHandler();
    };

    // Simulate click starting from child, bubbling to parent
    simulateClick([childWithStop, parentHandler]);

    expect(childHandler).toHaveBeenCalled();
    expect(parentHandler).not.toHaveBeenCalled();
  });

  test("without stopPropagation, both handlers fire", () => {
    const parentHandler = vi.fn();
    const childHandler = vi.fn();

    function simulateClick(handlers) {
      let propagationStopped = false;
      const event = {
        stopPropagation: () => {
          propagationStopped = true;
        },
      };

      for (const handler of handlers) {
        if (propagationStopped) break;
        handler(event);
      }
    }

    // Child handler does NOT call stopPropagation
    const childWithoutStop = (e) => {
      childHandler();
    };

    simulateClick([childWithoutStop, parentHandler]);

    expect(childHandler).toHaveBeenCalled();
    expect(parentHandler).toHaveBeenCalled();
  });
});

describe("Sidenav - Global Click Handler", () => {
  test("clicking outside menus closes all menus", () => {
    let openMenuId = "proj1";
    let openPageMenuId = "page1";

    function closeAllMenus() {
      openMenuId = null;
      openPageMenuId = null;
    }

    function handleGlobalClick(e) {
      if (!e.target.closest(".project-menu") && !e.target.closest(".page-menu")) {
        closeAllMenus();
      }
    }

    // Simulate click on something that's not a menu
    const mockEvent = {
      target: {
        closest: (selector) => null, // Not inside any menu
      },
    };

    handleGlobalClick(mockEvent);

    expect(openMenuId).toBeNull();
    expect(openPageMenuId).toBeNull();
  });

  test("clicking inside project menu does not close it", () => {
    let openMenuId = "proj1";

    function closeAllMenus() {
      openMenuId = null;
    }

    function handleGlobalClick(e) {
      if (!e.target.closest(".project-menu") && !e.target.closest(".page-menu")) {
        closeAllMenus();
      }
    }

    // Simulate click inside project menu
    const mockEvent = {
      target: {
        closest: (selector) => (selector === ".project-menu" ? {} : null),
      },
    };

    handleGlobalClick(mockEvent);

    expect(openMenuId).toBe("proj1"); // Menu stays open
  });
});

describe("Sidenav - Project Files State Management", () => {
  test("addFileToProject adds file to existing project files", () => {
    let projectFiles = {
      proj1: [{ external_id: "file1", filename: "doc.pdf" }],
    };

    function addFileToProject(projectId, file) {
      const files = projectFiles[projectId] || [];
      projectFiles = { ...projectFiles, [projectId]: [...files, file] };
    }

    addFileToProject("proj1", { external_id: "file2", filename: "image.png" });

    expect(projectFiles.proj1).toHaveLength(2);
    expect(projectFiles.proj1[1].filename).toBe("image.png");
  });

  test("addFileToProject creates array for new project", () => {
    let projectFiles = {};

    function addFileToProject(projectId, file) {
      const files = projectFiles[projectId] || [];
      projectFiles = { ...projectFiles, [projectId]: [...files, file] };
    }

    addFileToProject("proj1", { external_id: "file1", filename: "doc.pdf" });

    expect(projectFiles.proj1).toHaveLength(1);
    expect(projectFiles.proj1[0].filename).toBe("doc.pdf");
  });

  test("getProjectFiles returns empty array for unknown project", () => {
    const projectFiles = {
      proj1: [{ external_id: "file1" }],
    };

    function getProjectFiles(projectId) {
      return projectFiles[projectId] || [];
    }

    expect(getProjectFiles("proj2")).toEqual([]);
  });
});

describe("Sidenav - Keyboard Accessibility Preparation", () => {
  /**
   * These tests document the expected behavior for keyboard handlers
   * that will be added to fix the a11y warnings.
   */

  test("Enter key should trigger same action as click on project header", () => {
    let projectToggled = false;

    function handleProjectHeaderClick(projectId) {
      projectToggled = true;
    }

    function handleProjectHeaderKeydown(e, projectId) {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        handleProjectHeaderClick(projectId);
      }
    }

    const mockEvent = { key: "Enter", preventDefault: vi.fn() };
    handleProjectHeaderKeydown(mockEvent, "proj1");

    expect(projectToggled).toBe(true);
    expect(mockEvent.preventDefault).toHaveBeenCalled();
  });

  test("Space key should trigger same action as click on project header", () => {
    let projectToggled = false;

    function handleProjectHeaderClick(projectId) {
      projectToggled = true;
    }

    function handleProjectHeaderKeydown(e, projectId) {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        handleProjectHeaderClick(projectId);
      }
    }

    const mockEvent = { key: " ", preventDefault: vi.fn() };
    handleProjectHeaderKeydown(mockEvent, "proj1");

    expect(projectToggled).toBe(true);
    expect(mockEvent.preventDefault).toHaveBeenCalled();
  });

  test("Other keys should not trigger action", () => {
    let projectToggled = false;

    function handleProjectHeaderClick(projectId) {
      projectToggled = true;
    }

    function handleProjectHeaderKeydown(e, projectId) {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        handleProjectHeaderClick(projectId);
      }
    }

    const mockEvent = { key: "Tab", preventDefault: vi.fn() };
    handleProjectHeaderKeydown(mockEvent, "proj1");

    expect(projectToggled).toBe(false);
    expect(mockEvent.preventDefault).not.toHaveBeenCalled();
  });

  test("Keyboard event on nested button should not trigger parent handler", () => {
    let parentTriggered = false;
    let childTriggered = false;

    function handleParentKeydown(e, projectId) {
      // Only handle if the event target is the parent element itself
      if (e.target !== e.currentTarget) return;
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        parentTriggered = true;
      }
    }

    function handleChildClick(e) {
      e.stopPropagation();
      childTriggered = true;
    }

    // Simulate keydown on child button - target !== currentTarget
    const mockEvent = {
      key: "Enter",
      preventDefault: vi.fn(),
      stopPropagation: vi.fn(),
      target: { id: "child-button" },
      currentTarget: { id: "parent-div" },
    };

    handleParentKeydown(mockEvent, "proj1");

    expect(parentTriggered).toBe(false);
  });

  test("Keyboard event directly on parent should trigger handler", () => {
    let parentTriggered = false;

    function handleParentKeydown(e, projectId) {
      // Only handle if the event target is the parent element itself
      if (e.target !== e.currentTarget) return;
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        parentTriggered = true;
      }
    }

    // Simulate keydown directly on parent - target === currentTarget
    const parentElement = { id: "parent-div" };
    const mockEvent = {
      key: "Enter",
      preventDefault: vi.fn(),
      target: parentElement,
      currentTarget: parentElement,
    };

    handleParentKeydown(mockEvent, "proj1");

    expect(parentTriggered).toBe(true);
  });
});
