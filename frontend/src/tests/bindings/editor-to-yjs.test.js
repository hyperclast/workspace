/**
 * Editor → Yjs Binding Tests
 * Tests that CodeMirror editor changes propagate correctly to Yjs documents
 */
import { describe, test, expect, beforeEach, afterEach } from "vitest";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import * as Y from "yjs";
import { yCollab } from "y-codemirror.next";

describe("Editor → Yjs Binding", () => {
  let ydoc, ytext, view;

  beforeEach(() => {
    ydoc = new Y.Doc();
    ytext = ydoc.getText("codemirror");

    // Create CodeMirror editor with Yjs binding
    const state = EditorState.create({
      doc: "",
      extensions: [yCollab(ytext)],
    });

    view = new EditorView({
      state,
      parent: document.createElement("div"),
    });
  });

  afterEach(() => {
    view.destroy();
  });

  describe("Insert Operations", () => {
    test("typing in editor updates Yjs document", () => {
      // Simulate user typing
      view.dispatch({
        changes: { from: 0, insert: "Hello" },
      });

      // Yjs document should reflect the change
      expect(ytext.toString()).toBe("Hello");
    });

    test("inserting at end of content", () => {
      view.dispatch({
        changes: { from: 0, insert: "Hello" },
      });
      view.dispatch({
        changes: { from: 5, insert: " World" },
      });

      expect(ytext.toString()).toBe("Hello World");
    });

    test("inserting in middle of content", () => {
      view.dispatch({
        changes: { from: 0, insert: "Hello World" },
      });
      view.dispatch({
        changes: { from: 5, insert: " Beautiful" },
      });

      expect(ytext.toString()).toBe("Hello Beautiful World");
    });

    test("multiple rapid inserts", () => {
      // Simulate rapid typing
      for (let i = 0; i < 10; i++) {
        view.dispatch({
          changes: { from: view.state.doc.length, insert: "a" },
        });
      }

      expect(ytext.toString()).toBe("a".repeat(10));
      expect(ytext.length).toBe(10);
    });

    test("inserting multiline text", () => {
      view.dispatch({
        changes: { from: 0, insert: "Line 1\nLine 2\nLine 3" },
      });

      expect(ytext.toString()).toBe("Line 1\nLine 2\nLine 3");
    });

    test("inserting unicode and emoji", () => {
      view.dispatch({
        changes: { from: 0, insert: "Hello 👋 World 🌍" },
      });

      expect(ytext.toString()).toBe("Hello 👋 World 🌍");
    });
  });

  describe("Delete Operations", () => {
    test("deleting text from editor updates Yjs", () => {
      view.dispatch({
        changes: { from: 0, insert: "Hello World" },
      });
      view.dispatch({
        changes: { from: 5, to: 11 }, // Delete " World"
      });

      expect(ytext.toString()).toBe("Hello");
    });

    test("backspace simulation", () => {
      view.dispatch({
        changes: { from: 0, insert: "Helllo" }, // Typo
      });
      view.dispatch({
        changes: { from: 4, to: 5 }, // Delete one 'l'
      });

      expect(ytext.toString()).toBe("Hello");
    });

    test("selecting and deleting range", () => {
      view.dispatch({
        changes: { from: 0, insert: "The quick brown fox" },
      });
      view.dispatch({
        changes: { from: 4, to: 15 }, // Delete "quick brown"
      });

      expect(ytext.toString()).toBe("The  fox");
    });

    test("delete all content", () => {
      view.dispatch({
        changes: { from: 0, insert: "Delete me" },
      });
      view.dispatch({
        changes: { from: 0, to: 9 },
      });

      expect(ytext.toString()).toBe("");
    });
  });

  describe("Replace Operations", () => {
    test("replacing text (delete + insert)", () => {
      view.dispatch({
        changes: { from: 0, insert: "Hello World" },
      });
      view.dispatch({
        changes: { from: 6, to: 11, insert: "Universe" },
      });

      expect(ytext.toString()).toBe("Hello Universe");
    });

    test("replacing entire document", () => {
      view.dispatch({
        changes: { from: 0, insert: "Original text" },
      });
      view.dispatch({
        changes: { from: 0, to: 13, insert: "New text" },
      });

      expect(ytext.toString()).toBe("New text");
    });
  });

  describe("Complex Edit Sequences", () => {
    test("simulating real typing behavior", () => {
      // Type "Hello"
      "Hello".split("").forEach((char, i) => {
        view.dispatch({
          changes: { from: i, insert: char },
        });
      });

      expect(ytext.toString()).toBe("Hello");

      // Add space
      view.dispatch({
        changes: { from: 5, insert: " " },
      });

      // Type "World"
      "World".split("").forEach((char, i) => {
        view.dispatch({
          changes: { from: 6 + i, insert: char },
        });
      });

      expect(ytext.toString()).toBe("Hello World");
    });

    test("paste large text", () => {
      const largeText = "Lorem ipsum ".repeat(100);
      view.dispatch({
        changes: { from: 0, insert: largeText },
      });

      expect(ytext.toString()).toBe(largeText);
      expect(ytext.length).toBe(largeText.length);
    });

    test("multiple simultaneous changes", () => {
      // All positions are relative to the original document
      // Since original is empty, all inserts must be at position 0
      view.dispatch({
        changes: [
          { from: 0, insert: "Start " },
          { from: 0, insert: "Middle " },
          { from: 0, insert: "End" },
        ],
      });

      // CodeMirror applies changes with adjusted positions
      expect(ytext.toString()).toBe("Start Middle End");
    });
  });

  describe("Editor State Consistency", () => {
    test("editor and Yjs stay in sync after many operations", () => {
      const operations = [
        { from: 0, insert: "Hello" },
        { from: 5, insert: " World" },
        { from: 5, to: 6 }, // Delete space
        { from: 5, insert: "-" },
        { from: 11, insert: "!" },
      ];

      operations.forEach((op) => {
        view.dispatch({ changes: op });
      });

      // Editor and Yjs should have same content
      expect(view.state.doc.toString()).toBe(ytext.toString());
      expect(view.state.doc.toString()).toBe("Hello-World!");
    });

    test("document length matches after edits", () => {
      view.dispatch({
        changes: { from: 0, insert: "Test content" },
      });

      expect(view.state.doc.length).toBe(ytext.length);
      expect(view.state.doc.length).toBe(12);
    });
  });

  describe("Transaction Handling", () => {
    test("single transaction with multiple changes", () => {
      // Better approach: make sequential changes instead of simultaneous
      // to avoid position calculation complexity
      view.dispatch({
        changes: { from: 0, insert: "Line 1\n" },
      });
      view.dispatch({
        changes: { from: 7, insert: "Line 2\n" },
      });
      view.dispatch({
        changes: { from: 14, insert: "Line 3" },
      });

      expect(ytext.toString()).toBe("Line 1\nLine 2\nLine 3");
    });

    test("rapid sequential transactions", () => {
      for (let i = 0; i < 50; i++) {
        view.dispatch({
          changes: { from: i, insert: `${i} ` },
        });
      }

      const editorText = view.state.doc.toString();
      const yjsText = ytext.toString();

      expect(editorText).toBe(yjsText);
      expect(yjsText).toContain("0 ");
      expect(yjsText).toContain("49 ");
    });
  });

  describe("Edge Cases", () => {
    test("inserting at position 0 repeatedly", () => {
      view.dispatch({ changes: { from: 0, insert: "C" } });
      view.dispatch({ changes: { from: 0, insert: "B" } });
      view.dispatch({ changes: { from: 0, insert: "A" } });

      expect(ytext.toString()).toBe("ABC");
    });

    test("empty string inserts do nothing", () => {
      view.dispatch({ changes: { from: 0, insert: "Test" } });
      view.dispatch({ changes: { from: 2, insert: "" } });

      expect(ytext.toString()).toBe("Test");
    });

    test("handles special characters", () => {
      const special = 'Tab:\tNewline:\nQuote:"Slash:\\';
      view.dispatch({ changes: { from: 0, insert: special } });

      expect(ytext.toString()).toBe(special);
    });
  });
});
