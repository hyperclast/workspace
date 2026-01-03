/**
 * CodeFence StateField Tests
 *
 * Tests for the code fence tracking StateField that enables O(1) lookup
 * for whether a line is inside a code block.
 */

import { describe, test, expect, afterEach } from "vitest";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { codeFenceField } from "../../decorateFormatting.js";
import { CODE_FENCE_SCAN_LIMIT_LINES } from "../../config/performance.js";

function createEditorWithFences(content) {
  const state = EditorState.create({
    doc: content,
    extensions: [codeFenceField],
  });
  return state;
}

describe("codeFenceField", () => {
  describe("basic functionality", () => {
    test("detects single code block", () => {
      const doc = `Normal text

\`\`\`javascript
const x = 1;
\`\`\`

More text`;

      const state = createEditorWithFences(doc);
      const fences = state.field(codeFenceField);

      expect(fences).toHaveLength(1);
      expect(fences[0].start).toBe(3);
      expect(fences[0].end).toBe(5);
    });

    test("detects multiple code blocks", () => {
      const doc = `# Title

\`\`\`python
def foo():
    pass
\`\`\`

Some text

\`\`\`bash
echo "hello"
\`\`\``;

      const state = createEditorWithFences(doc);
      const fences = state.field(codeFenceField);

      expect(fences).toHaveLength(2);
      expect(fences[0].start).toBe(3);
      expect(fences[0].end).toBe(6);
      expect(fences[1].start).toBe(10);
      expect(fences[1].end).toBe(12);
    });

    test("handles empty document", () => {
      const state = createEditorWithFences("");
      const fences = state.field(codeFenceField);

      expect(fences).toHaveLength(0);
    });

    test("handles document with no code blocks", () => {
      const doc = `# Title

Regular text here.

## Another section

More regular text.`;

      const state = createEditorWithFences(doc);
      const fences = state.field(codeFenceField);

      expect(fences).toHaveLength(0);
    });

    test("handles unclosed code block at end of document", () => {
      const doc = `# Title

\`\`\`python
def foo():
    pass`;

      const state = createEditorWithFences(doc);
      const fences = state.field(codeFenceField);

      expect(fences).toHaveLength(1);
      expect(fences[0].start).toBe(3);
      expect(fences[0].end).toBe(state.doc.lines);
    });
  });

  describe("StateField updates", () => {
    test("updates when content is added", () => {
      const initialDoc = `# Title

\`\`\`
code
\`\`\``;

      let state = createEditorWithFences(initialDoc);
      let fences = state.field(codeFenceField);
      expect(fences).toHaveLength(1);

      state = state.update({
        changes: {
          from: state.doc.length,
          insert: `

\`\`\`
more code
\`\`\``,
        },
      }).state;

      fences = state.field(codeFenceField);
      expect(fences).toHaveLength(2);
    });

    test("updates when code block is removed", () => {
      const doc = `\`\`\`
code
\`\`\``;

      let state = createEditorWithFences(doc);
      let fences = state.field(codeFenceField);
      expect(fences).toHaveLength(1);

      state = state.update({
        changes: { from: 0, to: state.doc.length, insert: "No code blocks" },
      }).state;

      fences = state.field(codeFenceField);
      expect(fences).toHaveLength(0);
    });

    test("preserves state when selection changes only", () => {
      const doc = `\`\`\`
code
\`\`\``;

      let state = createEditorWithFences(doc);
      const fences1 = state.field(codeFenceField);

      state = state.update({
        selection: { anchor: 5 },
      }).state;

      const fences2 = state.field(codeFenceField);

      expect(fences1).toBe(fences2);
    });
  });

  describe("threshold behavior", () => {
    function generateLargeDoc(lines, includeCodeBlock = true) {
      const result = [];
      if (includeCodeBlock) {
        result.push("```");
        result.push("code");
        result.push("```");
      }
      for (let i = result.length; i < lines; i++) {
        result.push(`Line ${i}`);
      }
      return result.join("\n");
    }

    test(`returns code fences at ${CODE_FENCE_SCAN_LIMIT_LINES} lines (at threshold)`, () => {
      const doc = generateLargeDoc(CODE_FENCE_SCAN_LIMIT_LINES);
      const state = createEditorWithFences(doc);

      expect(state.doc.lines).toBe(CODE_FENCE_SCAN_LIMIT_LINES);

      const fences = state.field(codeFenceField);
      expect(fences).toHaveLength(1);
    });

    test(`returns empty array at ${CODE_FENCE_SCAN_LIMIT_LINES + 1} lines (over threshold)`, () => {
      const doc = generateLargeDoc(CODE_FENCE_SCAN_LIMIT_LINES + 1);
      const state = createEditorWithFences(doc);

      expect(state.doc.lines).toBe(CODE_FENCE_SCAN_LIMIT_LINES + 1);

      const fences = state.field(codeFenceField);
      expect(fences).toHaveLength(0);
    });

    test("gracefully degrades when document grows past threshold", () => {
      let state = createEditorWithFences(`\`\`\`
code
\`\`\``);

      let fences = state.field(codeFenceField);
      expect(fences).toHaveLength(1);

      const additionalLines = [];
      for (let i = 0; i < CODE_FENCE_SCAN_LIMIT_LINES; i++) {
        additionalLines.push(`Line ${i}`);
      }

      state = state.update({
        changes: { from: state.doc.length, insert: "\n" + additionalLines.join("\n") },
      }).state;

      fences = state.field(codeFenceField);
      expect(fences).toHaveLength(0);
    });
  });

  describe("edge cases", () => {
    test("handles code fence without language", () => {
      const doc = `\`\`\`
plain code
\`\`\``;

      const state = createEditorWithFences(doc);
      const fences = state.field(codeFenceField);

      expect(fences).toHaveLength(1);
    });

    test("handles nested backticks (but not nested code blocks)", () => {
      const doc = `\`\`\`
code with \` backticks \` inside
\`\`\``;

      const state = createEditorWithFences(doc);
      const fences = state.field(codeFenceField);

      expect(fences).toHaveLength(1);
      expect(fences[0].start).toBe(1);
      expect(fences[0].end).toBe(3);
    });

    test("handles adjacent code blocks", () => {
      const doc = `\`\`\`
first
\`\`\`
\`\`\`
second
\`\`\``;

      const state = createEditorWithFences(doc);
      const fences = state.field(codeFenceField);

      expect(fences).toHaveLength(2);
    });

    test("handles code block at start of document", () => {
      const doc = `\`\`\`
code
\`\`\`
text after`;

      const state = createEditorWithFences(doc);
      const fences = state.field(codeFenceField);

      expect(fences).toHaveLength(1);
      expect(fences[0].start).toBe(1);
    });

    test("handles code block at end of document", () => {
      const doc = `text before
\`\`\`
code
\`\`\``;

      const state = createEditorWithFences(doc);
      const fences = state.field(codeFenceField);

      expect(fences).toHaveLength(1);
      expect(fences[0].end).toBe(4);
    });
  });
});
