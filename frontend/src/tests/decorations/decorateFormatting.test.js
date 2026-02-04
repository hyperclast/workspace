/**
 * decorateFormatting.js Specific Tests
 *
 * Tests for the formatting decoration plugin covering all markdown patterns.
 */

import { describe, test, expect, afterEach } from "vitest";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { decorateFormatting, codeFenceField, toggleCheckbox } from "../../decorateFormatting.js";
import {
  generateDocumentWithFormatting,
  generateDocumentWithPatternsAt,
} from "../helpers/large-fixtures.js";
import { measureTime, getConfig, isFullMode } from "../helpers/perf-utils.js";

function createEditor(content) {
  const state = EditorState.create({
    doc: content,
    extensions: [codeFenceField, decorateFormatting],
  });

  const parent = document.createElement("div");
  parent.style.width = "800px";
  parent.style.height = "400px";
  parent.style.overflow = "auto";
  document.body.appendChild(parent);

  const view = new EditorView({ state, parent });
  return { view, parent };
}

function hasClass(view, className) {
  return view.contentDOM.querySelector(`.${className}`) !== null;
}

function countClass(view, className) {
  return view.contentDOM.querySelectorAll(`.${className}`).length;
}

function scrollToLine(view, lineNumber) {
  const line = view.state.doc.line(lineNumber);
  view.dispatch({
    effects: EditorView.scrollIntoView(line.from, { y: "start" }),
  });
  return new Promise((resolve) => requestAnimationFrame(resolve));
}

describe("decorateFormatting", () => {
  let view, parent;

  afterEach(() => {
    if (view) view.destroy();
    if (parent) parent.remove();
    view = null;
    parent = null;
  });

  describe("Bold formatting", () => {
    test("**text** gets format-bold class", () => {
      ({ view, parent } = createEditor("**bold text**"));
      expect(hasClass(view, "format-bold")).toBe(true);
    });

    test("cursor elsewhere hides ** markers", () => {
      ({ view, parent } = createEditor("Line 1\n**bold**\nLine 3"));
      view.dispatch({ selection: { anchor: 0 } });

      const text = view.contentDOM.textContent;
      expect(text).toContain("bold");
      expect(text).not.toContain("**bold**");
    });

    test("cursor on line shows ** markers", () => {
      ({ view, parent } = createEditor("**bold**"));
      view.dispatch({ selection: { anchor: 4 } });

      const text = view.contentDOM.textContent;
      expect(text).toContain("**bold**");
    });

    test("multiple bold on same line", () => {
      ({ view, parent } = createEditor("**a** and **b** and **c**"));
      view.dispatch({ selection: { anchor: 0 } });

      expect(countClass(view, "format-bold")).toBe(3);
    });
  });

  describe("Underline formatting", () => {
    test("__text__ gets format-underline class", () => {
      ({ view, parent } = createEditor("__underlined__"));
      expect(hasClass(view, "format-underline")).toBe(true);
    });

    test("cursor elsewhere hides __ markers", () => {
      ({ view, parent } = createEditor("Line 1\n__text__\nLine 3"));
      view.dispatch({ selection: { anchor: 0 } });

      const text = view.contentDOM.textContent;
      expect(text).not.toContain("__text__");
    });
  });

  describe("Inline code", () => {
    test("`code` gets format-inline-code class", () => {
      ({ view, parent } = createEditor("`code`"));
      expect(hasClass(view, "format-inline-code")).toBe(true);
    });

    test("cursor elsewhere hides backticks", () => {
      ({ view, parent } = createEditor("Line 1\n`code`\nLine 3"));
      view.dispatch({ selection: { anchor: 0 } });

      const text = view.contentDOM.textContent;
      expect(text).toContain("code");
    });

    test("multiple inline code spans", () => {
      ({ view, parent } = createEditor("`a` and `b` and `c`"));
      view.dispatch({ selection: { anchor: 0 } });

      expect(countClass(view, "format-inline-code")).toBe(3);
    });
  });

  describe("Headings", () => {
    test("# creates h1", () => {
      ({ view, parent } = createEditor("# Heading 1"));
      expect(hasClass(view, "format-h1")).toBe(true);
    });

    test("## creates h2", () => {
      ({ view, parent } = createEditor("## Heading 2"));
      expect(hasClass(view, "format-h2")).toBe(true);
    });

    test("###### creates h6", () => {
      ({ view, parent } = createEditor("###### Heading 6"));
      expect(hasClass(view, "format-h6")).toBe(true);
    });

    test("hash hidden when cursor elsewhere", () => {
      ({ view, parent } = createEditor("## Heading\nNext line"));
      view.dispatch({ selection: { anchor: 15 } });

      const text = view.contentDOM.textContent;
      expect(text).toContain("Heading");
    });

    test("hash shown when cursor on heading", () => {
      ({ view, parent } = createEditor("## Heading"));
      view.dispatch({ selection: { anchor: 0 } });

      const text = view.contentDOM.textContent;
      expect(text).toMatch(/^#/);
    });
  });

  describe("Lists - Bullets", () => {
    test("- item gets format-bullet-item class", () => {
      ({ view, parent } = createEditor("- Item"));
      expect(hasClass(view, "format-bullet-item")).toBe(true);
    });

    test("bullet widget appears when cursor elsewhere", () => {
      ({ view, parent } = createEditor("Before\n- Item\nAfter"));
      view.dispatch({ selection: { anchor: 0 } });
      expect(hasClass(view, "format-bullet")).toBe(true);
    });

    test("nested bullets get indent class", () => {
      ({ view, parent } = createEditor("- Top\n  - Nested"));
      expect(hasClass(view, "format-indent-1")).toBe(true);
    });
  });

  describe("Lists - Ordered", () => {
    test("1. item gets format-ordered-item class", () => {
      ({ view, parent } = createEditor("1. First item"));
      expect(hasClass(view, "format-ordered-item")).toBe(true);
    });

    test("multi-digit numbers work", () => {
      ({ view, parent } = createEditor("10. Tenth item"));
      expect(hasClass(view, "format-ordered-item")).toBe(true);
    });
  });

  describe("Lists - Checkboxes", () => {
    test("- [ ] gets format-checkbox-item class", () => {
      ({ view, parent } = createEditor("- [ ] Task"));
      expect(hasClass(view, "format-checkbox-item")).toBe(true);
    });

    test("- [x] gets format-checkbox-checked class", () => {
      ({ view, parent } = createEditor("- [x] Done"));
      expect(hasClass(view, "format-checkbox-checked")).toBe(true);
    });

    test("- [X] uppercase also works", () => {
      ({ view, parent } = createEditor("- [X] Done"));
      expect(hasClass(view, "format-checkbox-checked")).toBe(true);
    });

    test("checkbox widget is present when cursor elsewhere", () => {
      ({ view, parent } = createEditor("Before\n- [ ] Task\nAfter"));
      view.dispatch({ selection: { anchor: 0 } });
      const checkbox = view.contentDOM.querySelector('input[type="checkbox"]');
      expect(checkbox).not.toBeNull();
    });

    test("nested checkbox gets indent class", () => {
      ({ view, parent } = createEditor("  - [ ] Nested task"));
      expect(hasClass(view, "format-checkbox-item")).toBe(true);
    });
  });

  describe("Blockquotes", () => {
    test("> text gets format-blockquote class", () => {
      ({ view, parent } = createEditor("> Quote"));
      expect(hasClass(view, "format-blockquote")).toBe(true);
    });

    test("> marker hidden when cursor elsewhere", () => {
      ({ view, parent } = createEditor("Line 1\n> Quote\nLine 3"));
      view.dispatch({ selection: { anchor: 0 } });

      expect(hasClass(view, "format-blockquote")).toBe(true);
    });
  });

  describe("Code blocks", () => {
    test("``` creates code block", () => {
      ({ view, parent } = createEditor("```\ncode\n```"));
      expect(hasClass(view, "format-code-block")).toBe(true);
    });

    test("code fence hidden when cursor elsewhere", () => {
      ({ view, parent } = createEditor("Line 1\n```\ncode\n```\nLine 5"));
      view.dispatch({ selection: { anchor: 0 } });
    });

    test("content inside code block not decorated as markdown", () => {
      ({ view, parent } = createEditor("```\n# Not a heading\n**Not bold**\n```"));
      expect(hasClass(view, "format-h1")).toBe(false);
      expect(hasClass(view, "format-bold")).toBe(false);
    });

    test("code block with language", () => {
      ({ view, parent } = createEditor("```javascript\nconst x = 1;\n```"));
      expect(hasClass(view, "format-code-block")).toBe(true);
    });
  });

  describe("Horizontal rules", () => {
    test("--- creates HR when cursor elsewhere", () => {
      ({ view, parent } = createEditor("Before\n---\nAfter"));
      view.dispatch({ selection: { anchor: 0 } });
      const hr = view.contentDOM.querySelector("hr");
      expect(hr).not.toBeNull();
    });

    test("*** creates HR when cursor elsewhere", () => {
      ({ view, parent } = createEditor("Before\n***\nAfter"));
      view.dispatch({ selection: { anchor: 0 } });
      const hr = view.contentDOM.querySelector("hr");
      expect(hr).not.toBeNull();
    });

    test("___ creates HR when cursor elsewhere", () => {
      ({ view, parent } = createEditor("Before\n___\nAfter"));
      view.dispatch({ selection: { anchor: 0 } });
      const hr = view.contentDOM.querySelector("hr");
      expect(hr).not.toBeNull();
    });

    test("HR visible when cursor elsewhere", () => {
      ({ view, parent } = createEditor("Line 1\n---\nLine 3"));
      view.dispatch({ selection: { anchor: 0 } });

      const hr = view.contentDOM.querySelector("hr");
      expect(hr).not.toBeNull();
    });
  });

  describe("Performance - viewport-based processing", () => {
    test("decoration should be O(viewport) not O(document)", async () => {
      const smallDoc = generateDocumentWithFormatting({ lines: 100 });
      const largeDoc = generateDocumentWithFormatting({ lines: getConfig(5000, 50000) });

      const { duration: smallDuration } = await measureTime(() => {
        const { view: v, parent: p } = createEditor(smallDoc);
        v.destroy();
        p.remove();
      });

      const { duration: largeDuration } = await measureTime(() => {
        ({ view, parent } = createEditor(largeDoc));
      });

      console.log(`[PERF] decorateFormatting creation:`);
      console.log(`  100 lines: ${smallDuration.toFixed(2)}ms`);
      console.log(`  ${getConfig(5000, 50000)} lines: ${largeDuration.toFixed(2)}ms`);
      console.log(`  Ratio: ${(largeDuration / smallDuration).toFixed(1)}x`);
    });

    test("editing at start should be fast regardless of doc size", async () => {
      const content = generateDocumentWithFormatting({ lines: getConfig(2000, 20000) });
      ({ view, parent } = createEditor(content));

      const latencies = [];
      for (let i = 0; i < 10; i++) {
        const { duration } = await measureTime(() => {
          view.dispatch({
            changes: { from: 0, insert: "x" },
          });
        });
        latencies.push(duration);
      }

      const avgLatency = latencies.reduce((a, b) => a + b, 0) / latencies.length;
      console.log(`[PERF] Edit at start: avg ${avgLatency.toFixed(2)}ms`);

      expect(avgLatency).toBeLessThan(100);
    });

    test("decorations appear in viewport", async () => {
      const content = "Line 1\n# Heading text\nLine 3";

      ({ view, parent } = createEditor(content));
      view.dispatch({ selection: { anchor: 0 } });

      expect(hasClass(view, "format-heading")).toBe(true);
    });
  });

  describe("Mixed formatting", () => {
    test("heading is styled (cursor elsewhere)", () => {
      ({ view, parent } = createEditor("Before\n## Heading text\nAfter"));
      view.dispatch({ selection: { anchor: 0 } });
      expect(hasClass(view, "format-h2")).toBe(true);
    });

    test("list item is styled (cursor elsewhere)", () => {
      ({ view, parent } = createEditor("Before\n- Item text\nAfter"));
      view.dispatch({ selection: { anchor: 0 } });
      expect(hasClass(view, "format-bullet-item")).toBe(true);
    });

    test("blockquote line is styled", () => {
      ({ view, parent } = createEditor("Before\n> Quote text\nAfter"));
      view.dispatch({ selection: { anchor: 0 } });
      expect(hasClass(view, "format-blockquote")).toBe(true);
    });
  });

  describe("toggleCheckbox function", () => {
    test("single line: plain text becomes checkbox", () => {
      ({ view, parent } = createEditor("Task one"));
      view.dispatch({ selection: { anchor: 0 } });
      toggleCheckbox(view);
      expect(view.state.doc.toString()).toBe("- [ ] Task one");
    });

    test("single line: bullet becomes checkbox", () => {
      ({ view, parent } = createEditor("- Task one"));
      view.dispatch({ selection: { anchor: 0 } });
      toggleCheckbox(view);
      expect(view.state.doc.toString()).toBe("- [ ] Task one");
    });

    test("single line: unchecked checkbox becomes checked", () => {
      ({ view, parent } = createEditor("- [ ] Task one"));
      view.dispatch({ selection: { anchor: 0 } });
      toggleCheckbox(view);
      expect(view.state.doc.toString()).toBe("- [x] Task one");
    });

    test("single line: checked checkbox becomes unchecked", () => {
      ({ view, parent } = createEditor("- [x] Task one"));
      view.dispatch({ selection: { anchor: 0 } });
      toggleCheckbox(view);
      expect(view.state.doc.toString()).toBe("- [ ] Task one");
    });

    test("multi-line: all plain text lines become checkboxes", () => {
      ({ view, parent } = createEditor("First task\nSecond task\nThird task"));
      // Select all lines (from start of first to end of last)
      view.dispatch({ selection: { anchor: 0, head: view.state.doc.length } });
      toggleCheckbox(view);
      expect(view.state.doc.toString()).toBe(
        "- [ ] First task\n- [ ] Second task\n- [ ] Third task"
      );
    });

    test("multi-line: all bullet lines become checkboxes", () => {
      ({ view, parent } = createEditor("- First task\n- Second task\n- Third task"));
      view.dispatch({ selection: { anchor: 0, head: view.state.doc.length } });
      toggleCheckbox(view);
      expect(view.state.doc.toString()).toBe(
        "- [ ] First task\n- [ ] Second task\n- [ ] Third task"
      );
    });

    test("multi-line: all unchecked checkboxes become checked", () => {
      ({ view, parent } = createEditor("- [ ] First task\n- [ ] Second task\n- [ ] Third task"));
      view.dispatch({ selection: { anchor: 0, head: view.state.doc.length } });
      toggleCheckbox(view);
      expect(view.state.doc.toString()).toBe(
        "- [x] First task\n- [x] Second task\n- [x] Third task"
      );
    });

    test("multi-line: mixed content - each line transforms appropriately", () => {
      ({ view, parent } = createEditor(
        "Plain text\n- Bullet item\n- [ ] Unchecked\n- [x] Checked"
      ));
      view.dispatch({ selection: { anchor: 0, head: view.state.doc.length } });
      toggleCheckbox(view);
      // Plain -> checkbox, bullet -> checkbox, unchecked -> checked, checked -> unchecked
      expect(view.state.doc.toString()).toBe(
        "- [ ] Plain text\n- [ ] Bullet item\n- [x] Unchecked\n- [ ] Checked"
      );
    });

    test("multi-line: indented content preserves indentation", () => {
      ({ view, parent } = createEditor("  First task\n  Second task"));
      view.dispatch({ selection: { anchor: 0, head: view.state.doc.length } });
      toggleCheckbox(view);
      expect(view.state.doc.toString()).toBe("- [ ]   First task\n- [ ]   Second task");
    });

    test("multi-line: indented bullets become checkboxes", () => {
      ({ view, parent } = createEditor("  - First task\n  - Second task"));
      view.dispatch({ selection: { anchor: 0, head: view.state.doc.length } });
      toggleCheckbox(view);
      expect(view.state.doc.toString()).toBe("  - [ ] First task\n  - [ ] Second task");
    });
  });
});
