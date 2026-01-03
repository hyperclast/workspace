/**
 * Decoration User Interaction Tests
 *
 * Tests that decorations respond correctly to user interactions:
 * clicking, cursor movement, typing, undo/redo, etc.
 */

import { describe, test, expect, afterEach } from "vitest";
import { EditorState } from "@codemirror/state";
import { EditorView, keymap } from "@codemirror/view";
import { defaultKeymap, history, undo, redo } from "@codemirror/commands";
import { decorateFormatting, codeFenceField } from "../../decorateFormatting.js";
import { decorateLinks } from "../../decorateLinks.js";

function createEditor(content) {
  const state = EditorState.create({
    doc: content,
    extensions: [
      codeFenceField,
      decorateFormatting,
      decorateLinks,
      history(),
      keymap.of([...defaultKeymap]),
    ],
  });

  const parent = document.createElement("div");
  parent.style.width = "800px";
  parent.style.height = "600px";
  document.body.appendChild(parent);

  const view = new EditorView({ state, parent });
  return { view, parent };
}

function hasDecoration(view, className) {
  return view.contentDOM.querySelector(`.${className}`) !== null;
}

function countDecorations(view, className) {
  return view.contentDOM.querySelectorAll(`.${className}`).length;
}

function typeText(view, text, pos) {
  view.dispatch({
    changes: { from: pos, insert: text },
    selection: { anchor: pos + text.length },
  });
}

function deleteRange(view, from, to) {
  view.dispatch({
    changes: { from, to },
    selection: { anchor: from },
  });
}

function moveCursor(view, pos) {
  view.dispatch({ selection: { anchor: pos } });
}

describe("Decoration User Interactions", () => {
  let view, parent;

  afterEach(() => {
    if (view) view.destroy();
    if (parent) parent.remove();
    view = null;
    parent = null;
  });

  describe("Checkbox interactions", () => {
    test("checkbox widget appears when cursor elsewhere", () => {
      ({ view, parent } = createEditor("Line 1\n- [ ] Task item\nLine 3"));
      view.dispatch({ selection: { anchor: 0 } });
      const checkbox = view.contentDOM.querySelector('input[type="checkbox"]');
      expect(checkbox).not.toBeNull();
      expect(checkbox.type).toBe("checkbox");
    });

    test("checkbox state reflects document content", () => {
      ({ view, parent } = createEditor("Line 1\n- [x] Checked task\nLine 3"));
      view.dispatch({ selection: { anchor: 0 } });
      const checkbox = view.contentDOM.querySelector('input[type="checkbox"]');
      expect(checkbox.checked).toBe(true);
    });

    test("unchecked checkbox state", () => {
      ({ view, parent } = createEditor("Line 1\n- [ ] Unchecked task\nLine 3"));
      view.dispatch({ selection: { anchor: 0 } });
      const checkbox = view.contentDOM.querySelector('input[type="checkbox"]');
      expect(checkbox.checked).toBe(false);
    });
  });

  describe("Cursor movement and decoration visibility", () => {
    test("cursor entering link shows raw syntax", () => {
      ({ view, parent } = createEditor("Before [Link](url) after"));

      moveCursor(view, 0);
      let text = view.contentDOM.textContent;
      expect(text).toContain("Link");
      expect(text).not.toContain("](url)");

      moveCursor(view, 10);
      text = view.contentDOM.textContent;
      expect(text).toContain("[Link](url)");
    });

    test("cursor leaving link hides syntax", () => {
      ({ view, parent } = createEditor("Before [Link](url) after"));

      moveCursor(view, 10);
      moveCursor(view, 0);

      const text = view.contentDOM.textContent;
      expect(text).toContain("Link");
    });

    test("cursor on bold line shows asterisks", () => {
      ({ view, parent } = createEditor("Line 1\nText **bold** more\nLine 3"));

      moveCursor(view, 0);
      let text = view.contentDOM.textContent;
      expect(text).not.toContain("**bold**");

      const boldLine = view.state.doc.line(2);
      moveCursor(view, boldLine.from + 5);
      text = view.contentDOM.textContent;
      expect(text).toContain("**bold**");
    });

    test("cursor on heading line shows hash marks", () => {
      ({ view, parent } = createEditor("# Heading\nNext line"));

      const headingLine = view.state.doc.line(1);
      moveCursor(view, headingLine.from);

      const text = view.contentDOM.textContent;
      expect(text).toContain("#");
    });
  });

  describe("Typing and decoration updates", () => {
    test("typing inside bold keeps bold styling", () => {
      ({ view, parent } = createEditor("**bold**"));

      moveCursor(view, 4);
      typeText(view, "X", 4);

      expect(view.state.doc.toString()).toBe("**boXld**");
      expect(hasDecoration(view, "format-bold")).toBe(true);
    });

    test("typing to complete bold pattern creates decoration", () => {
      ({ view, parent } = createEditor("**incomplete"));
      expect(hasDecoration(view, "format-bold")).toBe(false);

      typeText(view, "**", view.state.doc.length);
      expect(hasDecoration(view, "format-bold")).toBe(true);
    });

    test("typing to break bold pattern removes decoration", () => {
      ({ view, parent } = createEditor("**bold**"));
      expect(hasDecoration(view, "format-bold")).toBe(true);

      deleteRange(view, 0, 2);
      expect(hasDecoration(view, "format-bold")).toBe(false);
    });

    test("typing new link creates decoration", () => {
      ({ view, parent } = createEditor("Click here"));
      expect(hasDecoration(view, "format-link")).toBe(false);

      view.dispatch({
        changes: { from: 6, to: 10, insert: "[here](url)" },
      });
      expect(hasDecoration(view, "format-link")).toBe(true);
    });

    test("completing checkbox syntax creates widget", () => {
      ({ view, parent } = createEditor("- ["));

      typeText(view, " ] Task", view.state.doc.length);

      expect(hasDecoration(view, "format-checkbox-item")).toBe(true);
    });
  });

  describe("Deletion and decoration updates", () => {
    test("deleting ** from bold removes styling", () => {
      ({ view, parent } = createEditor("**bold**"));

      deleteRange(view, 0, 2);
      expect(hasDecoration(view, "format-bold")).toBe(false);
    });

    test("deleting closing ** removes styling", () => {
      ({ view, parent } = createEditor("**bold**"));

      deleteRange(view, 6, 8);
      expect(hasDecoration(view, "format-bold")).toBe(false);
    });

    test("deleting heading hash removes heading styling", () => {
      ({ view, parent } = createEditor("## Heading"));

      deleteRange(view, 0, 3);
      expect(hasDecoration(view, "format-h2")).toBe(false);
    });

    test("deleting checkbox marker removes widget", () => {
      ({ view, parent } = createEditor("- [ ] Task"));

      deleteRange(view, 0, 6);
      expect(view.contentDOM.querySelector('input[type="checkbox"]')).toBeNull();
    });
  });

  describe("Undo/Redo with decorations", () => {
    test("undo restores previous decoration state", () => {
      ({ view, parent } = createEditor("**bold**"));
      expect(hasDecoration(view, "format-bold")).toBe(true);

      deleteRange(view, 0, 2);
      expect(hasDecoration(view, "format-bold")).toBe(false);

      undo(view);
      expect(hasDecoration(view, "format-bold")).toBe(true);
    });

    test("redo restores changed decoration state", () => {
      ({ view, parent } = createEditor("**bold**"));

      deleteRange(view, 0, 2);
      undo(view);
      redo(view);

      expect(hasDecoration(view, "format-bold")).toBe(false);
    });

    test("multiple undos through decoration changes", () => {
      ({ view, parent } = createEditor("text"));

      typeText(view, "**", 0);
      typeText(view, "**", view.state.doc.length);
      expect(hasDecoration(view, "format-bold")).toBe(true);

      undo(view);
      undo(view);
      expect(view.state.doc.toString()).toBe("text");
      expect(hasDecoration(view, "format-bold")).toBe(false);
    });
  });

  describe("Paste with decorations", () => {
    test("pasting bold text creates decoration", () => {
      ({ view, parent } = createEditor("Before  after"));

      view.dispatch({
        changes: { from: 7, insert: "**pasted**" },
      });

      expect(hasDecoration(view, "format-bold")).toBe(true);
    });

    test("pasting link creates decoration", () => {
      ({ view, parent } = createEditor("Text "));

      view.dispatch({
        changes: { from: 5, insert: "[link](https://example.com)" },
      });

      expect(hasDecoration(view, "format-link")).toBe(true);
    });

    test("pasting multiple formatted elements", () => {
      ({ view, parent } = createEditor(""));

      view.dispatch({
        changes: {
          from: 0,
          insert: "**bold** and `code` and [link](url)",
        },
      });

      expect(hasDecoration(view, "format-bold")).toBe(true);
      expect(hasDecoration(view, "format-inline-code")).toBe(true);
      expect(hasDecoration(view, "format-link")).toBe(true);
    });
  });

  describe("Selection and decorations", () => {
    test("selecting decorated text works", () => {
      ({ view, parent } = createEditor("**bold**"));

      view.dispatch({
        selection: { anchor: 2, head: 6 },
      });

      expect(view.state.selection.main.from).toBe(2);
      expect(view.state.selection.main.to).toBe(6);
    });

    test("replacing selected decorated text", () => {
      ({ view, parent } = createEditor("**bold**"));

      view.dispatch({
        changes: { from: 2, to: 6, insert: "new" },
        selection: { anchor: 5 },
      });

      expect(view.state.doc.toString()).toBe("**new**");
      expect(hasDecoration(view, "format-bold")).toBe(true);
    });

    test("deleting selection removes decoration if broken", () => {
      ({ view, parent } = createEditor("**bold**"));

      view.dispatch({
        changes: { from: 0, to: 4 },
      });

      expect(view.state.doc.toString()).toBe("ld**");
      expect(hasDecoration(view, "format-bold")).toBe(false);
    });
  });

  describe("Multi-line operations", () => {
    test("adding newline inside code block", () => {
      ({ view, parent } = createEditor("```\ncode\n```"));

      view.dispatch({
        changes: { from: 8, insert: "\nmore code" },
      });

      expect(hasDecoration(view, "format-code-block")).toBe(true);
    });

    test("deleting line break merges decorated lines", () => {
      ({ view, parent } = createEditor("**bold**\n**more**"));

      view.dispatch({
        changes: { from: 8, to: 9 },
      });

      expect(countDecorations(view, "format-bold")).toBeGreaterThanOrEqual(1);
    });
  });
});
