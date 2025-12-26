/**
 * SECTION DEFINITION
 *
 * A "section" is a contiguous block of non-blank lines.
 *
 * Rules:
 * - A section starts at the first non-blank line after:
 *     - the beginning of the document, or
 *     - two or more consecutive blank lines.
 *
 * - A section ends just before:
 *     - the next occurrence of two or more consecutive blank lines, or
 *     - the end of the document (EOF), whichever comes first.
 *
 * Notes:
 * - The blank lines that delimit sections are NOT included in the section.
 * - If there are no blank lines, the entire document is a single section.
 * - Trailing blank lines are ignored and do not form a section.
 */

import { getSections } from "../../getSections.js";
import { EditorState } from "@codemirror/state";

function createDocFromText(text) {
  return EditorState.create({ doc: text }).doc;
}

// for seeing what's actually happening
function printSectionSpans(text, sections) {
  let result = "";
  let cursor = 0;
  for (const { from, to } of sections) {
    if (cursor < from) {
      result += text.slice(cursor, from);
    }
    result += "[[" + text.slice(from, to) + "]]";
    cursor = to;
  }
  result += text.slice(cursor);
  console.log(result);
}

describe("getSections", () => {
  test("single section", () => {
    const text = "Hello world\nThis is a note";
    const doc = createDocFromText(text);
    const sections = getSections(doc);
    expect(sections).toEqual([{ from: 0, to: text.length, line: 1 }]);
  });

  test("two sections", () => {
    const text = "First section\n\n\nSecond section\nMore text";
    const doc = createDocFromText(text);
    const sections = getSections(doc);
    printSectionSpans(text, sections);
    expect(sections).toEqual([
      { from: 0, to: 13, line: 1 }, // ends at \n\n\n start
      { from: 16, to: 40, line: 4 }, // starts at "Second section"
    ]);
  });

  test("only blank lines", () => {
    const doc = createDocFromText("\n\n\n");
    expect(getSections(doc)).toEqual([]);
  });

  test("empty document", () => {
    const doc = createDocFromText("");
    expect(getSections(doc)).toEqual([]);
  });

  test("blank lines at start", () => {
    const text = "\n\nStart\nBody\n\n\nNext\n";
    const doc = createDocFromText(text);
    const sections = getSections(doc);
    expect(sections).toEqual([
      { from: 2, to: 12, line: 3 }, // "Start\nBody\n"
      { from: 15, to: 20, line: 7 }, // "Next\n"
    ]);
  });

  test("trailing blank lines after last section", () => {
    const text = "Section one\nContent\n\n\n";
    const doc = createDocFromText(text);
    const sections = getSections(doc);
    expect(sections).toEqual([{ from: 0, to: 19, line: 1 }]);
  });

  test("blank lines between multiple sections", () => {
    const text = "First\nLine\n\n\nSecond\nLine\n\n\nThird";
    const doc = createDocFromText(text);
    const sections = getSections(doc);
    expect(sections).toEqual([
      { from: 0, to: 10, line: 1 },
      { from: 13, to: 24, line: 5 },
      { from: 27, to: 32, line: 9 },
    ]);
  });

  test("no blank lines but multiple logical sections", () => {
    const text = "First section\nSecond section\nThird section";
    const doc = createDocFromText(text);
    const sections = getSections(doc);
    expect(sections).toEqual([{ from: 0, to: text.length, line: 1 }]);
  });

  test("section with only one line of text between blank lines", () => {
    const text = "\n\nTitle\n\n\n";
    const doc = createDocFromText(text);
    const sections = getSections(doc);
    expect(sections).toEqual([
      {
        from: text.indexOf("Title"),
        to: text.indexOf("Title") + "Title".length,
        line: 3,
      },
    ]);
  });

  test("section with indented lines", () => {
    const text = "  Line one\n    Line two\n\n\nNext";
    const doc = createDocFromText(text);
    const sections = getSections(doc);
    expect(sections).toEqual([
      { from: 0, to: 23, line: 1 },
      { from: 26, to: 30, line: 5 },
    ]);
  });

  test("handles document with only whitespace at start", () => {
    const text = "   \n   \n\nContent";
    const doc = createDocFromText(text);

    // This should NOT throw an error
    expect(() => getSections(doc)).not.toThrow();

    const sections = getSections(doc);
    expect(sections.length).toBeGreaterThanOrEqual(0);
  });

  test("handles document with leading blank lines", () => {
    const text = "\n\n\n\nFirst section";
    const doc = createDocFromText(text);

    expect(() => getSections(doc)).not.toThrow();

    const sections = getSections(doc);
    expect(sections).toEqual([
      { from: 4, to: 17, line: 5 }, // "First section" starts at line 5
    ]);
  });

  test("handles single character followed by two blank lines", () => {
    // This is an edge case that could trigger j - blankStreak = 0
    const text = "A\n\n";
    const doc = createDocFromText(text);

    expect(() => getSections(doc)).not.toThrow();

    const sections = getSections(doc);
    expect(sections).toEqual([
      { from: 0, to: 1, line: 1 }, // Just "A"
    ]);
  });
});
