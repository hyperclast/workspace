import { describe, test, expect, afterEach, vi } from "vitest";
import { decorateSectionHeaders } from "../../decorateSectionHeaders.js";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";

describe("decorateSectionHeaders - basic functionality", () => {
  let view;

  afterEach(() => {
    if (view && !view.destroyed) {
      view.destroy();
    }
  });

  test("decorates heading lines", () => {
    const doc = `# First Section
Content line 1
Content line 2

## Second Section
More content`;

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateSectionHeaders],
      }),
      parent: document.createElement("div"),
    });

    const plugin = view.plugin(decorateSectionHeaders);
    expect(plugin).toBeDefined();
    expect(plugin.decorations.size).toBeGreaterThan(0);

    const headerElements = view.dom.querySelectorAll(".section-header");
    expect(headerElements.length).toBe(2);
  });

  test("handles single heading document", () => {
    const doc = `# Only Section
Line 1
Line 2
Line 3`;

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateSectionHeaders],
      }),
      parent: document.createElement("div"),
    });

    const headerElements = view.dom.querySelectorAll(".section-header");
    expect(headerElements.length).toBe(1);
  });

  test("handles empty document", () => {
    const doc = "";

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateSectionHeaders],
      }),
      parent: document.createElement("div"),
    });

    const plugin = view.plugin(decorateSectionHeaders);
    expect(plugin.decorations.size).toBe(0);

    const headerElements = view.dom.querySelectorAll(".section-header");
    expect(headerElements.length).toBe(0);
  });

  test("handles multiple consecutive headings", () => {
    const doc = `# Section 1
Content 1
# Section 2
Content 2
# Section 3
Content 3
# Section 4
Content 4`;

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateSectionHeaders],
      }),
      parent: document.createElement("div"),
    });

    const headerElements = view.dom.querySelectorAll(".section-header");
    expect(headerElements.length).toBe(4);
  });

  test("decorates heading at document start", () => {
    const doc = `# First line is header
Content
## Another section`;

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateSectionHeaders],
      }),
      parent: document.createElement("div"),
    });

    const headerElements = view.dom.querySelectorAll(".section-header");
    expect(headerElements.length).toBe(2);
  });

  test("decorates heading at document end", () => {
    const doc = `# First Section
Content
## Last Section`;

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateSectionHeaders],
      }),
      parent: document.createElement("div"),
    });

    const headerElements = view.dom.querySelectorAll(".section-header");
    expect(headerElements.length).toBe(2);
  });

  test("updates decorations after document change", async () => {
    const doc = "# Initial content";

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateSectionHeaders],
      }),
      parent: document.createElement("div"),
    });

    let headerElements = view.dom.querySelectorAll(".section-header");
    expect(headerElements.length).toBe(1);

    view.dispatch({
      changes: { from: view.state.doc.length, insert: "\n# New Section" },
    });

    await new Promise((resolve) => setTimeout(resolve, 250));

    headerElements = view.dom.querySelectorAll(".section-header");
    expect(headerElements.length).toBe(2);
  });

  test("debounces rapid document changes", async () => {
    const doc = "# Initial";

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateSectionHeaders],
      }),
      parent: document.createElement("div"),
    });

    const plugin = view.plugin(decorateSectionHeaders);
    const computeSpy = vi.spyOn(plugin, "computeDecorations");
    const initialCallCount = computeSpy.mock.calls.length;

    view.dispatch({ changes: { from: 0, insert: "a" } });
    view.dispatch({ changes: { from: 0, insert: "b" } });
    view.dispatch({ changes: { from: 0, insert: "c" } });

    expect(computeSpy.mock.calls.length).toBe(initialCallCount);

    await new Promise((resolve) => setTimeout(resolve, 250));

    expect(computeSpy.mock.calls.length).toBeGreaterThan(initialCallCount);
  });

  test("handles nested headings", () => {
    const doc = `# Header 1
Content
## Header 2
More content`;

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateSectionHeaders],
      }),
      parent: document.createElement("div"),
    });

    const headerElements = view.dom.querySelectorAll(".section-header");
    expect(headerElements.length).toBe(2);
  });

  test("does not decorate non-headings", () => {
    const doc = `Just plain text
No headings here
#NoSpace doesn't count`;

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateSectionHeaders],
      }),
      parent: document.createElement("div"),
    });

    const headerElements = view.dom.querySelectorAll(".section-header");
    expect(headerElements.length).toBe(0);
  });
});

describe("decorateSectionHeaders - table interaction", () => {
  let view;

  afterEach(() => {
    if (view && !view.destroyed) {
      view.destroy();
    }
  });

  test("does not apply section header styling inside markdown tables", () => {
    const doc = `| Name | Age |
|------|-----|
| Alice | 30 |
| Bob | 25 |`;

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateSectionHeaders],
      }),
      parent: document.createElement("div"),
    });

    const headerElements = view.dom.querySelectorAll(".section-header");
    expect(headerElements.length).toBe(0);
  });

  test("applies section header styling before table", () => {
    const doc = `# User List

| Name | Age |
|------|-----|
| Alice | 30 |`;

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateSectionHeaders],
      }),
      parent: document.createElement("div"),
    });

    const headerElements = view.dom.querySelectorAll(".section-header");
    expect(headerElements.length).toBe(1);
  });

  test("applies section header styling after table", () => {
    const doc = `| Name | Age |
|------|-----|
| Alice | 30 |

# Next Section Header`;

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateSectionHeaders],
      }),
      parent: document.createElement("div"),
    });

    const headerElements = view.dom.querySelectorAll(".section-header");
    expect(headerElements.length).toBe(1);
  });

  test("handles document with both tables and headings", () => {
    const doc = `# Introduction

Some text here

| Product | Price |
|---------|-------|
| Apple   | $1.00 |
| Banana  | $0.50 |

# Summary`;

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateSectionHeaders],
      }),
      parent: document.createElement("div"),
    });

    const headerElements = view.dom.querySelectorAll(".section-header");
    expect(headerElements.length).toBe(2);
  });

  test("handles multiple tables in document", () => {
    const doc = `# Table 1

| A | B |
|---|---|
| 1 | 2 |

# Table 2

| C | D |
|---|---|
| 3 | 4 |`;

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateSectionHeaders],
      }),
      parent: document.createElement("div"),
    });

    const headerElements = view.dom.querySelectorAll(".section-header");
    expect(headerElements.length).toBe(2);
  });
});

describe("decorateSectionHeaders - memory leak prevention", () => {
  let view;

  afterEach(() => {
    if (view && !view.destroyed) {
      view.destroy();
    }
  });

  test("does not call view.update() after view is destroyed", async () => {
    const text = "# Header\nContent\n## Next section";

    view = new EditorView({
      state: EditorState.create({
        doc: text,
        extensions: [decorateSectionHeaders],
      }),
      parent: document.createElement("div"),
    });

    view.dispatch({
      changes: { from: 0, insert: "x" },
    });

    view.destroy();

    await new Promise((resolve) => setTimeout(resolve, 250));

    expect(view.destroyed).toBe(true);
  });

  test("handles destroy during pending debounce timeout", () => {
    const text = "# Section 1\n## Section 2";

    view = new EditorView({
      state: EditorState.create({
        doc: text,
        extensions: [decorateSectionHeaders],
      }),
      parent: document.createElement("div"),
    });

    view.dispatch({
      changes: { from: 0, insert: "x" },
    });

    expect(() => view.destroy()).not.toThrow();
    expect(view.destroyed).toBe(true);
  });
});
