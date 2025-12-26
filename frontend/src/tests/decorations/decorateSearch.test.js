import { describe, test, expect, afterEach, beforeEach } from "vitest";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import {
  decorateSearch,
  setSearchHighlights,
  updateActiveMatchIndex,
} from "../../decorateSearch.js";

describe("decorateSearch - Search Highlight Management", () => {
  let view;
  let searchHighlights = [];

  beforeEach(() => {
    // Reset search highlights before each test
    searchHighlights = [];
    setSearchHighlights(() => searchHighlights);
  });

  afterEach(() => {
    if (view && !view.destroyed) {
      view.destroy();
    }
    // Reset to empty function
    setSearchHighlights(() => []);
  });

  test("decorates search matches with highlight class", () => {
    const doc = "The quick brown fox jumps over the lazy dog";

    // Set up search highlights for "the" (case-insensitive positions)
    searchHighlights = [
      { from: 0, to: 3 }, // "The"
      { from: 31, to: 34 }, // "the"
    ];

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateSearch],
      }),
      parent: document.createElement("div"),
    });

    const plugin = view.plugin(decorateSearch);
    expect(plugin).toBeDefined();
    expect(plugin.decorations.size).toBeGreaterThan(0);

    const highlightElements = view.dom.querySelectorAll(".search-highlight");
    expect(highlightElements.length).toBe(2);
  });

  test("marks active search match with active class", () => {
    const doc = "apple apple apple";

    searchHighlights = [
      { from: 0, to: 5 }, // First "apple"
      { from: 6, to: 11 }, // Second "apple"
      { from: 12, to: 17 }, // Third "apple"
    ];

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateSearch],
      }),
      parent: document.createElement("div"),
    });

    // Set the second match as active
    updateActiveMatchIndex(1);

    // Force view update
    view.dispatch({ changes: { from: 0, to: 0, insert: "" } });

    const activeElements = view.dom.querySelectorAll(".search-highlight-active");
    expect(activeElements.length).toBe(1);

    const regularElements = view.dom.querySelectorAll(".search-highlight");
    // Total highlights should be 3, but 1 is active
    expect(regularElements.length).toBe(2);
  });

  test("handles no search matches", () => {
    const doc = "Some text without matches";

    searchHighlights = []; // No highlights

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateSearch],
      }),
      parent: document.createElement("div"),
    });

    const plugin = view.plugin(decorateSearch);
    expect(plugin.decorations.size).toBe(0);

    const highlightElements = view.dom.querySelectorAll(".search-highlight");
    expect(highlightElements.length).toBe(0);
  });

  test("updates decorations when search highlights change", () => {
    const doc = "test test test";

    searchHighlights = [{ from: 0, to: 4 }]; // One match

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateSearch],
      }),
      parent: document.createElement("div"),
    });

    let highlightElements = view.dom.querySelectorAll(".search-highlight");
    expect(highlightElements.length).toBe(1);

    // Add more highlights
    searchHighlights = [
      { from: 0, to: 4 },
      { from: 5, to: 9 },
      { from: 10, to: 14 },
    ];

    // Trigger update by dispatching a change (even a no-op change)
    view.dispatch({
      changes: { from: 0, to: 0, insert: "" },
    });

    highlightElements = view.dom.querySelectorAll(".search-highlight");
    expect(highlightElements.length).toBe(3);
  });

  test("updates active match index", () => {
    const doc = "one two three four";

    searchHighlights = [
      { from: 0, to: 3 }, // "one"
      { from: 4, to: 7 }, // "two"
      { from: 8, to: 13 }, // "three"
    ];

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateSearch],
      }),
      parent: document.createElement("div"),
    });

    // Initially no active match (index -1)
    let activeElements = view.dom.querySelectorAll(".search-highlight-active");
    expect(activeElements.length).toBe(0);

    // Set first match as active
    updateActiveMatchIndex(0);
    view.dispatch({ changes: { from: 0, to: 0, insert: "" } });
    activeElements = view.dom.querySelectorAll(".search-highlight-active");
    expect(activeElements.length).toBe(1);

    // Set third match as active
    updateActiveMatchIndex(2);
    view.dispatch({ changes: { from: 0, to: 0, insert: "" } });
    activeElements = view.dom.querySelectorAll(".search-highlight-active");
    expect(activeElements.length).toBe(1);
  });

  test("handles overlapping search ranges gracefully", () => {
    const doc = "abcdefghij";

    // Overlapping ranges (not realistic but testing robustness)
    searchHighlights = [
      { from: 0, to: 3 }, // "abc"
      { from: 2, to: 5 }, // "cde" (overlaps)
    ];

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateSearch],
      }),
      parent: document.createElement("div"),
    });

    const plugin = view.plugin(decorateSearch);
    expect(plugin.decorations).toBeDefined();
    expect(plugin.decorations.size).toBeGreaterThan(0);
  });

  test("clears active highlight when index set to -1", () => {
    const doc = "find find find";

    searchHighlights = [
      { from: 0, to: 4 },
      { from: 5, to: 9 },
      { from: 10, to: 14 },
    ];

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateSearch],
      }),
      parent: document.createElement("div"),
    });

    // Set first match as active
    updateActiveMatchIndex(0);
    view.dispatch({ changes: { from: 0, to: 0, insert: "" } });
    let activeElements = view.dom.querySelectorAll(".search-highlight-active");
    expect(activeElements.length).toBe(1);

    // Clear active match
    updateActiveMatchIndex(-1);
    view.dispatch({ changes: { from: 0, to: 0, insert: "" } });
    activeElements = view.dom.querySelectorAll(".search-highlight-active");
    expect(activeElements.length).toBe(0);

    // All should be regular highlights
    const regularElements = view.dom.querySelectorAll(".search-highlight");
    expect(regularElements.length).toBe(3);
  });

  test("handles single character matches", () => {
    const doc = "a b a b a";

    searchHighlights = [
      { from: 0, to: 1 }, // "a"
      { from: 4, to: 5 }, // "a"
      { from: 8, to: 9 }, // "a"
    ];

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateSearch],
      }),
      parent: document.createElement("div"),
    });

    const highlightElements = view.dom.querySelectorAll(".search-highlight");
    expect(highlightElements.length).toBe(3);
  });

  test("handles match at document boundaries", () => {
    const doc = "start middle end";

    searchHighlights = [
      { from: 0, to: 5 }, // "start" at beginning
      { from: 13, to: 16 }, // "end" at end
    ];

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateSearch],
      }),
      parent: document.createElement("div"),
    });

    const highlightElements = view.dom.querySelectorAll(".search-highlight");
    expect(highlightElements.length).toBe(2);
  });
});
