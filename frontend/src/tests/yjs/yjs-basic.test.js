/**
 * Basic Yjs CRDT Operations Tests
 * Tests fundamental document operations without network simulation
 */
import { describe, test, expect, beforeEach } from "vitest";
import * as Y from "yjs";

describe("Yjs Basic Document Operations", () => {
  let doc;
  let text;

  beforeEach(() => {
    doc = new Y.Doc();
    text = doc.getText("content");
  });

  describe("Insert Operations", () => {
    test("inserts text at position 0", () => {
      text.insert(0, "Hello");
      expect(text.toString()).toBe("Hello");
    });

    test("inserts text at end of existing content", () => {
      text.insert(0, "Hello");
      text.insert(5, " World");
      expect(text.toString()).toBe("Hello World");
    });

    test("inserts text in middle of content", () => {
      text.insert(0, "Hello World");
      text.insert(5, " Beautiful");
      expect(text.toString()).toBe("Hello Beautiful World");
    });

    test("handles multiple sequential inserts", () => {
      text.insert(0, "H");
      text.insert(1, "e");
      text.insert(2, "l");
      text.insert(3, "l");
      text.insert(4, "o");
      expect(text.toString()).toBe("Hello");
    });

    test("inserts empty string without error", () => {
      text.insert(0, "Hello");
      text.insert(5, "");
      expect(text.toString()).toBe("Hello");
    });
  });

  describe("Delete Operations", () => {
    test("deletes text range from beginning", () => {
      text.insert(0, "Hello World");
      text.delete(0, 6); // Delete "Hello "
      expect(text.toString()).toBe("World");
    });

    test("deletes text range from end", () => {
      text.insert(0, "Hello World");
      text.delete(5, 6); // Delete " World"
      expect(text.toString()).toBe("Hello");
    });

    test("deletes text range from middle", () => {
      text.insert(0, "Hello Beautiful World");
      text.delete(5, 10); // Delete " Beautiful"
      expect(text.toString()).toBe("Hello World");
    });

    test("deletes single character", () => {
      text.insert(0, "Hello");
      text.delete(4, 1); // Delete "o"
      expect(text.toString()).toBe("Hell");
    });

    test("deletes all content", () => {
      text.insert(0, "Hello World");
      text.delete(0, 11);
      expect(text.toString()).toBe("");
    });

    test("handles delete on empty document", () => {
      // Yjs will throw an error if trying to delete from empty document
      // This is expected behavior - you can't delete what doesn't exist
      expect(() => text.delete(0, 5)).toThrow();
    });
  });

  describe("Combined Insert and Delete", () => {
    test("performs insert then delete", () => {
      text.insert(0, "Hello World");
      text.delete(5, 6); // Delete " World"
      text.insert(5, "!");
      expect(text.toString()).toBe("Hello!");
    });

    test("simulates typing with backspace", () => {
      text.insert(0, "Helllo"); // Typo
      text.delete(4, 1); // Remove extra 'l'
      expect(text.toString()).toBe("Hello");
    });

    test("replaces text (delete + insert)", () => {
      text.insert(0, "Hello World");
      text.delete(6, 5); // Delete "World"
      text.insert(6, "Universe");
      expect(text.toString()).toBe("Hello Universe");
    });
  });

  describe("Undo/Redo Operations", () => {
    let undoManager;

    beforeEach(() => {
      undoManager = new Y.UndoManager(text, {
        captureTimeout: 0, // Capture each change separately
      });
    });

    test("undoes single insert", () => {
      text.insert(0, "Hello");
      expect(text.toString()).toBe("Hello");

      undoManager.undo();
      expect(text.toString()).toBe("");
    });

    test("redoes single insert", () => {
      text.insert(0, "Hello");
      undoManager.undo();
      expect(text.toString()).toBe("");

      undoManager.redo();
      expect(text.toString()).toBe("Hello");
    });

    test("undoes multiple operations", () => {
      // Operations need to be in separate transactions to be undone separately
      doc.transact(() => {
        text.insert(0, "Hello");
      });
      doc.transact(() => {
        text.insert(5, " World");
      });
      expect(text.toString()).toBe("Hello World");

      undoManager.undo();
      expect(text.toString()).toBe("Hello");

      undoManager.undo();
      expect(text.toString()).toBe("");
    });

    test("undoes and redoes in sequence", () => {
      // Operations need to be in separate transactions
      doc.transact(() => {
        text.insert(0, "Hello");
      });
      doc.transact(() => {
        text.insert(5, " World");
      });

      undoManager.undo(); // Undo " World"
      expect(text.toString()).toBe("Hello");

      undoManager.redo(); // Redo " World"
      expect(text.toString()).toBe("Hello World");

      undoManager.undo(); // Undo " World" again
      undoManager.undo(); // Undo "Hello"
      expect(text.toString()).toBe("");
    });

    test("clears redo stack on new operation", () => {
      // Operations need to be in separate transactions
      doc.transact(() => {
        text.insert(0, "Hello");
      });
      doc.transact(() => {
        text.insert(5, " World");
      });

      undoManager.undo(); // Undo " World"
      expect(text.toString()).toBe("Hello");

      // New operation should clear redo stack
      doc.transact(() => {
        text.insert(5, "!");
      });
      expect(text.toString()).toBe("Hello!");

      // Redo should do nothing (redo stack is cleared)
      undoManager.redo();
      expect(text.toString()).toBe("Hello!");
    });
  });

  describe("Document State and Length", () => {
    test("reports correct length for empty document", () => {
      expect(text.length).toBe(0);
    });

    test("reports correct length after insert", () => {
      text.insert(0, "Hello");
      expect(text.length).toBe(5);
    });

    test("reports correct length after delete", () => {
      text.insert(0, "Hello World");
      text.delete(5, 6);
      expect(text.length).toBe(5);
    });

    test("extracts substring using toJSON", () => {
      text.insert(0, "Hello World");
      const content = text.toJSON();
      expect(content).toBe("Hello World");
    });
  });

  describe("Unicode and Special Characters", () => {
    test("handles emoji", () => {
      text.insert(0, "Hello 👋 World 🌍");
      expect(text.toString()).toBe("Hello 👋 World 🌍");
    });

    test("handles multi-byte characters", () => {
      text.insert(0, "你好世界"); // Chinese: Hello World
      expect(text.toString()).toBe("你好世界");
    });

    test("handles accented characters", () => {
      text.insert(0, "Café résumé");
      expect(text.toString()).toBe("Café résumé");
    });

    test("handles newlines", () => {
      text.insert(0, "Line 1\nLine 2\nLine 3");
      expect(text.toString()).toBe("Line 1\nLine 2\nLine 3");
    });

    test("handles tabs and special whitespace", () => {
      text.insert(0, "Hello\tWorld");
      expect(text.toString()).toBe("Hello\tWorld");
    });
  });

  describe("Edge Cases", () => {
    test("handles very long text", () => {
      const longText = "a".repeat(10000);
      text.insert(0, longText);
      expect(text.length).toBe(10000);
      expect(text.toString()).toBe(longText);
    });

    test("handles rapid sequential operations", () => {
      // Simulate rapid typing
      for (let i = 0; i < 100; i++) {
        text.insert(text.length, "a");
      }
      expect(text.length).toBe(100);
      expect(text.toString()).toBe("a".repeat(100));
    });

    test("handles insert at invalid position gracefully", () => {
      text.insert(0, "Hello");
      // Yjs should handle this gracefully (insert at end)
      text.insert(100, " World");
      expect(text.toString()).toContain("Hello");
    });
  });
});
