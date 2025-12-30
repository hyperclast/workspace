import { describe, test, expect } from "vitest";
import { EditorState } from "@codemirror/state";
import { findSectionFold } from "../../findSectionFold.js";

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
