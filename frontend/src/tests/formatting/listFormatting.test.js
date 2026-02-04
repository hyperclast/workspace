/**
 * List Formatting Tests
 *
 * Comprehensive tests for multi-line list toggling operations including:
 * - Bullet lists (ul)
 * - Ordered lists (ol)
 * - Checkboxes
 * - Mixed content scenarios
 * - Multiple toggle cycles
 * - Undo/redo functionality
 */

import { describe, test, expect, afterEach } from "vitest";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { history, undo, redo } from "@codemirror/commands";
import {
  toggleLinePrefix,
  toggleOrderedList,
  toggleBulletList,
  toggleBlockquote,
} from "../../lib/listFormatting.js";
import { toggleCheckbox } from "../../decorateFormatting.js";

function createEditor(content) {
  const state = EditorState.create({
    doc: content,
    extensions: [history()],
  });

  const parent = document.createElement("div");
  parent.style.width = "800px";
  parent.style.height = "400px";
  parent.style.overflow = "auto";
  document.body.appendChild(parent);

  const view = new EditorView({ state, parent });
  return { view, parent };
}

function selectAll(view) {
  view.dispatch({ selection: { anchor: 0, head: view.state.doc.length } });
}

function selectLines(view, fromLine, toLine) {
  const from = view.state.doc.line(fromLine).from;
  const to = view.state.doc.line(toLine).to;
  view.dispatch({ selection: { anchor: from, head: to } });
}

describe("listFormatting", () => {
  let view, parent;

  afterEach(() => {
    if (view) view.destroy();
    if (parent) parent.remove();
    view = null;
    parent = null;
  });

  describe("toggleBulletList (ul)", () => {
    test("single line: plain text becomes bullet", () => {
      ({ view, parent } = createEditor("Item one"));
      view.dispatch({ selection: { anchor: 0 } });
      toggleBulletList(view);
      expect(view.state.doc.toString()).toBe("- Item one");
    });

    test("single line: bullet is removed", () => {
      ({ view, parent } = createEditor("- Item one"));
      view.dispatch({ selection: { anchor: 0 } });
      toggleBulletList(view);
      expect(view.state.doc.toString()).toBe("Item one");
    });

    test("multi-line: all plain text lines become bullets", () => {
      ({ view, parent } = createEditor("First item\nSecond item\nThird item"));
      selectAll(view);
      toggleBulletList(view);
      expect(view.state.doc.toString()).toBe("- First item\n- Second item\n- Third item");
    });

    test("multi-line: all bullets are removed", () => {
      ({ view, parent } = createEditor("- First item\n- Second item\n- Third item"));
      selectAll(view);
      toggleBulletList(view);
      expect(view.state.doc.toString()).toBe("First item\nSecond item\nThird item");
    });

    test("multi-line: mixed content - adds bullets to lines without them", () => {
      ({ view, parent } = createEditor("- Has bullet\nNo bullet\n- Has bullet"));
      selectAll(view);
      toggleBulletList(view);
      // Not all have prefix, so all get the prefix added
      expect(view.state.doc.toString()).toBe("- - Has bullet\n- No bullet\n- - Has bullet");
    });

    test("multi-line: toggle twice returns to original", () => {
      const original = "First item\nSecond item\nThird item";
      ({ view, parent } = createEditor(original));
      selectAll(view);
      toggleBulletList(view);
      expect(view.state.doc.toString()).toBe("- First item\n- Second item\n- Third item");
      selectAll(view);
      toggleBulletList(view);
      expect(view.state.doc.toString()).toBe(original);
    });

    test("multi-line: toggle three times adds bullets again", () => {
      ({ view, parent } = createEditor("Item A\nItem B"));
      selectAll(view);
      toggleBulletList(view);
      selectAll(view);
      toggleBulletList(view);
      selectAll(view);
      toggleBulletList(view);
      expect(view.state.doc.toString()).toBe("- Item A\n- Item B");
    });
  });

  describe("toggleOrderedList (ol)", () => {
    test("single line: plain text becomes numbered", () => {
      ({ view, parent } = createEditor("Item one"));
      view.dispatch({ selection: { anchor: 0 } });
      toggleOrderedList(view);
      expect(view.state.doc.toString()).toBe("1. Item one");
    });

    test("single line: number is removed", () => {
      ({ view, parent } = createEditor("1. Item one"));
      view.dispatch({ selection: { anchor: 0 } });
      toggleOrderedList(view);
      expect(view.state.doc.toString()).toBe("Item one");
    });

    test("multi-line: all plain text lines become numbered sequentially", () => {
      ({ view, parent } = createEditor("First item\nSecond item\nThird item"));
      selectAll(view);
      toggleOrderedList(view);
      expect(view.state.doc.toString()).toBe("1. First item\n2. Second item\n3. Third item");
    });

    test("multi-line: all numbers are removed", () => {
      ({ view, parent } = createEditor("1. First item\n2. Second item\n3. Third item"));
      selectAll(view);
      toggleOrderedList(view);
      expect(view.state.doc.toString()).toBe("First item\nSecond item\nThird item");
    });

    test("multi-line: renumbers existing numbered list", () => {
      ({ view, parent } = createEditor("5. Wrong number\n10. Also wrong\n99. Way off"));
      selectAll(view);
      toggleOrderedList(view);
      // All have numbers, so they get removed
      expect(view.state.doc.toString()).toBe("Wrong number\nAlso wrong\nWay off");
    });

    test("multi-line: mixed numbered and plain - adds numbers to all", () => {
      ({ view, parent } = createEditor("1. Has number\nNo number\n3. Has number"));
      selectAll(view);
      toggleOrderedList(view);
      // Not all have prefix, so numbers are added/updated sequentially
      expect(view.state.doc.toString()).toBe("1. Has number\n2. No number\n3. Has number");
    });

    test("multi-line: toggle twice returns to original", () => {
      const original = "First item\nSecond item\nThird item";
      ({ view, parent } = createEditor(original));
      selectAll(view);
      toggleOrderedList(view);
      expect(view.state.doc.toString()).toBe("1. First item\n2. Second item\n3. Third item");
      selectAll(view);
      toggleOrderedList(view);
      expect(view.state.doc.toString()).toBe(original);
    });

    test("multi-line: toggle three times adds numbers again", () => {
      ({ view, parent } = createEditor("Item A\nItem B"));
      selectAll(view);
      toggleOrderedList(view);
      selectAll(view);
      toggleOrderedList(view);
      selectAll(view);
      toggleOrderedList(view);
      expect(view.state.doc.toString()).toBe("1. Item A\n2. Item B");
    });

    test("handles double-digit numbers correctly", () => {
      const lines = Array.from({ length: 12 }, (_, i) => `Item ${i + 1}`).join("\n");
      ({ view, parent } = createEditor(lines));
      selectAll(view);
      toggleOrderedList(view);
      const result = view.state.doc.toString();
      expect(result).toContain("10. Item 10");
      expect(result).toContain("11. Item 11");
      expect(result).toContain("12. Item 12");
    });
  });

  describe("toggleCheckbox", () => {
    test("multi-line: plain text becomes checkboxes", () => {
      ({ view, parent } = createEditor("Task A\nTask B\nTask C"));
      selectAll(view);
      toggleCheckbox(view);
      expect(view.state.doc.toString()).toBe("- [ ] Task A\n- [ ] Task B\n- [ ] Task C");
    });

    test("multi-line: all unchecked become checked", () => {
      ({ view, parent } = createEditor("- [ ] Task A\n- [ ] Task B\n- [ ] Task C"));
      selectAll(view);
      toggleCheckbox(view);
      expect(view.state.doc.toString()).toBe("- [x] Task A\n- [x] Task B\n- [x] Task C");
    });

    test("multi-line: all checked become unchecked", () => {
      ({ view, parent } = createEditor("- [x] Task A\n- [x] Task B\n- [x] Task C"));
      selectAll(view);
      toggleCheckbox(view);
      expect(view.state.doc.toString()).toBe("- [ ] Task A\n- [ ] Task B\n- [ ] Task C");
    });

    test("multi-line: toggle four times cycles through states", () => {
      ({ view, parent } = createEditor("Task A\nTask B"));
      selectAll(view);
      toggleCheckbox(view);
      expect(view.state.doc.toString()).toBe("- [ ] Task A\n- [ ] Task B");
      selectAll(view);
      toggleCheckbox(view);
      expect(view.state.doc.toString()).toBe("- [x] Task A\n- [x] Task B");
      selectAll(view);
      toggleCheckbox(view);
      expect(view.state.doc.toString()).toBe("- [ ] Task A\n- [ ] Task B");
      selectAll(view);
      toggleCheckbox(view);
      expect(view.state.doc.toString()).toBe("- [x] Task A\n- [x] Task B");
    });
  });

  describe("Mixed content scenarios", () => {
    test("convert bullets to ordered list", () => {
      ({ view, parent } = createEditor("- Item A\n- Item B\n- Item C"));
      selectAll(view);
      toggleOrderedList(view);
      // Bullets don't match ordered list pattern, so numbers are added
      expect(view.state.doc.toString()).toBe("1. - Item A\n2. - Item B\n3. - Item C");
    });

    test("convert ordered list to bullets", () => {
      ({ view, parent } = createEditor("1. Item A\n2. Item B\n3. Item C"));
      selectAll(view);
      toggleBulletList(view);
      // Numbers don't match bullet pattern, so bullets are added
      expect(view.state.doc.toString()).toBe("- 1. Item A\n- 2. Item B\n- 3. Item C");
    });

    test("convert bullets to checkboxes", () => {
      ({ view, parent } = createEditor("- Item A\n- Item B\n- Item C"));
      selectAll(view);
      toggleCheckbox(view);
      // Bullets become checkboxes (checkbox detection finds bullet and inserts [ ])
      expect(view.state.doc.toString()).toBe("- [ ] Item A\n- [ ] Item B\n- [ ] Item C");
    });

    test("convert checkboxes to ordered list", () => {
      ({ view, parent } = createEditor("- [ ] Task A\n- [ ] Task B\n- [ ] Task C"));
      selectAll(view);
      toggleOrderedList(view);
      // Checkboxes don't match OL pattern
      expect(view.state.doc.toString()).toBe("1. - [ ] Task A\n2. - [ ] Task B\n3. - [ ] Task C");
    });

    test("mixed ul/ol/checkbox selection - add bullets", () => {
      ({ view, parent } = createEditor("- Bullet\n1. Numbered\n- [ ] Checkbox\nPlain text"));
      selectAll(view);
      toggleBulletList(view);
      // Not all start with "- ", so prefix is added to all
      expect(view.state.doc.toString()).toBe(
        "- - Bullet\n- 1. Numbered\n- - [ ] Checkbox\n- Plain text"
      );
    });

    test("mixed ul/ol/checkbox selection - add numbers", () => {
      ({ view, parent } = createEditor("- Bullet\n1. Numbered\n- [ ] Checkbox\nPlain text"));
      selectAll(view);
      toggleOrderedList(view);
      // Not all match OL pattern, so numbers added
      expect(view.state.doc.toString()).toBe(
        "1. - Bullet\n2. Numbered\n3. - [ ] Checkbox\n4. Plain text"
      );
    });

    test("mixed ul/ol/checkbox selection - toggle checkboxes", () => {
      ({ view, parent } = createEditor("- Bullet\n1. Numbered\n- [ ] Checkbox\nPlain text"));
      selectAll(view);
      toggleCheckbox(view);
      // Each line transforms based on its current state
      expect(view.state.doc.toString()).toBe(
        "- [ ] Bullet\n- [ ] 1. Numbered\n- [x] Checkbox\n- [ ] Plain text"
      );
    });

    test("partial selection - only selected lines change", () => {
      ({ view, parent } = createEditor("Line 1\nLine 2\nLine 3\nLine 4\nLine 5"));
      selectLines(view, 2, 4);
      toggleBulletList(view);
      expect(view.state.doc.toString()).toBe("Line 1\n- Line 2\n- Line 3\n- Line 4\nLine 5");
    });

    test("sequential format changes", () => {
      ({ view, parent } = createEditor("Task A\nTask B\nTask C"));

      // Add bullets
      selectAll(view);
      toggleBulletList(view);
      expect(view.state.doc.toString()).toBe("- Task A\n- Task B\n- Task C");

      // Convert to checkboxes
      selectAll(view);
      toggleCheckbox(view);
      expect(view.state.doc.toString()).toBe("- [ ] Task A\n- [ ] Task B\n- [ ] Task C");

      // Check all
      selectAll(view);
      toggleCheckbox(view);
      expect(view.state.doc.toString()).toBe("- [x] Task A\n- [x] Task B\n- [x] Task C");

      // Add numbers on top (complex nesting)
      selectAll(view);
      toggleOrderedList(view);
      expect(view.state.doc.toString()).toBe("1. - [x] Task A\n2. - [x] Task B\n3. - [x] Task C");
    });
  });

  describe("Undo/Redo functionality", () => {
    test("undo single bullet toggle", () => {
      const original = "Item A\nItem B\nItem C";
      ({ view, parent } = createEditor(original));
      selectAll(view);
      toggleBulletList(view);
      expect(view.state.doc.toString()).toBe("- Item A\n- Item B\n- Item C");

      undo(view);
      expect(view.state.doc.toString()).toBe(original);
    });

    test("redo single bullet toggle", () => {
      ({ view, parent } = createEditor("Item A\nItem B\nItem C"));
      selectAll(view);
      toggleBulletList(view);
      const withBullets = view.state.doc.toString();

      undo(view);
      redo(view);
      expect(view.state.doc.toString()).toBe(withBullets);
    });

    test("undo single ordered list toggle", () => {
      const original = "Item A\nItem B\nItem C";
      ({ view, parent } = createEditor(original));
      selectAll(view);
      toggleOrderedList(view);
      expect(view.state.doc.toString()).toBe("1. Item A\n2. Item B\n3. Item C");

      undo(view);
      expect(view.state.doc.toString()).toBe(original);
    });

    test("redo single ordered list toggle", () => {
      ({ view, parent } = createEditor("Item A\nItem B\nItem C"));
      selectAll(view);
      toggleOrderedList(view);
      const withNumbers = view.state.doc.toString();

      undo(view);
      redo(view);
      expect(view.state.doc.toString()).toBe(withNumbers);
    });

    test("undo single checkbox toggle", () => {
      const original = "Task A\nTask B\nTask C";
      ({ view, parent } = createEditor(original));
      selectAll(view);
      toggleCheckbox(view);
      expect(view.state.doc.toString()).toBe("- [ ] Task A\n- [ ] Task B\n- [ ] Task C");

      undo(view);
      expect(view.state.doc.toString()).toBe(original);
    });

    test("redo single checkbox toggle", () => {
      ({ view, parent } = createEditor("Task A\nTask B\nTask C"));
      selectAll(view);
      toggleCheckbox(view);
      const withCheckboxes = view.state.doc.toString();

      undo(view);
      redo(view);
      expect(view.state.doc.toString()).toBe(withCheckboxes);
    });

    test("undo multiple sequential toggles step by step", () => {
      const original = "Item A\nItem B";
      ({ view, parent } = createEditor(original));

      selectAll(view);
      toggleBulletList(view);
      const afterBullets = view.state.doc.toString();
      expect(afterBullets).toBe("- Item A\n- Item B");

      selectAll(view);
      toggleBulletList(view);
      const afterRemove = view.state.doc.toString();
      expect(afterRemove).toBe(original);

      selectAll(view);
      toggleOrderedList(view);
      const afterNumbers = view.state.doc.toString();
      expect(afterNumbers).toBe("1. Item A\n2. Item B");

      // Undo back through all changes
      undo(view);
      expect(view.state.doc.toString()).toBe(afterRemove);

      undo(view);
      expect(view.state.doc.toString()).toBe(afterBullets);

      undo(view);
      expect(view.state.doc.toString()).toBe(original);
    });

    test("redo multiple sequential toggles step by step", () => {
      const original = "Item A\nItem B";
      ({ view, parent } = createEditor(original));

      selectAll(view);
      toggleBulletList(view);
      const afterBullets = view.state.doc.toString();

      selectAll(view);
      toggleOrderedList(view);
      const afterNumbers = view.state.doc.toString();

      // Undo all
      undo(view);
      undo(view);
      expect(view.state.doc.toString()).toBe(original);

      // Redo step by step
      redo(view);
      expect(view.state.doc.toString()).toBe(afterBullets);

      redo(view);
      expect(view.state.doc.toString()).toBe(afterNumbers);
    });

    test("undo/redo with checkbox state changes", () => {
      ({ view, parent } = createEditor("- [ ] Task A\n- [ ] Task B"));

      selectAll(view);
      toggleCheckbox(view);
      expect(view.state.doc.toString()).toBe("- [x] Task A\n- [x] Task B");

      selectAll(view);
      toggleCheckbox(view);
      expect(view.state.doc.toString()).toBe("- [ ] Task A\n- [ ] Task B");

      // Undo unchecking
      undo(view);
      expect(view.state.doc.toString()).toBe("- [x] Task A\n- [x] Task B");

      // Undo checking
      undo(view);
      expect(view.state.doc.toString()).toBe("- [ ] Task A\n- [ ] Task B");

      // Redo checking
      redo(view);
      expect(view.state.doc.toString()).toBe("- [x] Task A\n- [x] Task B");
    });

    test("undo/redo mixed format changes", () => {
      const original = "Task A\nTask B";
      ({ view, parent } = createEditor(original));

      // Add bullets
      selectAll(view);
      toggleBulletList(view);
      const step1 = view.state.doc.toString();

      // Convert to checkboxes
      selectAll(view);
      toggleCheckbox(view);
      const step2 = view.state.doc.toString();

      // Check them
      selectAll(view);
      toggleCheckbox(view);
      const step3 = view.state.doc.toString();

      // Undo all the way back
      undo(view);
      expect(view.state.doc.toString()).toBe(step2);

      undo(view);
      expect(view.state.doc.toString()).toBe(step1);

      undo(view);
      expect(view.state.doc.toString()).toBe(original);

      // Redo all the way forward
      redo(view);
      expect(view.state.doc.toString()).toBe(step1);

      redo(view);
      expect(view.state.doc.toString()).toBe(step2);

      redo(view);
      expect(view.state.doc.toString()).toBe(step3);
    });

    test("undo after partial selection change", () => {
      const original = "Line 1\nLine 2\nLine 3\nLine 4";
      ({ view, parent } = createEditor(original));

      // Only select middle lines
      selectLines(view, 2, 3);
      toggleBulletList(view);
      expect(view.state.doc.toString()).toBe("Line 1\n- Line 2\n- Line 3\nLine 4");

      undo(view);
      expect(view.state.doc.toString()).toBe(original);
    });

    test("complex undo/redo scenario with many toggles", () => {
      const original = "A\nB\nC";
      ({ view, parent } = createEditor(original));
      const states = [original];

      // Toggle bullets 3 times
      for (let i = 0; i < 3; i++) {
        selectAll(view);
        toggleBulletList(view);
        states.push(view.state.doc.toString());
      }

      // Verify we have 4 states (original + 3 toggles)
      expect(states).toEqual(["A\nB\nC", "- A\n- B\n- C", "A\nB\nC", "- A\n- B\n- C"]);

      // Undo all 3 toggles
      for (let i = 2; i >= 0; i--) {
        undo(view);
        expect(view.state.doc.toString()).toBe(states[i]);
      }

      // Redo all 3 toggles
      for (let i = 1; i <= 3; i++) {
        redo(view);
        expect(view.state.doc.toString()).toBe(states[i]);
      }
    });
  });

  describe("Partial bullet list to ordered list conversion", () => {
    test("convert middle lines of bullet list to ordered list", () => {
      // Reproducing bug from screenshot:
      // User has bullet list, selects middle lines, clicks ordered list
      ({ view, parent } = createEditor("out\n- hi\n- hello\n- test\nmeow"));

      // Select lines 3 and 4 (- hello and - test)
      selectLines(view, 3, 4);
      toggleOrderedList(view);

      // Expected: numbers added before bullets on selected lines only
      const result = view.state.doc.toString();
      console.log("Result:", JSON.stringify(result));
      expect(result).toBe("out\n- hi\n1. - hello\n2. - test\nmeow");
    });

    test("convert first two lines of bullet list to ordered list", () => {
      ({ view, parent } = createEditor("- first\n- second\n- third\n- fourth"));
      selectLines(view, 1, 2);
      toggleOrderedList(view);
      expect(view.state.doc.toString()).toBe("1. - first\n2. - second\n- third\n- fourth");
    });

    test("convert last two lines of bullet list to ordered list", () => {
      ({ view, parent } = createEditor("- first\n- second\n- third\n- fourth"));
      selectLines(view, 3, 4);
      toggleOrderedList(view);
      expect(view.state.doc.toString()).toBe("- first\n- second\n1. - third\n2. - fourth");
    });

    test("convert middle of ordered list to bullets", () => {
      ({ view, parent } = createEditor("1. first\n2. second\n3. third\n4. fourth"));
      selectLines(view, 2, 3);
      toggleBulletList(view);
      expect(view.state.doc.toString()).toBe("1. first\n- 2. second\n- 3. third\n4. fourth");
    });
  });

  describe("Edge cases", () => {
    test("empty document", () => {
      ({ view, parent } = createEditor(""));
      selectAll(view);
      toggleBulletList(view);
      expect(view.state.doc.toString()).toBe("- ");
    });

    test("single empty line", () => {
      ({ view, parent } = createEditor("\n"));
      selectAll(view);
      toggleBulletList(view);
      expect(view.state.doc.toString()).toBe("- \n- ");
    });

    test("lines with only whitespace", () => {
      ({ view, parent } = createEditor("  \n   \n    "));
      selectAll(view);
      toggleBulletList(view);
      expect(view.state.doc.toString()).toBe("-   \n-    \n-     ");
    });

    test("very long line", () => {
      const longText = "A".repeat(10000);
      ({ view, parent } = createEditor(longText));
      selectAll(view);
      toggleBulletList(view);
      expect(view.state.doc.toString()).toBe(`- ${longText}`);
    });

    test("many lines", () => {
      const lines = Array.from({ length: 100 }, (_, i) => `Line ${i + 1}`).join("\n");
      ({ view, parent } = createEditor(lines));
      selectAll(view);
      toggleBulletList(view);

      const result = view.state.doc.toString();
      const resultLines = result.split("\n");
      expect(resultLines.length).toBe(100);
      expect(resultLines[0]).toBe("- Line 1");
      expect(resultLines[99]).toBe("- Line 100");
    });

    test("unicode content", () => {
      ({ view, parent } = createEditor("日本語\n中文\nहिन्दी\n🎉🎊🎁"));
      selectAll(view);
      toggleBulletList(view);
      expect(view.state.doc.toString()).toBe("- 日本語\n- 中文\n- हिन्दी\n- 🎉🎊🎁");
    });

    test("lines with existing indentation", () => {
      ({ view, parent } = createEditor("  Indented\n    More indented\nNot indented"));
      selectAll(view);
      toggleBulletList(view);
      expect(view.state.doc.toString()).toBe("-   Indented\n-     More indented\n- Not indented");
    });

    test("selection starting mid-line", () => {
      ({ view, parent } = createEditor("Line 1\nLine 2\nLine 3"));
      // Select from middle of line 1 to middle of line 3
      view.dispatch({ selection: { anchor: 3, head: view.state.doc.length - 2 } });
      toggleBulletList(view);
      // Should still affect entire lines
      expect(view.state.doc.toString()).toBe("- Line 1\n- Line 2\n- Line 3");
    });
  });

  describe("Blockquote toggle", () => {
    test("multi-line: all plain text lines become blockquotes", () => {
      ({ view, parent } = createEditor("Quote 1\nQuote 2\nQuote 3"));
      selectAll(view);
      toggleBlockquote(view);
      expect(view.state.doc.toString()).toBe("> Quote 1\n> Quote 2\n> Quote 3");
    });

    test("multi-line: all blockquotes are removed", () => {
      ({ view, parent } = createEditor("> Quote 1\n> Quote 2\n> Quote 3"));
      selectAll(view);
      toggleBlockquote(view);
      expect(view.state.doc.toString()).toBe("Quote 1\nQuote 2\nQuote 3");
    });

    test("undo/redo blockquote toggle", () => {
      const original = "Quote A\nQuote B";
      ({ view, parent } = createEditor(original));
      selectAll(view);
      toggleBlockquote(view);
      expect(view.state.doc.toString()).toBe("> Quote A\n> Quote B");

      undo(view);
      expect(view.state.doc.toString()).toBe(original);

      redo(view);
      expect(view.state.doc.toString()).toBe("> Quote A\n> Quote B");
    });
  });
});
