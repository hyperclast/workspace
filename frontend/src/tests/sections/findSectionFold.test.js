import { describe, test, expect } from "vitest";
import { EditorState } from "@codemirror/state";
import { findSectionFold } from "../../findSectionFold.js";
import { SECTION_SCAN_LIMIT_LINES } from "../../config/performance.js";

describe("findSectionFold", () => {
  test("returns fold range for H1 with content", () => {
    const doc = `# Main Title
This is line 2
This is line 3`;

    const state = EditorState.create({ doc });
    const line1 = state.doc.line(1);
    const result = findSectionFold(state, line1.from);

    expect(result).not.toBeNull();
    expect(result.from).toBe(line1.to);
    expect(result.to).toBe(doc.length);
  });

  test("returns null for heading-only section at end", () => {
    const doc = `# First
Content
# Last`;

    const state = EditorState.create({ doc });
    const line3 = state.doc.line(3);
    const result = findSectionFold(state, line3.from);

    expect(result).toBeNull();
  });

  test("returns null for non-heading line", () => {
    const doc = `# Title
Content line`;

    const state = EditorState.create({ doc });
    const line2 = state.doc.line(2);
    const result = findSectionFold(state, line2.from);

    expect(result).toBeNull();
  });

  test("H1 folds until next H1", () => {
    const doc = `# First
Content 1
# Second
Content 2`;

    const state = EditorState.create({ doc });
    const line1 = state.doc.line(1);
    const result = findSectionFold(state, line1.from);

    expect(result).not.toBeNull();
    expect(result.from).toBe(line1.to);
    const line2 = state.doc.line(2);
    expect(result.to).toBe(line2.to);
  });

  test("H2 folds until next H2", () => {
    const doc = `# Main
## Sub 1
Content 1
## Sub 2
Content 2`;

    const state = EditorState.create({ doc });
    const line2 = state.doc.line(2);
    const result = findSectionFold(state, line2.from);

    expect(result).not.toBeNull();
    expect(result.from).toBe(line2.to);
    const line3 = state.doc.line(3);
    expect(result.to).toBe(line3.to);
  });

  test("H2 folds until H1", () => {
    const doc = `# First
## Sub
Content
# Second`;

    const state = EditorState.create({ doc });
    const line2 = state.doc.line(2);
    const result = findSectionFold(state, line2.from);

    expect(result).not.toBeNull();
    const line3 = state.doc.line(3);
    expect(result.to).toBe(line3.to);
  });

  test("H1 includes nested H2 in fold", () => {
    const doc = `# Main
Intro
## Sub
Details
More`;

    const state = EditorState.create({ doc });
    const line1 = state.doc.line(1);
    const result = findSectionFold(state, line1.from);

    expect(result).not.toBeNull();
    expect(result.to).toBe(doc.length);
  });

  test("handles document with no headings", () => {
    const doc = `Just plain text
No headings here`;

    const state = EditorState.create({ doc });
    const line1 = state.doc.line(1);
    const result = findSectionFold(state, line1.from);

    expect(result).toBeNull();
  });

  test("handles deep nesting", () => {
    const doc = `# H1
## H2
### H3
Content
## H2b`;

    const state = EditorState.create({ doc });
    const line3 = state.doc.line(3);
    const result = findSectionFold(state, line3.from);

    expect(result).not.toBeNull();
    const line4 = state.doc.line(4);
    expect(result.to).toBe(line4.to);
  });

  test("returns fold range for section at document end", () => {
    const doc = `# First
## Sub
Content
More content`;

    const state = EditorState.create({ doc });
    const line2 = state.doc.line(2);
    const result = findSectionFold(state, line2.from);

    expect(result).not.toBeNull();
    expect(result.to).toBe(doc.length);
  });
});

describe("findSectionFold - threshold boundaries", () => {
  function generateDocWithHeading(lineCount) {
    const lines = ["# Heading"];
    for (let i = 1; i < lineCount; i++) {
      lines.push(`Line ${i}`);
    }
    return lines.join("\n");
  }

  test(`works correctly at ${SECTION_SCAN_LIMIT_LINES - 1} lines (just under threshold)`, () => {
    const doc = generateDocWithHeading(SECTION_SCAN_LIMIT_LINES - 1);
    const state = EditorState.create({ doc });

    expect(state.doc.lines).toBe(SECTION_SCAN_LIMIT_LINES - 1);

    const line1 = state.doc.line(1);
    const result = findSectionFold(state, line1.from);

    expect(result).not.toBeNull();
    expect(result.from).toBe(line1.to);
    expect(result.to).toBe(doc.length);
  });

  test(`works correctly at exactly ${SECTION_SCAN_LIMIT_LINES} lines (at threshold)`, () => {
    const doc = generateDocWithHeading(SECTION_SCAN_LIMIT_LINES);
    const state = EditorState.create({ doc });

    expect(state.doc.lines).toBe(SECTION_SCAN_LIMIT_LINES);

    const line1 = state.doc.line(1);
    const result = findSectionFold(state, line1.from);

    expect(result).not.toBeNull();
  });

  test(`disables folding at ${SECTION_SCAN_LIMIT_LINES + 1} lines (just over threshold)`, () => {
    const doc = generateDocWithHeading(SECTION_SCAN_LIMIT_LINES + 1);
    const state = EditorState.create({ doc });

    expect(state.doc.lines).toBe(SECTION_SCAN_LIMIT_LINES + 1);

    const line1 = state.doc.line(1);
    const result = findSectionFold(state, line1.from);

    expect(result).toBeNull();
  });
});

describe("findSectionFold - cache isolation", () => {
  test("separate documents have independent caches", () => {
    const doc1 = `# Doc 1
Content 1`;

    const doc2 = `# Doc 2
## Sub heading
Content 2`;

    const state1 = EditorState.create({ doc: doc1 });
    const state2 = EditorState.create({ doc: doc2 });

    const result1 = findSectionFold(state1, state1.doc.line(1).from);
    const result2 = findSectionFold(state2, state2.doc.line(1).from);

    expect(result1).not.toBeNull();
    expect(result2).not.toBeNull();

    expect(result1.to).toBe(doc1.length);
    expect(result2.to).toBe(doc2.length);

    expect(result1.to).not.toBe(result2.to);
  });

  test("document modification creates new cache entry", () => {
    const initialDoc = `# Heading
Line 1`;

    const state1 = EditorState.create({ doc: initialDoc });
    const result1 = findSectionFold(state1, state1.doc.line(1).from);

    const modifiedDoc = `# Heading
Line 1
Line 2
Line 3`;

    const state2 = EditorState.create({ doc: modifiedDoc });
    const result2 = findSectionFold(state2, state2.doc.line(1).from);

    expect(result1).not.toBeNull();
    expect(result2).not.toBeNull();

    expect(result1.to).not.toBe(result2.to);
    expect(result1.to).toBe(initialDoc.length);
    expect(result2.to).toBe(modifiedDoc.length);
  });

  test("interleaved operations on different documents work correctly", () => {
    const docA = `# A
Content A`;

    const docB = `# B
Content B
More B`;

    const stateA = EditorState.create({ doc: docA });
    const stateB = EditorState.create({ doc: docB });

    const resultA1 = findSectionFold(stateA, stateA.doc.line(1).from);
    const resultB1 = findSectionFold(stateB, stateB.doc.line(1).from);
    const resultA2 = findSectionFold(stateA, stateA.doc.line(1).from);

    expect(resultA1).not.toBeNull();
    expect(resultB1).not.toBeNull();
    expect(resultA2).not.toBeNull();

    expect(resultA1.to).toBe(resultA2.to);
    expect(resultA1.to).not.toBe(resultB1.to);
  });
});
