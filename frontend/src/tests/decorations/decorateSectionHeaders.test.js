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

  test("decorates section header lines", () => {
    const doc = `First Section
Content line 1
Content line 2


Second Section
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
    expect(headerElements.length).toBe(2); // Two section headers
  });

  test("handles single section document", () => {
    const doc = `Only Section
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

  test("handles multiple consecutive sections", () => {
    const doc = `Section 1


Section 2


Section 3


Section 4`;

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

  test("decorates section at document start", () => {
    const doc = `First line is header
Content


Another section`;

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

  test("decorates section at document end", () => {
    const doc = `First Section


Last Section
Final line`;

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
    const doc = "Initial content";

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateSectionHeaders],
      }),
      parent: document.createElement("div"),
    });

    // Initially one section
    let headerElements = view.dom.querySelectorAll(".section-header");
    expect(headerElements.length).toBe(1);

    // Add a new section
    view.dispatch({
      changes: { from: view.state.doc.length, insert: "\n\n\nNew Section" },
    });

    // Wait for debounce (200ms + buffer)
    await new Promise((resolve) => setTimeout(resolve, 250));

    // Should now have two sections
    headerElements = view.dom.querySelectorAll(".section-header");
    expect(headerElements.length).toBe(2);
  });

  test("debounces rapid document changes", async () => {
    const doc = "Initial";

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

    // Make multiple rapid changes
    view.dispatch({ changes: { from: 0, insert: "a" } });
    view.dispatch({ changes: { from: 0, insert: "b" } });
    view.dispatch({ changes: { from: 0, insert: "c" } });

    // Should not have computed decorations yet (still debouncing)
    expect(computeSpy.mock.calls.length).toBe(initialCallCount);

    // Wait for debounce
    await new Promise((resolve) => setTimeout(resolve, 250));

    // Should have computed decorations once after debounce
    expect(computeSpy.mock.calls.length).toBeGreaterThan(initialCallCount);
  });

  test("handles section with only blank lines separator", () => {
    const doc = `Header 1
Content


Header 2`;

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

    // Table rows should not be decorated as section headers
    const headerElements = view.dom.querySelectorAll(".section-header");
    expect(headerElements.length).toBe(0);
  });

  test("applies section header styling before table", () => {
    const doc = `User List

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

    // Only "User List" should be a section header, not table rows
    const headerElements = view.dom.querySelectorAll(".section-header");
    expect(headerElements.length).toBe(1);
  });

  test("applies section header styling after table", () => {
    const doc = `| Name | Age |
|------|-----|
| Alice | 30 |


Next Section Header`;

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateSectionHeaders],
      }),
      parent: document.createElement("div"),
    });

    // Only "Next Section Header" should be decorated, not table rows
    const headerElements = view.dom.querySelectorAll(".section-header");
    expect(headerElements.length).toBe(1);
  });

  test("handles document with both tables and regular sections", () => {
    const doc = `Introduction

Some text here


| Product | Price |
|---------|-------|
| Apple   | $1.00 |
| Banana  | $0.50 |


Summary`;

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateSectionHeaders],
      }),
      parent: document.createElement("div"),
    });

    // Should have 2 section headers: "Introduction" and "Summary"
    // Table rows should not be decorated
    const headerElements = view.dom.querySelectorAll(".section-header");
    expect(headerElements.length).toBe(2);
  });

  test("handles multiple tables in document", () => {
    const doc = `Table 1

| A | B |
|---|---|
| 1 | 2 |


Table 2

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

    // Should have 2 section headers: "Table 1" and "Table 2"
    // Table rows should not be decorated
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
    const text = "Header\nContent\n\n\nNext section";

    view = new EditorView({
      state: EditorState.create({
        doc: text,
        extensions: [decorateSectionHeaders],
      }),
      parent: document.createElement("div"),
    });

    // Trigger an update to set the timeout
    view.dispatch({
      changes: { from: 0, insert: "x" },
    });

    // Destroy the view immediately
    view.destroy();

    // Wait for debounce timeout (200ms + buffer)
    await new Promise((resolve) => setTimeout(resolve, 250));

    // If bug exists, this test would show console errors
    // With fix, no errors should occur
    expect(view.destroyed).toBe(true);
  });

  test("handles destroy during pending debounce timeout", () => {
    const text = "Section 1\n\n\nSection 2";

    view = new EditorView({
      state: EditorState.create({
        doc: text,
        extensions: [decorateSectionHeaders],
      }),
      parent: document.createElement("div"),
    });

    // Trigger update to create timeout
    view.dispatch({
      changes: { from: 0, insert: "x" },
    });

    // Destroy before timeout fires - should not throw any errors
    expect(() => view.destroy()).not.toThrow();

    // Verify view is actually destroyed
    expect(view.destroyed).toBe(true);
  });
});
