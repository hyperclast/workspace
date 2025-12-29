/**
 * Yjs → Editor Binding Tests
 * Tests that Yjs document changes propagate correctly to CodeMirror editor
 */
import { describe, test, expect, beforeEach, afterEach } from "vitest";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import * as Y from "yjs";
import { yCollab } from "y-codemirror.next";

describe("Yjs → Editor Binding", () => {
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
    test("Yjs insert updates editor", () => {
      // Insert via Yjs
      ytext.insert(0, "Hello");

      // Editor should reflect the change
      expect(view.state.doc.toString()).toBe("Hello");
    });

    test("inserting at end of content", () => {
      ytext.insert(0, "Hello");
      ytext.insert(5, " World");

      expect(view.state.doc.toString()).toBe("Hello World");
    });

    test("inserting in middle of content", () => {
      ytext.insert(0, "Hello World");
      ytext.insert(5, " Beautiful");

      expect(view.state.doc.toString()).toBe("Hello Beautiful World");
    });

    test("multiple rapid inserts", () => {
      // Simulate rapid updates from remote client
      for (let i = 0; i < 10; i++) {
        ytext.insert(ytext.length, "a");
      }

      expect(view.state.doc.toString()).toBe("a".repeat(10));
      expect(view.state.doc.length).toBe(10);
    });

    test("inserting multiline text", () => {
      ytext.insert(0, "Line 1\nLine 2\nLine 3");

      expect(view.state.doc.toString()).toBe("Line 1\nLine 2\nLine 3");
      expect(view.state.doc.lines).toBe(3);
    });

    test("inserting unicode and emoji", () => {
      ytext.insert(0, "Hello 👋 World 🌍");

      expect(view.state.doc.toString()).toBe("Hello 👋 World 🌍");
    });
  });

  describe("Delete Operations", () => {
    test("Yjs delete updates editor", () => {
      ytext.insert(0, "Hello World");
      ytext.delete(5, 6); // Delete " World"

      expect(view.state.doc.toString()).toBe("Hello");
    });

    test("deleting from beginning", () => {
      ytext.insert(0, "Hello World");
      ytext.delete(0, 6); // Delete "Hello "

      expect(view.state.doc.toString()).toBe("World");
    });

    test("deleting from middle", () => {
      ytext.insert(0, "Hello Beautiful World");
      ytext.delete(5, 10); // Delete " Beautiful"

      expect(view.state.doc.toString()).toBe("Hello World");
    });

    test("deleting all content", () => {
      ytext.insert(0, "Delete me");
      ytext.delete(0, 9);

      expect(view.state.doc.toString()).toBe("");
      expect(view.state.doc.length).toBe(0);
    });

    test("multiple sequential deletes", () => {
      ytext.insert(0, "ABCDEFGH");
      ytext.delete(0, 1); // Delete 'A'
      ytext.delete(0, 1); // Delete 'B'
      ytext.delete(0, 1); // Delete 'C'

      expect(view.state.doc.toString()).toBe("DEFGH");
    });
  });

  describe("Replace Operations", () => {
    test("Yjs replace (delete + insert) updates editor", () => {
      ytext.insert(0, "Hello World");
      ytext.delete(6, 5); // Delete "World"
      ytext.insert(6, "Universe");

      expect(view.state.doc.toString()).toBe("Hello Universe");
    });

    test("replacing entire document", () => {
      ytext.insert(0, "Original text");
      ytext.delete(0, 13);
      ytext.insert(0, "New text");

      expect(view.state.doc.toString()).toBe("New text");
    });

    test("atomic replace in transaction", () => {
      ytext.insert(0, "Hello World");

      // Replace in single transaction
      ydoc.transact(() => {
        ytext.delete(6, 5);
        ytext.insert(6, "There");
      });

      expect(view.state.doc.toString()).toBe("Hello There");
    });
  });

  describe("Remote Updates from Another Client", () => {
    let doc2, text2;

    beforeEach(() => {
      doc2 = new Y.Doc();
      text2 = doc2.getText("codemirror");
    });

    test("receives update from remote client", () => {
      // Remote client makes edit
      text2.insert(0, "Remote edit");

      // Sync to local client
      const update = Y.encodeStateAsUpdate(doc2);
      Y.applyUpdate(ydoc, update);

      // Editor should show remote edit
      expect(view.state.doc.toString()).toBe("Remote edit");
    });

    test("merges concurrent edits from remote client", () => {
      // Start with synced state
      ytext.insert(0, "Hello World");
      const initialUpdate = Y.encodeStateAsUpdate(ydoc);
      Y.applyUpdate(doc2, initialUpdate);

      // Local edit
      ytext.insert(0, "Local: ");

      // Remote edit (concurrent)
      text2.insert(11, "!");

      // Sync remote changes to local
      const remoteUpdate = Y.encodeStateAsUpdate(doc2);
      Y.applyUpdate(ydoc, remoteUpdate);

      // Editor should have both edits
      expect(view.state.doc.toString()).toContain("Local:");
      expect(view.state.doc.toString()).toContain("!");
    });

    test("handles multiple rapid remote updates", () => {
      // Remote client makes many rapid edits
      for (let i = 0; i < 20; i++) {
        text2.insert(text2.length, `${i} `);
      }

      // Sync all updates
      const update = Y.encodeStateAsUpdate(doc2);
      Y.applyUpdate(ydoc, update);

      // Editor should reflect all updates
      expect(view.state.doc.toString()).toContain("0 ");
      expect(view.state.doc.toString()).toContain("19 ");
    });
  });

  describe("Document State Consistency", () => {
    test("editor and Yjs stay in sync", () => {
      const operations = [
        () => ytext.insert(0, "Hello"),
        () => ytext.insert(5, " World"),
        () => ytext.delete(5, 1), // Delete space
        () => ytext.insert(5, "-"),
        () => ytext.insert(11, "!"),
      ];

      operations.forEach((op) => op());

      // Editor and Yjs should have same content
      expect(view.state.doc.toString()).toBe(ytext.toString());
      expect(view.state.doc.toString()).toBe("Hello-World!");
    });

    test("document length matches after Yjs edits", () => {
      ytext.insert(0, "Test content");

      expect(view.state.doc.length).toBe(ytext.length);
      expect(view.state.doc.length).toBe(12);
    });

    test("line count matches after multiline insert", () => {
      ytext.insert(0, "Line 1\nLine 2\nLine 3\nLine 4");

      expect(view.state.doc.lines).toBe(4);
    });
  });

  describe("Complex Update Sequences", () => {
    test("handles mixed insert/delete sequence", () => {
      ytext.insert(0, "A");
      ytext.insert(1, "B");
      ytext.insert(2, "C");
      ytext.delete(1, 1); // Delete 'B'
      ytext.insert(1, "X");
      ytext.insert(3, "Y");

      expect(view.state.doc.toString()).toBe("AXCY");
    });

    test("handles large batch insert", () => {
      const largeText = "Lorem ipsum ".repeat(100);
      ytext.insert(0, largeText);

      expect(view.state.doc.toString()).toBe(largeText);
      expect(view.state.doc.length).toBe(largeText.length);
    });

    test("handles transactional updates", () => {
      ydoc.transact(() => {
        ytext.insert(0, "Line 1\n");
        ytext.insert(7, "Line 2\n");
        ytext.insert(14, "Line 3");
      });

      expect(view.state.doc.toString()).toBe("Line 1\nLine 2\nLine 3");
      expect(view.state.doc.lines).toBe(3);
    });
  });

  describe("Undo/Redo Integration", () => {
    let undoManager;

    beforeEach(() => {
      undoManager = new Y.UndoManager(ytext, {
        captureTimeout: 0,
      });
    });

    test("editor updates when Yjs undoes", () => {
      // Make edit
      ydoc.transact(() => {
        ytext.insert(0, "Hello");
      });
      expect(view.state.doc.toString()).toBe("Hello");

      // Undo
      undoManager.undo();
      expect(view.state.doc.toString()).toBe("");
    });

    test("editor updates when Yjs redoes", () => {
      ydoc.transact(() => {
        ytext.insert(0, "Hello");
      });

      undoManager.undo();
      expect(view.state.doc.toString()).toBe("");

      undoManager.redo();
      expect(view.state.doc.toString()).toBe("Hello");
    });

    test("undoes multiple operations", () => {
      ydoc.transact(() => {
        ytext.insert(0, "First");
      });
      ydoc.transact(() => {
        ytext.insert(5, " Second");
      });
      ydoc.transact(() => {
        ytext.insert(12, " Third");
      });

      expect(view.state.doc.toString()).toBe("First Second Third");

      undoManager.undo();
      expect(view.state.doc.toString()).toBe("First Second");

      undoManager.undo();
      expect(view.state.doc.toString()).toBe("First");

      undoManager.undo();
      expect(view.state.doc.toString()).toBe("");
    });
  });

  describe("Edge Cases", () => {
    test("handles empty string insert", () => {
      ytext.insert(0, "Test");
      ytext.insert(2, ""); // Empty insert

      expect(view.state.doc.toString()).toBe("Test");
    });

    test("handles special characters", () => {
      const special = 'Tab:\tNewline:\nQuote:"Slash:\\';
      ytext.insert(0, special);

      expect(view.state.doc.toString()).toBe(special);
    });

    test("inserting at position 0 repeatedly", () => {
      ytext.insert(0, "C");
      ytext.insert(0, "B");
      ytext.insert(0, "A");

      expect(view.state.doc.toString()).toBe("ABC");
    });

    test("handles very long document", () => {
      const longText = "x".repeat(10000);
      ytext.insert(0, longText);

      expect(view.state.doc.length).toBe(10000);
      expect(view.state.doc.toString()).toBe(longText);
    });
  });

  describe("Incremental Updates", () => {
    test("applies only missing updates", () => {
      const doc2 = new Y.Doc();
      const text2 = doc2.getText("codemirror");

      // Doc2 has initial content
      text2.insert(0, "Initial");
      const initialUpdate = Y.encodeStateAsUpdate(doc2);
      Y.applyUpdate(ydoc, initialUpdate);

      expect(view.state.doc.toString()).toBe("Initial");

      // Doc2 makes more edits
      text2.insert(7, " More");
      text2.insert(12, " Content");

      // Get only the new updates
      const stateVector = Y.encodeStateVector(ydoc);
      const incrementalUpdate = Y.encodeStateAsUpdate(doc2, stateVector);

      // Apply incremental update
      Y.applyUpdate(ydoc, incrementalUpdate);

      expect(view.state.doc.toString()).toBe("Initial More Content");
    });

    test("handles out-of-order update application", () => {
      const doc2 = new Y.Doc();
      const text2 = doc2.getText("codemirror");

      // Create multiple updates
      text2.insert(0, "A");
      const update1 = Y.encodeStateAsUpdate(doc2);

      text2.insert(1, "B");
      const update2 = Y.encodeStateAsUpdate(doc2);

      text2.insert(2, "C");
      const update3 = Y.encodeStateAsUpdate(doc2);

      // Apply in different order
      Y.applyUpdate(ydoc, update3);
      Y.applyUpdate(ydoc, update1);
      Y.applyUpdate(ydoc, update2);

      // Should still converge correctly
      expect(view.state.doc.toString()).toBe("ABC");
    });
  });
});
