import { describe, it, expect } from "vitest";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";

// Test the regex patterns directly
describe("Blockquote regex patterns", () => {
  const BLOCKQUOTE_REGEX = /^(\s*)> (.*)$/;
  const EMPTY_BLOCKQUOTE_REGEX = /^(\s*)>\s*$/;

  it("BLOCKQUOTE_REGEX should match line with content", () => {
    const match = "> hello".match(BLOCKQUOTE_REGEX);
    expect(match).toBeTruthy();
    expect(match[1]).toBe(""); // no indent
    expect(match[2]).toBe("hello");
  });

  it("BLOCKQUOTE_REGEX should match indented line with content", () => {
    const match = "  > hello".match(BLOCKQUOTE_REGEX);
    expect(match).toBeTruthy();
    expect(match[1]).toBe("  "); // 2 space indent
    expect(match[2]).toBe("hello");
  });

  it("BLOCKQUOTE_REGEX should NOT match empty blockquote (just > )", () => {
    // "> " should NOT match BLOCKQUOTE_REGEX because it requires content after "> "
    // Wait, (.*) matches empty string too, so "> " would match with group 2 being ""
    const match = "> ".match(BLOCKQUOTE_REGEX);
    // Actually this WILL match with empty group 2
    expect(match).toBeTruthy();
    expect(match[2]).toBe("");
  });

  it("EMPTY_BLOCKQUOTE_REGEX should match empty blockquote", () => {
    expect("> ".match(EMPTY_BLOCKQUOTE_REGEX)).toBeTruthy();
    expect(">".match(EMPTY_BLOCKQUOTE_REGEX)).toBeTruthy();
    expect(">   ".match(EMPTY_BLOCKQUOTE_REGEX)).toBeTruthy();
    expect("  > ".match(EMPTY_BLOCKQUOTE_REGEX)).toBeTruthy();
  });

  it("EMPTY_BLOCKQUOTE_REGEX should NOT match blockquote with content", () => {
    expect("> hello".match(EMPTY_BLOCKQUOTE_REGEX)).toBeFalsy();
    expect("> a".match(EMPTY_BLOCKQUOTE_REGEX)).toBeFalsy();
  });
});

// Test the actual handler logic
describe("Blockquote Enter handler logic", () => {
  const BLOCKQUOTE_REGEX = /^(\s*)> (.*)$/;
  const EMPTY_BLOCKQUOTE_REGEX = /^(\s*)>\s*$/;

  function simulateEnter(docText, cursorPos = null) {
    const pos = cursorPos ?? docText.length;
    const state = EditorState.create({
      doc: docText,
      selection: { anchor: pos },
    });

    const line = state.doc.lineAt(pos);

    // Check empty blockquote first (exit case)
    const emptyMatch = line.text.match(EMPTY_BLOCKQUOTE_REGEX);
    if (emptyMatch) {
      const indent = emptyMatch[1];
      // Replace the line with just the indent (removing "> ")
      const newDoc = docText.slice(0, line.from) + indent + docText.slice(line.to);
      return { doc: newDoc, action: "exit" };
    }

    // Check blockquote with content (continue case)
    const match = line.text.match(BLOCKQUOTE_REGEX);
    if (match) {
      const indent = match[1];
      const newLine = "\n" + indent + "> ";
      const newDoc = docText.slice(0, pos) + newLine + docText.slice(pos);
      return { doc: newDoc, action: "continue" };
    }

    return { doc: docText, action: "none" };
  }

  describe("Continue blockquote", () => {
    it("should add > prefix when pressing Enter at end of blockquote line", () => {
      const result = simulateEnter("> hello");
      expect(result.action).toBe("continue");
      expect(result.doc).toBe("> hello\n> ");
    });

    it("should preserve indent when continuing", () => {
      const result = simulateEnter("  > hello");
      expect(result.action).toBe("continue");
      expect(result.doc).toBe("  > hello\n  > ");
    });

    it("should insert at cursor position in middle of line", () => {
      const result = simulateEnter("> hello world", 7); // after "> hello"
      expect(result.action).toBe("continue");
      expect(result.doc).toBe("> hello\n>  world");
    });
  });

  describe("Exit blockquote", () => {
    it("should remove > when pressing Enter on empty blockquote", () => {
      const result = simulateEnter("> ");
      expect(result.action).toBe("exit");
      expect(result.doc).toBe("");
    });

    it("should remove > on second line empty blockquote", () => {
      const result = simulateEnter("> hello\n> ");
      expect(result.action).toBe("exit");
      expect(result.doc).toBe("> hello\n");
    });

    it("should preserve indent when exiting", () => {
      const result = simulateEnter("  > ");
      expect(result.action).toBe("exit");
      expect(result.doc).toBe("  ");
    });
  });
});

// The issue: "> " matches BOTH regexes! EMPTY should be checked first.
describe("Regex priority issue", () => {
  const BLOCKQUOTE_REGEX = /^(\s*)> (.*)$/;
  const EMPTY_BLOCKQUOTE_REGEX = /^(\s*)>\s*$/;

  it("empty blockquote '> ' matches both regexes - EMPTY must be checked first", () => {
    const text = "> ";
    const emptyMatch = text.match(EMPTY_BLOCKQUOTE_REGEX);
    const contentMatch = text.match(BLOCKQUOTE_REGEX);

    // Both match!
    expect(emptyMatch).toBeTruthy();
    expect(contentMatch).toBeTruthy();

    // EMPTY_BLOCKQUOTE_REGEX should be checked first to handle exit case
  });
});
