/**
 * Viewport Boundary Edge Case Tests
 *
 * Tests for decorations at viewport edges - the most critical edge cases
 * for viewport-based decoration processing.
 */

import { describe, test, expect, beforeEach, afterEach } from "vitest";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { decorateFormatting, codeFenceField } from "../../decorateFormatting.js";
import { decorateLinks } from "../../decorateLinks.js";
import { decorateEmails } from "../../decorateEmails.js";
import { generateDocumentWithPatternsAt } from "../helpers/large-fixtures.js";

function createEditor(content, height = 300) {
  const state = EditorState.create({
    doc: content,
    extensions: [
      codeFenceField,
      decorateFormatting,
      decorateLinks,
      decorateEmails,
      EditorView.lineWrapping,
    ],
  });

  const parent = document.createElement("div");
  parent.style.width = "800px";
  parent.style.height = `${height}px`;
  parent.style.overflow = "auto";
  document.body.appendChild(parent);

  const view = new EditorView({ state, parent });
  return { view, parent };
}

function scrollToLine(view, lineNumber) {
  const line = view.state.doc.line(lineNumber);
  view.dispatch({
    effects: EditorView.scrollIntoView(line.from, { y: "start" }),
  });
  return new Promise((resolve) => requestAnimationFrame(resolve));
}

function getViewportLines(view) {
  const { from, to } = view.viewport;
  const fromLine = view.state.doc.lineAt(from).number;
  const toLine = view.state.doc.lineAt(to).number;
  return { fromLine, toLine, from, to };
}

function hasDecoration(view, className) {
  return view.contentDOM.querySelector(`.${className}`) !== null;
}

function countDecorations(view, className) {
  return view.contentDOM.querySelectorAll(`.${className}`).length;
}

describe("Viewport Boundary Edge Cases", () => {
  let view, parent;

  afterEach(() => {
    if (view) {
      view.destroy();
      view = null;
    }
    if (parent) {
      parent.remove();
      parent = null;
    }
  });

  describe("Decorations at viewport edges", () => {
    test("link at first visible line is fully decorated", async () => {
      const content = generateDocumentWithPatternsAt({
        totalLines: 500,
        patterns: [{ line: 100, content: "[Link Text](https://example.com) at viewport start" }],
      });

      ({ view, parent } = createEditor(content, 200));
      await scrollToLine(view, 100);

      const { fromLine } = getViewportLines(view);
      expect(fromLine).toBeLessThanOrEqual(101);
      expect(hasDecoration(view, "format-link")).toBe(true);
    });

    test("link at last visible line is fully decorated", async () => {
      const content = generateDocumentWithPatternsAt({
        totalLines: 500,
        patterns: [{ line: 102, content: "[Link Text](https://example.com) at viewport end" }],
      });

      ({ view, parent } = createEditor(content, 200));
      await scrollToLine(view, 100);

      expect(hasDecoration(view, "format-link")).toBe(true);
    });

    test("bold text spanning lines near viewport boundary", async () => {
      const content = generateDocumentWithPatternsAt({
        totalLines: 500,
        patterns: [
          { line: 99, content: "Text before viewport" },
          { line: 100, content: "**bold text here** at start" },
          { line: 101, content: "And more **bold** after" },
        ],
      });

      ({ view, parent } = createEditor(content, 200));
      await scrollToLine(view, 100);

      expect(hasDecoration(view, "format-bold")).toBe(true);
      expect(countDecorations(view, "format-bold")).toBeGreaterThanOrEqual(1);
    });

    test("heading at viewport start shows correctly", async () => {
      const content = generateDocumentWithPatternsAt({
        totalLines: 500,
        patterns: [{ line: 100, content: "## Heading at viewport boundary" }],
      });

      ({ view, parent } = createEditor(content, 200));
      await scrollToLine(view, 100);

      expect(hasDecoration(view, "format-h2")).toBe(true);
    });

    test("checkbox at viewport edge renders widget", async () => {
      const content = generateDocumentWithPatternsAt({
        totalLines: 500,
        patterns: [{ line: 100, content: "- [ ] Task at viewport boundary" }],
      });

      ({ view, parent } = createEditor(content, 200));
      await scrollToLine(view, 100);

      expect(hasDecoration(view, "format-checkbox-item")).toBe(true);
    });
  });

  describe("Multi-line patterns crossing viewport", () => {
    test("code block starting above viewport shows content correctly", async () => {
      const content = generateDocumentWithPatternsAt({
        totalLines: 500,
        patterns: [
          { line: 95, content: "```javascript" },
          { line: 96, content: "const above = true;" },
          { line: 97, content: "const alsoAbove = true;" },
          { line: 98, content: "const nearEdge = true;" },
          { line: 99, content: "const atEdge = true;" },
          { line: 100, content: "const visible = true;" },
          { line: 101, content: "const alsoVisible = true;" },
          { line: 102, content: "```" },
        ],
      });

      ({ view, parent } = createEditor(content, 200));
      await scrollToLine(view, 100);

      expect(hasDecoration(view, "format-code-block")).toBe(true);
    });

    test("code block ending in viewport shows correctly", async () => {
      const content = generateDocumentWithPatternsAt({
        totalLines: 500,
        patterns: [
          { line: 100, content: "```" },
          { line: 101, content: "code line 1" },
          { line: 102, content: "code line 2" },
          { line: 103, content: "```" },
        ],
      });

      ({ view, parent } = createEditor(content, 200));
      await scrollToLine(view, 100);

      expect(hasDecoration(view, "format-code-block")).toBe(true);
    });

    test("blockquote continuing from above viewport", async () => {
      const content = generateDocumentWithPatternsAt({
        totalLines: 500,
        patterns: [
          { line: 95, content: "> Quote starting above" },
          { line: 96, content: "> Continuing quote" },
          { line: 97, content: "> More quote" },
          { line: 98, content: "> Still quoting" },
          { line: 99, content: "> Almost there" },
          { line: 100, content: "> Now in viewport" },
          { line: 101, content: "> End of quote" },
        ],
      });

      ({ view, parent } = createEditor(content, 200));
      await scrollToLine(view, 100);

      expect(hasDecoration(view, "format-blockquote")).toBe(true);
    });

    test("list item with continuation at boundary", async () => {
      const content = generateDocumentWithPatternsAt({
        totalLines: 500,
        patterns: [
          { line: 99, content: "- First item above viewport" },
          { line: 100, content: "- Item at viewport start" },
          { line: 101, content: "  - Nested item" },
          { line: 102, content: "    - Deep nested" },
        ],
      });

      ({ view, parent } = createEditor(content, 200));
      await scrollToLine(view, 100);

      expect(hasDecoration(view, "format-bullet-item")).toBe(true);
    });
  });

  describe("Scrolling behavior", () => {
    test("scrolling down reveals decorations without delay", async () => {
      const content = generateDocumentWithPatternsAt({
        totalLines: 1000,
        patterns: [
          { line: 200, content: "**Bold at line 200**" },
          { line: 400, content: "[Link at 400](https://example.com)" },
          { line: 600, content: "## Heading at 600" },
          { line: 800, content: "- [ ] Task at 800" },
        ],
      });

      ({ view, parent } = createEditor(content, 200));

      await scrollToLine(view, 200);
      expect(hasDecoration(view, "format-bold")).toBe(true);

      await scrollToLine(view, 400);
      expect(hasDecoration(view, "format-link")).toBe(true);

      await scrollToLine(view, 600);
      expect(hasDecoration(view, "format-h2")).toBe(true);

      await scrollToLine(view, 800);
      expect(hasDecoration(view, "format-checkbox-item")).toBe(true);
    });

    test("scrolling up into decorated content shows decorations", async () => {
      const content = generateDocumentWithPatternsAt({
        totalLines: 500,
        patterns: [
          { line: 50, content: "**Bold early in doc**" },
          { line: 100, content: "[Link in middle](url)" },
        ],
      });

      ({ view, parent } = createEditor(content, 200));

      await scrollToLine(view, 200);
      await scrollToLine(view, 100);
      expect(hasDecoration(view, "format-link")).toBe(true);

      await scrollToLine(view, 50);
      expect(hasDecoration(view, "format-bold")).toBe(true);
    });

    test("rapid scrolling maintains decoration integrity", async () => {
      const content = generateDocumentWithPatternsAt({
        totalLines: 1000,
        patterns: Array.from({ length: 20 }, (_, i) => ({
          line: i * 50,
          content: `**Bold at ${i * 50}**`,
        })),
      });

      ({ view, parent } = createEditor(content, 200));

      for (let i = 0; i < 5; i++) {
        await scrollToLine(view, 100 + i * 100);
        await new Promise((r) => setTimeout(r, 10));
      }

      expect(hasDecoration(view, "format-bold")).toBe(true);
    });
  });

  describe("Cursor and selection at boundaries", () => {
    test("cursor on link at viewport edge shows raw syntax", async () => {
      const content = generateDocumentWithPatternsAt({
        totalLines: 500,
        patterns: [{ line: 100, content: "[Link Text](https://example.com)" }],
      });

      ({ view, parent } = createEditor(content, 200));
      await scrollToLine(view, 100);

      const line = view.state.doc.line(101);
      view.dispatch({ selection: { anchor: line.from + 5 } });

      const text = view.contentDOM.textContent;
      expect(text).toContain("[Link Text]");
    });

    test("selection spanning multiple decorated lines", async () => {
      const content = generateDocumentWithPatternsAt({
        totalLines: 500,
        patterns: [
          { line: 100, content: "**Bold line 1**" },
          { line: 101, content: "Normal line" },
          { line: 102, content: "**Bold line 2**" },
        ],
      });

      ({ view, parent } = createEditor(content, 200));
      await scrollToLine(view, 100);

      const line100 = view.state.doc.line(101);
      const line102 = view.state.doc.line(103);
      view.dispatch({
        selection: { anchor: line100.from, head: line102.to },
      });

      expect(countDecorations(view, "format-bold")).toBeGreaterThanOrEqual(1);
    });

    test("cursor movement across viewport boundary", async () => {
      const content = generateDocumentWithPatternsAt({
        totalLines: 500,
        patterns: [
          { line: 50, content: "## Heading above" },
          { line: 150, content: "## Heading below" },
        ],
      });

      ({ view, parent } = createEditor(content, 200));

      await scrollToLine(view, 100);
      const { toLine } = getViewportLines(view);

      const line = view.state.doc.line(toLine + 5);
      view.dispatch({
        selection: { anchor: line.from },
        scrollIntoView: true,
      });

      await new Promise((r) => requestAnimationFrame(r));
      expect(view.state.selection.main.head).toBe(line.from);
    });
  });

  describe("Edge cases at document boundaries", () => {
    test("decoration at document start", () => {
      const content = "**Bold at very start**\n" + "Normal line\n".repeat(100);
      ({ view, parent } = createEditor(content, 200));

      expect(hasDecoration(view, "format-bold")).toBe(true);
    });

    test("decoration at document end", async () => {
      const content = "Normal line\n".repeat(100) + "**Bold at very end**";
      ({ view, parent } = createEditor(content, 200));

      await scrollToLine(view, 100);
      expect(hasDecoration(view, "format-bold")).toBe(true);
    });

    test("single line document with decoration", () => {
      ({ view, parent } = createEditor("**Only one bold line**", 200));
      expect(hasDecoration(view, "format-bold")).toBe(true);
    });

    test("empty document", () => {
      ({ view, parent } = createEditor("", 200));
      expect(view.state.doc.length).toBe(0);
    });
  });
});
