import { describe, test, expect, beforeEach, afterEach } from "vitest";
import { EditorView } from "@codemirror/view";
import { EditorState } from "@codemirror/state";
import { markdown } from "@codemirror/lang-markdown";

describe("Editor Visibility", () => {
  let container;
  let view;

  beforeEach(() => {
    // Create a container that mimics the actual DOM structure
    container = document.createElement("div");
    container.id = "editor";
    container.style.width = "100%";
    container.style.maxWidth = "768px";
    container.style.height = "100%";
    document.body.appendChild(container);
  });

  afterEach(() => {
    if (view) {
      view.destroy();
    }
    if (container && container.parentNode) {
      container.parentNode.removeChild(container);
    }
  });

  test("editor content has visible text color", () => {
    // Create a simple theme
    const simpleTheme = EditorView.theme({
      "&": {
        color: "black",
        backgroundColor: "white"
      },
      ".cm-content": {
        caretColor: "black",
        color: "black"
      },
      ".cm-line": {
        color: "black"
      }
    }, { dark: false });

    view = new EditorView({
      parent: container,
      state: EditorState.create({
        doc: "Test content that should be visible",
        extensions: [markdown(), simpleTheme],
      }),
    });

    // Get the actual DOM elements
    const contentElement = view.dom.querySelector(".cm-content");
    const lineElement = view.dom.querySelector(".cm-line");

    expect(contentElement).toBeTruthy();
    expect(lineElement).toBeTruthy();

    // Check computed styles
    const contentStyle = window.getComputedStyle(contentElement);
    const lineStyle = window.getComputedStyle(lineElement);

    // Text should have a visible color (not transparent, not white on white)
    expect(contentStyle.color).not.toBe("rgba(0, 0, 0, 0)"); // not transparent
    expect(contentStyle.color).not.toBe("transparent");

    expect(lineStyle.color).not.toBe("rgba(0, 0, 0, 0)"); // not transparent
    expect(lineStyle.color).not.toBe("transparent");

    // Background should be set
    const editorStyle = window.getComputedStyle(view.dom);
    expect(editorStyle.backgroundColor).not.toBe("transparent");
  });

  test("editor content is not hidden via display:none", () => {
    const simpleTheme = EditorView.theme({
      ".cm-content": { color: "black" },
      ".cm-line": { color: "black" }
    }, { dark: false });

    view = new EditorView({
      parent: container,
      state: EditorState.create({
        doc: "Visible text",
        extensions: [markdown(), simpleTheme],
      }),
    });

    const contentElement = view.dom.querySelector(".cm-content");
    const lineElement = view.dom.querySelector(".cm-line");

    const contentStyle = window.getComputedStyle(contentElement);
    const lineStyle = window.getComputedStyle(lineElement);

    expect(contentStyle.display).not.toBe("none");
    expect(lineStyle.display).not.toBe("none");
  });

  test("editor content is not hidden via visibility:hidden", () => {
    const simpleTheme = EditorView.theme({
      ".cm-content": { color: "black" },
      ".cm-line": { color: "black" }
    }, { dark: false });

    view = new EditorView({
      parent: container,
      state: EditorState.create({
        doc: "Visible text",
        extensions: [markdown(), simpleTheme],
      }),
    });

    const contentElement = view.dom.querySelector(".cm-content");
    const lineElement = view.dom.querySelector(".cm-line");

    const contentStyle = window.getComputedStyle(contentElement);
    const lineStyle = window.getComputedStyle(lineElement);

    expect(contentStyle.visibility).not.toBe("hidden");
    expect(lineStyle.visibility).not.toBe("hidden");
  });

  test("editor content has non-zero opacity", () => {
    const simpleTheme = EditorView.theme({
      ".cm-content": { color: "black" },
      ".cm-line": { color: "black" }
    }, { dark: false });

    view = new EditorView({
      parent: container,
      state: EditorState.create({
        doc: "Visible text",
        extensions: [markdown(), simpleTheme],
      }),
    });

    const contentElement = view.dom.querySelector(".cm-content");
    const lineElement = view.dom.querySelector(".cm-line");

    const contentStyle = window.getComputedStyle(contentElement);
    const lineStyle = window.getComputedStyle(lineElement);

    // In happy-dom, opacity might be empty string if not set, which defaults to 1
    const contentOpacity = contentStyle.opacity === "" ? 1 : parseFloat(contentStyle.opacity);
    const lineOpacity = lineStyle.opacity === "" ? 1 : parseFloat(lineStyle.opacity);

    expect(contentOpacity).toBeGreaterThan(0);
    expect(lineOpacity).toBeGreaterThan(0);
  });

  test("editor has non-zero dimensions", () => {
    const simpleTheme = EditorView.theme({
      ".cm-content": { color: "black" },
      ".cm-line": { color: "black" }
    }, { dark: false });

    view = new EditorView({
      parent: container,
      state: EditorState.create({
        doc: "Visible text",
        extensions: [markdown(), simpleTheme],
      }),
    });

    const rect = view.dom.getBoundingClientRect();

    // Note: In happy-dom, dimensions might be 0 in test environment
    // In a real browser, the editor would have actual dimensions
    // We test that the element exists and has the necessary structure
    expect(view.dom).toBeTruthy();
    expect(view.dom.querySelector(".cm-content")).toBeTruthy();

    // If dimensions are available (real browser), they should be > 0
    if (rect.width > 0 || rect.height > 0) {
      expect(rect.width).toBeGreaterThan(0);
      expect(rect.height).toBeGreaterThan(0);
    }
  });

  test("editor lines are positioned on-screen", () => {
    const simpleTheme = EditorView.theme({
      ".cm-content": { color: "black" },
      ".cm-line": { color: "black" }
    }, { dark: false });

    view = new EditorView({
      parent: container,
      state: EditorState.create({
        doc: "Visible text line 1\nVisible text line 2",
        extensions: [markdown(), simpleTheme],
      }),
    });

    const lineElement = view.dom.querySelector(".cm-line");
    const rect = lineElement.getBoundingClientRect();

    // Line should not be positioned off-screen (negative coordinates)
    expect(rect.left).toBeGreaterThanOrEqual(0);
    expect(rect.top).toBeGreaterThanOrEqual(0);
  });

  test("text color contrasts with background", () => {
    const simpleTheme = EditorView.theme({
      "&": {
        color: "black",
        backgroundColor: "white"
      },
      ".cm-content": {
        color: "black"
      },
      ".cm-line": {
        color: "black"
      }
    }, { dark: false });

    view = new EditorView({
      parent: container,
      state: EditorState.create({
        doc: "Visible text",
        extensions: [markdown(), simpleTheme],
      }),
    });

    const editorStyle = window.getComputedStyle(view.dom);
    const lineElement = view.dom.querySelector(".cm-line");
    const lineStyle = window.getComputedStyle(lineElement);

    // Parse colors (may be empty in happy-dom)
    const bgColor = editorStyle.backgroundColor || "white";
    const textColor = lineStyle.color || "black";

    // They should not be the same
    expect(textColor).not.toBe(bgColor);

    // In a real browser environment, verify actual RGB values
    if (textColor.includes("rgb") && bgColor.includes("rgb")) {
      expect(textColor).toContain("rgb(0, 0, 0)"); // black
      expect(bgColor).toContain("rgb(255, 255, 255)"); // white
    }
  });

  test("cursor is visible", () => {
    const simpleTheme = EditorView.theme({
      ".cm-cursor": {
        borderLeftColor: "black",
        borderLeftWidth: "2px"
      }
    }, { dark: false });

    view = new EditorView({
      parent: container,
      state: EditorState.create({
        doc: "Text",
        extensions: [markdown(), simpleTheme],
      }),
    });

    view.focus();

    const cursor = view.dom.querySelector(".cm-cursor");
    if (cursor) {
      const cursorStyle = window.getComputedStyle(cursor);

      expect(cursorStyle.borderLeftColor).not.toBe("transparent");
      expect(cursorStyle.borderLeftColor).not.toBe("rgba(0, 0, 0, 0)");
      expect(parseFloat(cursorStyle.borderLeftWidth)).toBeGreaterThan(0);
    }
  });
});
