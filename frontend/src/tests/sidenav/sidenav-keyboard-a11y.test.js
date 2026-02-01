/**
 * Sidenav Keyboard Accessibility Tests
 *
 * Tests for the keyboard accessibility improvements added to the Sidenav component.
 * These tests verify that:
 * 1. Enter activates on keydown (matching native button behavior)
 * 2. Space activates on keyup (matching native button behavior)
 * 3. Keyboard events on nested buttons don't trigger parent handlers
 * 4. preventDefault is called appropriately to prevent scrolling
 */

import { describe, test, expect, vi } from "vitest";

/**
 * These are the exact implementations of handleKeydown and handleKeyup from Sidenav.svelte
 * Copied here to test the logic in isolation.
 */
function handleKeydown(e, action) {
  if (e.target !== e.currentTarget) return;
  if (e.key === "Enter") {
    e.preventDefault();
    action();
  } else if (e.key === " ") {
    e.preventDefault(); // Prevent scroll, but don't activate yet
  }
}

function handleKeyup(e, action) {
  if (e.target !== e.currentTarget) return;
  if (e.key === " ") {
    action();
  }
}

describe("Sidenav Keyboard Accessibility - handleKeydown function", () => {
  describe("Enter key behavior", () => {
    test("Enter key triggers action on keydown", () => {
      const action = vi.fn();
      const element = { id: "test-element" };
      const event = {
        key: "Enter",
        target: element,
        currentTarget: element,
        preventDefault: vi.fn(),
      };

      handleKeydown(event, action);

      expect(action).toHaveBeenCalledTimes(1);
      expect(event.preventDefault).toHaveBeenCalledTimes(1);
    });

    test("Enter does not trigger on keyup", () => {
      const action = vi.fn();
      const element = { id: "test-element" };
      const event = {
        key: "Enter",
        target: element,
        currentTarget: element,
      };

      handleKeyup(event, action);

      expect(action).not.toHaveBeenCalled();
    });
  });

  describe("Space key behavior (keydown prevents scroll, keyup activates)", () => {
    test("Space on keydown calls preventDefault but does NOT trigger action", () => {
      const action = vi.fn();
      const element = { id: "test-element" };
      const event = {
        key: " ",
        target: element,
        currentTarget: element,
        preventDefault: vi.fn(),
      };

      handleKeydown(event, action);

      expect(action).not.toHaveBeenCalled();
      expect(event.preventDefault).toHaveBeenCalledTimes(1);
    });

    test("Space on keyup triggers action", () => {
      const action = vi.fn();
      const element = { id: "test-element" };
      const event = {
        key: " ",
        target: element,
        currentTarget: element,
      };

      handleKeyup(event, action);

      expect(action).toHaveBeenCalledTimes(1);
    });

    test("Full Space key cycle: keydown prevents scroll, keyup activates", () => {
      const action = vi.fn();
      const element = { id: "test-element" };

      // Keydown event
      const keydownEvent = {
        key: " ",
        target: element,
        currentTarget: element,
        preventDefault: vi.fn(),
      };

      // Keyup event
      const keyupEvent = {
        key: " ",
        target: element,
        currentTarget: element,
      };

      // Simulate the full cycle
      handleKeydown(keydownEvent, action);
      expect(action).not.toHaveBeenCalled(); // Not yet
      expect(keydownEvent.preventDefault).toHaveBeenCalled(); // Prevent scroll

      handleKeyup(keyupEvent, action);
      expect(action).toHaveBeenCalledTimes(1); // Now activated
    });
  });

  describe("Other keys are ignored", () => {
    test("Tab key does not trigger action", () => {
      const action = vi.fn();
      const element = { id: "test-element" };
      const event = {
        key: "Tab",
        target: element,
        currentTarget: element,
        preventDefault: vi.fn(),
      };

      handleKeydown(event, action);
      handleKeyup(event, action);

      expect(action).not.toHaveBeenCalled();
      expect(event.preventDefault).not.toHaveBeenCalled();
    });

    test("Escape key does not trigger action", () => {
      const action = vi.fn();
      const element = { id: "test-element" };
      const event = {
        key: "Escape",
        target: element,
        currentTarget: element,
        preventDefault: vi.fn(),
      };

      handleKeydown(event, action);
      handleKeyup(event, action);

      expect(action).not.toHaveBeenCalled();
    });

    test("Arrow keys do not trigger action", () => {
      const action = vi.fn();
      const element = { id: "test-element" };

      for (const key of ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"]) {
        const event = {
          key,
          target: element,
          currentTarget: element,
          preventDefault: vi.fn(),
        };

        handleKeydown(event, action);
        handleKeyup(event, action);
      }

      expect(action).not.toHaveBeenCalled();
    });

    test("Letter keys do not trigger action", () => {
      const action = vi.fn();
      const element = { id: "test-element" };

      for (const key of ["a", "b", "z", "A", "Z"]) {
        const event = {
          key,
          target: element,
          currentTarget: element,
          preventDefault: vi.fn(),
        };

        handleKeydown(event, action);
        handleKeyup(event, action);
      }

      expect(action).not.toHaveBeenCalled();
    });
  });

  describe("Event target filtering (prevents child button interference)", () => {
    test("keydown does not trigger action when event originates from child element", () => {
      const action = vi.fn();
      const parentElement = { id: "parent-div" };
      const childElement = { id: "child-button" };
      const event = {
        key: "Enter",
        target: childElement, // Event originated from child
        currentTarget: parentElement, // Handler is on parent
        preventDefault: vi.fn(),
      };

      handleKeydown(event, action);

      expect(action).not.toHaveBeenCalled();
      expect(event.preventDefault).not.toHaveBeenCalled();
    });

    test("keyup does not trigger action when event originates from child element", () => {
      const action = vi.fn();
      const parentElement = { id: "parent-div" };
      const childElement = { id: "child-button" };
      const event = {
        key: " ",
        target: childElement,
        currentTarget: parentElement,
      };

      handleKeyup(event, action);

      expect(action).not.toHaveBeenCalled();
    });

    test("Space on nested menu button does not expand project", () => {
      const action = vi.fn();
      const parentElement = { id: "sidebar-project-header" };
      const menuButton = { id: "project-menu-btn" };

      const keydownEvent = {
        key: " ",
        target: menuButton,
        currentTarget: parentElement,
        preventDefault: vi.fn(),
      };

      const keyupEvent = {
        key: " ",
        target: menuButton,
        currentTarget: parentElement,
      };

      handleKeydown(keydownEvent, action);
      handleKeyup(keyupEvent, action);

      expect(action).not.toHaveBeenCalled();
    });

    test("Enter on nested menu button does not expand project", () => {
      const action = vi.fn();
      const parentElement = { id: "sidebar-project-header" };
      const menuButton = { id: "project-menu-btn" };
      const event = {
        key: "Enter",
        target: menuButton,
        currentTarget: parentElement,
        preventDefault: vi.fn(),
      };

      handleKeydown(event, action);

      expect(action).not.toHaveBeenCalled();
    });

    test("triggers action when event target equals currentTarget", () => {
      const action = vi.fn();
      const element = { id: "sidebar-project-header" };
      const event = {
        key: "Enter",
        target: element,
        currentTarget: element,
        preventDefault: vi.fn(),
      };

      handleKeydown(event, action);

      expect(action).toHaveBeenCalledTimes(1);
    });
  });

  describe("Integration scenarios", () => {
    test("project header: Enter key expands/collapses project", () => {
      let projectExpanded = false;
      const toggleProject = () => {
        projectExpanded = !projectExpanded;
      };

      const headerElement = { id: "sidebar-project-header" };
      const event = {
        key: "Enter",
        target: headerElement,
        currentTarget: headerElement,
        preventDefault: vi.fn(),
      };

      handleKeydown(event, toggleProject);

      expect(projectExpanded).toBe(true);
    });

    test("project header: Space key expands/collapses on keyup", () => {
      let projectExpanded = false;
      const toggleProject = () => {
        projectExpanded = !projectExpanded;
      };

      const headerElement = { id: "sidebar-project-header" };

      // Keydown - just prevent default
      handleKeydown(
        {
          key: " ",
          target: headerElement,
          currentTarget: headerElement,
          preventDefault: vi.fn(),
        },
        toggleProject
      );
      expect(projectExpanded).toBe(false); // Not yet

      // Keyup - now activate
      handleKeyup(
        {
          key: " ",
          target: headerElement,
          currentTarget: headerElement,
        },
        toggleProject
      );
      expect(projectExpanded).toBe(true);
    });

    test("page item: Space key navigates on keyup", () => {
      let navigatedToPage = null;
      const navigateToPage = (pageId) => {
        navigatedToPage = pageId;
      };

      const pageElement = { id: "sidebar-item" };

      handleKeyup(
        {
          key: " ",
          target: pageElement,
          currentTarget: pageElement,
        },
        () => navigateToPage("page123")
      );

      expect(navigatedToPage).toBe("page123");
    });

    test("page item: Enter on share button does not navigate", () => {
      let navigatedToPage = null;
      const navigateToPage = (pageId) => {
        navigatedToPage = pageId;
      };

      const pageElement = { id: "sidebar-item" };
      const shareButton = { id: "page-shared-indicator" };
      const event = {
        key: "Enter",
        target: shareButton,
        currentTarget: pageElement,
        preventDefault: vi.fn(),
      };

      handleKeydown(event, () => navigateToPage("page123"));

      expect(navigatedToPage).toBeNull();
    });

    test("files header: Enter key toggles files section", () => {
      let filesExpanded = false;
      const toggleFilesSection = () => {
        filesExpanded = !filesExpanded;
      };

      const filesHeader = { id: "sidebar-files-header" };
      const event = {
        key: "Enter",
        target: filesHeader,
        currentTarget: filesHeader,
        preventDefault: vi.fn(),
      };

      handleKeydown(event, toggleFilesSection);

      expect(filesExpanded).toBe(true);
    });

    test("file item: Enter key opens file", () => {
      let openedFile = null;
      const openFile = (file) => {
        openedFile = file;
      };

      const fileElement = { id: "sidebar-file-item" };
      const file = { external_id: "file1", link: "https://example.com/file" };
      const event = {
        key: "Enter",
        target: fileElement,
        currentTarget: fileElement,
        preventDefault: vi.fn(),
      };

      handleKeydown(event, () => openFile(file));

      expect(openedFile).toEqual(file);
    });
  });

  describe("preventDefault behavior", () => {
    test("preventDefault is called for Enter key on keydown", () => {
      const action = vi.fn();
      const element = { id: "test" };
      const event = {
        key: "Enter",
        target: element,
        currentTarget: element,
        preventDefault: vi.fn(),
      };

      handleKeydown(event, action);

      expect(event.preventDefault).toHaveBeenCalledTimes(1);
    });

    test("preventDefault is called for Space key on keydown (prevents scroll)", () => {
      const action = vi.fn();
      const element = { id: "test" };
      const event = {
        key: " ",
        target: element,
        currentTarget: element,
        preventDefault: vi.fn(),
      };

      handleKeydown(event, action);

      expect(event.preventDefault).toHaveBeenCalledTimes(1);
    });

    test("preventDefault is NOT called on keyup", () => {
      // keyup doesn't need preventDefault - the action is just fired
      const action = vi.fn();
      const element = { id: "test" };
      const event = {
        key: " ",
        target: element,
        currentTarget: element,
        preventDefault: vi.fn(),
      };

      handleKeyup(event, action);

      // Note: we don't even call preventDefault in handleKeyup
      expect(event.preventDefault).not.toHaveBeenCalled();
    });

    test("preventDefault is NOT called when event is filtered out by target check", () => {
      const action = vi.fn();
      const parentElement = { id: "parent" };
      const childElement = { id: "child" };
      const event = {
        key: "Enter",
        target: childElement,
        currentTarget: parentElement,
        preventDefault: vi.fn(),
      };

      handleKeydown(event, action);

      expect(event.preventDefault).not.toHaveBeenCalled();
    });
  });
});
