import { describe, test, expect } from "vitest";
import { EditorState } from "@codemirror/state";
import { findSectionFold } from "../../findSectionFold.js";

describe("findSectionFold", () => {
  test("returns fold range for multi-line section", () => {
    const doc = `Section Header
This is line 2
This is line 3
This is line 4


Next section`;

    const state = EditorState.create({ doc });

    // Find the first section (line 1)
    const line1 = state.doc.line(1);
    const result = findSectionFold(state, line1.from);

    expect(result).not.toBeNull();
    expect(result.from).toBe(line1.to); // After "Section Header"

    // Should fold until the end of line 4 (before the blank lines)
    const line4 = state.doc.line(4);
    expect(result.to).toBe(line4.to);
  });

  test("returns null for single-line section", () => {
    const doc = `Single line section


Next section
With content`;

    const state = EditorState.create({ doc });

    // The first section only has one line
    const line1 = state.doc.line(1);
    const result = findSectionFold(state, line1.from);

    // Should return null because there's nothing to fold (section.to === line.to + 1)
    expect(result).toBeNull();
  });

  test("returns null for non-section line", () => {
    const doc = `Section Header
Content line


Next section`;

    const state = EditorState.create({ doc });

    // Line 2 is content, not a section header
    const line2 = state.doc.line(2);
    const result = findSectionFold(state, line2.from);

    // Should return null because line 2 is not a section start
    expect(result).toBeNull();
  });

  test("handles section at end of document", () => {
    const doc = `First section


Last section header
Last section content line 1
Last section content line 2`;

    const state = EditorState.create({ doc });

    // Find the last section (line 4)
    const line4 = state.doc.line(4);
    const result = findSectionFold(state, line4.from);

    expect(result).not.toBeNull();
    expect(result.from).toBe(line4.to); // After "Last section header"

    // Should fold to the end of the document
    const lastLine = state.doc.line(state.doc.lines);
    expect(result.to).toBe(lastLine.to);
  });

  test("handles section with only one content line", () => {
    const doc = `Section Header
Only one content line


Next section`;

    const state = EditorState.create({ doc });

    // The first section has header + one content line = 2 lines total
    const line1 = state.doc.line(1);
    const result = findSectionFold(state, line1.from);

    expect(result).not.toBeNull();
    expect(result.from).toBe(line1.to); // After "Section Header"

    // Should fold just the one content line
    const line2 = state.doc.line(2);
    expect(result.to).toBe(line2.to);
  });

  test("returns correct range for first section", () => {
    const doc = `First Section Header
First section line 1
First section line 2


Second Section Header
Second section content`;

    const state = EditorState.create({ doc });

    const line1 = state.doc.line(1);
    const result = findSectionFold(state, line1.from);

    expect(result).not.toBeNull();
    expect(result.from).toBe(line1.to);

    // Should end at line 3 (last line of first section)
    const line3 = state.doc.line(3);
    expect(result.to).toBe(line3.to);
  });

  test("returns correct range for last section", () => {
    const doc = `First Section


Last Section Header
Last section line 1
Last section line 2
Last section line 3`;

    const state = EditorState.create({ doc });

    // Find last section (line 4)
    const line4 = state.doc.line(4);
    const result = findSectionFold(state, line4.from);

    expect(result).not.toBeNull();
    expect(result.from).toBe(line4.to); // After "Last Section Header"

    // Should fold to end of document (line 7)
    const line7 = state.doc.line(7);
    expect(result.to).toBe(line7.to);
  });
});
