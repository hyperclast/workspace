import { describe, test, expect, beforeEach } from "vitest";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { resolveAnchorRange, buildSuggestionChange } from "../../lib/utils/applySuggestion.js";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeState(doc) {
  return EditorState.create({ doc });
}

/** Create a state, apply the change from buildSuggestionChange, return new doc string. */
function applyChange(doc, anchorRange, body) {
  const state = makeState(doc);
  const change = buildSuggestionChange(state, anchorRange, body);
  const newState = state.update({ changes: change }).state;
  return newState.doc.toString();
}

// ---------------------------------------------------------------------------
// resolveAnchorRange
// ---------------------------------------------------------------------------
describe("resolveAnchorRange", () => {
  test("returns range from highlight field when comment ID matches", () => {
    const state = makeState("hello world");
    const ranges = [
      { from: 0, to: 5, commentId: "c1" },
      { from: 6, to: 11, commentId: "c2" },
    ];
    const result = resolveAnchorRange(state, ranges, {
      external_id: "c2",
      anchor_text: "world",
    });
    expect(result).toEqual({ from: 6, to: 11 });
  });

  test("prefers highlight range over text search", () => {
    // The highlight range might differ from a naive text search if the anchor
    // was resolved via Yjs binary positions.
    const state = makeState("world hello world");
    const ranges = [{ from: 12, to: 17, commentId: "c1" }]; // second "world"
    const result = resolveAnchorRange(state, ranges, {
      external_id: "c1",
      anchor_text: "world",
    });
    // Should use highlight range (12-17), not text search (0-5)
    expect(result).toEqual({ from: 12, to: 17 });
  });

  test("falls back to text search when no highlight range matches", () => {
    const state = makeState("the quick brown fox");
    const result = resolveAnchorRange(state, [], {
      external_id: "c1",
      anchor_text: "brown fox",
    });
    expect(result).toEqual({ from: 10, to: 19 });
  });

  test("returns null when anchor text is not found", () => {
    const state = makeState("hello world");
    const result = resolveAnchorRange(state, [], {
      external_id: "c1",
      anchor_text: "missing",
    });
    expect(result).toBeNull();
  });

  test("returns null when anchor text is empty and no highlight range", () => {
    const state = makeState("hello world");
    const result = resolveAnchorRange(state, [], {
      external_id: "c1",
      anchor_text: "",
    });
    expect(result).toBeNull();
  });

  test("returns null when highlight ranges array is empty and no anchor text", () => {
    const state = makeState("hello world");
    const result = resolveAnchorRange(state, [], {
      external_id: "c1",
      anchor_text: "",
    });
    expect(result).toBeNull();
  });

  test("text search finds first occurrence", () => {
    const state = makeState("foo bar foo baz foo");
    const result = resolveAnchorRange(state, [], {
      external_id: "c1",
      anchor_text: "foo",
    });
    expect(result).toEqual({ from: 0, to: 3 });
  });
});

// ---------------------------------------------------------------------------
// buildSuggestionChange — insertion position (paragraph-aware)
// ---------------------------------------------------------------------------
describe("buildSuggestionChange — insertion position", () => {
  test("inserts after end of paragraph (walks past continuation lines)", () => {
    // No blank lines → entire doc is one paragraph
    const doc = "Line one\nLine two\nLine three";
    const result = applyChange(doc, { from: 9, to: 17 }, "Suggestion");
    // Should insert after "Line three" (end of paragraph), not after "Line two"
    expect(result).toBe("Line one\nLine two\nLine three\n\nSuggestion\n");
  });

  test("inserts after paragraph boundary when blank line exists", () => {
    const doc = "Para one line A\nPara one line B\n\nPara two";
    // Anchor in first paragraph
    const result = applyChange(doc, { from: 0, to: 8 }, "Suggestion");
    // Should insert after "Para one line B" (end of first paragraph)
    expect(result).toBe("Para one line A\nPara one line B\n\nSuggestion\n\n\nPara two");
  });

  test("anchor mid-line in hard-wrapped paragraph", () => {
    const doc = "The quick brown fox jumps over the lazy dog.\nThe end is near.";
    // Anchor covers "brown fox" mid-line — should walk to end of paragraph
    const result = applyChange(doc, { from: 10, to: 19 }, "Suggestion");
    expect(result).toBe(
      "The quick brown fox jumps over the lazy dog.\nThe end is near.\n\nSuggestion\n"
    );
  });

  test("anchor at very end of document", () => {
    const doc = "First line\nLast line";
    const result = applyChange(doc, { from: 11, to: 20 }, "Appended");
    expect(result).toBe("First line\nLast line\n\nAppended\n");
  });

  test("anchor in first paragraph of multi-paragraph document", () => {
    const doc = "First para\n\nSecond para\n\nThird para";
    const result = applyChange(doc, { from: 0, to: 5 }, "After first");
    expect(result).toBe("First para\n\nAfter first\n\n\nSecond para\n\nThird para");
  });

  test("anchor in last paragraph", () => {
    const doc = "First para\n\nSecond para\n\nThird para";
    const result = applyChange(doc, { from: 25, to: 35 }, "After third");
    expect(result).toBe("First para\n\nSecond para\n\nThird para\n\nAfter third\n");
  });

  test("single-line document", () => {
    const doc = "Only line here";
    const result = applyChange(doc, { from: 0, to: 14 }, "New content");
    expect(result).toBe("Only line here\n\nNew content\n");
  });

  test("empty document", () => {
    const doc = "";
    const result = applyChange(doc, { from: 0, to: 0 }, "Inserted");
    expect(result).toBe("\n\nInserted\n");
  });
});

// ---------------------------------------------------------------------------
// buildSuggestionChange — body trimming
// ---------------------------------------------------------------------------
describe("buildSuggestionChange — body handling", () => {
  test("trims leading and trailing whitespace from body", () => {
    const doc = "Content here";
    const result = applyChange(doc, { from: 0, to: 7 }, "  trimmed  ");
    expect(result).toBe("Content here\n\ntrimmed\n");
  });

  test("preserves internal newlines in body", () => {
    const doc = "Content here";
    const body = "Line A\nLine B\nLine C";
    const result = applyChange(doc, { from: 0, to: 7 }, body);
    expect(result).toBe("Content here\n\nLine A\nLine B\nLine C\n");
  });

  test("multi-paragraph body with bullet points", () => {
    const doc = "Paragraph one\n\nParagraph two";
    const body =
      "Here are some references:\n\n- **BOHB**: Falkner et al., 2018\n- **ASHA**: Li et al., 2020";
    const result = applyChange(doc, { from: 0, to: 13 }, body);
    // \n\n prefix + body + \n trailing, then the original \n\n before "Paragraph two" remains
    expect(result).toBe(
      "Paragraph one\n\n" +
        "Here are some references:\n\n- **BOHB**: Falkner et al., 2018\n- **ASHA**: Li et al., 2020\n" +
        "\n\n" +
        "Paragraph two"
    );
  });
});

// ---------------------------------------------------------------------------
// buildSuggestionChange — hard-wrapped paragraph handling
// ---------------------------------------------------------------------------
describe("hard-wrapped paragraph handling", () => {
  test("anchor mid-word in single-line paragraph", () => {
    const doc = "exploration can easily take tens of training-years.";
    const result = applyChange(doc, { from: 16, to: 18 }, "Suggestion");
    expect(result).toBe("exploration can easily take tens of training-years.\n\nSuggestion\n");
  });

  test("anchor mid-line in hard-wrapped paragraph walks to paragraph end", () => {
    const doc =
      "Moreover, no systematic, efficient exploration or pruning of the\n" +
      "space is possible. In turn, an exhaustive exploration can easily take\n" +
      "tens of training-years.";
    const anchorText = "space is possible. In turn, an exhaustive exploration ca";
    const anchorFrom = doc.indexOf(anchorText);
    const anchorTo = anchorFrom + anchorText.length;

    const result = applyChange(doc, { from: anchorFrom, to: anchorTo }, "Reference here");
    // All three lines are one paragraph (no blank lines), so insertion goes after "tens of training-years."
    expect(result).toBe(doc + "\n\nReference here\n");
  });

  test("hard-wrapped paragraph followed by blank line", () => {
    const doc =
      "The engines are pitted against each other in a round-robin fash-\n" +
      "ion. Each engine plays 400 matches.\n" +
      "\n" +
      "Next section starts here.";
    const anchorText = "pitted against each other";
    const anchorFrom = doc.indexOf(anchorText);
    const anchorTo = anchorFrom + anchorText.length;

    const result = applyChange(doc, { from: anchorFrom, to: anchorTo }, "Inserted");
    // Should insert after "ion. Each engine plays 400 matches." (end of paragraph before blank line)
    const lines = result.split("\n");
    expect(lines[0]).toBe("The engines are pitted against each other in a round-robin fash-");
    expect(lines[1]).toBe("ion. Each engine plays 400 matches.");
    expect(lines[2]).toBe("");
    expect(lines[3]).toBe("Inserted");
  });

  test("all lines in same paragraph — inserts at end of doc", () => {
    const doc = "AAA\nBBB\nCCC\nDDD";
    const result = applyChange(doc, { from: 4, to: 11 }, "Inserted");
    expect(result).toBe("AAA\nBBB\nCCC\nDDD\n\nInserted\n");
  });
});

// ---------------------------------------------------------------------------
// buildSuggestionChange — section-aware (2+ blank lines = section delimiter)
// ---------------------------------------------------------------------------
describe("section boundaries", () => {
  test("inserting between sections preserves section delimiter", () => {
    const doc = "Section one content\n\n\nSection two content";
    // Anchor in first section — blank line is paragraph boundary
    const result = applyChange(doc, { from: 0, to: 11 }, "Added");
    expect(result).toBe("Section one content\n\nAdded\n\n\n\nSection two content");
  });

  test("anchor on line before section break", () => {
    const doc = "Paragraph A\n\n\nParagraph B";
    const result = applyChange(doc, { from: 0, to: 11 }, "Note");
    expect(result).toBe("Paragraph A\n\nNote\n\n\n\nParagraph B");
  });
});

// ---------------------------------------------------------------------------
// End-to-end with EditorView dispatch
// ---------------------------------------------------------------------------
describe("end-to-end with EditorView.dispatch", () => {
  let view;

  function createView(doc) {
    if (view && !view.destroyed) view.destroy();
    view = new EditorView({
      state: EditorState.create({ doc }),
      parent: document.createElement("div"),
    });
    return view;
  }

  beforeEach(() => {
    if (view && !view.destroyed) view.destroy();
  });

  test("dispatching the change produces correct document", () => {
    // Two paragraphs separated by blank line
    const v = createView("Hello world\n\nSecond line");
    const range = { from: 0, to: 5 }; // "Hello"
    const change = buildSuggestionChange(v.state, range, "Suggestion");
    v.dispatch({ changes: change });
    expect(v.state.doc.toString()).toBe("Hello world\n\nSuggestion\n\n\nSecond line");
  });

  test("insertion in single-paragraph doc appends to end", () => {
    const v = createView("Content here\nMore content");
    const range = { from: 0, to: 7 }; // "Content"
    const change = buildSuggestionChange(v.state, range, "Added");
    v.dispatch({ changes: change });
    // No blank lines → one paragraph → inserts at end
    expect(v.state.doc.toString()).toBe("Content here\nMore content\n\nAdded\n");
  });

  test("resolveAnchorRange + buildSuggestionChange integration", () => {
    const doc = "The problem is complex.\nWe need better tools.\n\nConclusion follows.";
    const v = createView(doc);
    const range = resolveAnchorRange(v.state, [], {
      external_id: "c1",
      anchor_text: "better tools",
    });
    expect(range).toEqual({ from: 32, to: 44 });

    const change = buildSuggestionChange(v.state, range, "Try tool X.");
    v.dispatch({ changes: change });

    // "better tools" is in first paragraph, blank line separates from "Conclusion"
    expect(v.state.doc.toString()).toBe(
      "The problem is complex.\nWe need better tools.\n\nTry tool X.\n\n\nConclusion follows."
    );
  });

  test("long multi-paragraph suggestion does not corrupt surrounding text", () => {
    const original =
      "Introduction paragraph.\n\nMain body of the document with details.\n\nConclusion.";
    const v = createView(original);
    const range = resolveAnchorRange(v.state, [], {
      external_id: "c1",
      anchor_text: "Main body",
    });
    const suggestion =
      "Additional context:\n\n- Point one\n- Point two\n\nSee also: [link](https://example.com)";
    const change = buildSuggestionChange(v.state, range, suggestion);
    v.dispatch({ changes: change });

    const result = v.state.doc.toString();
    // Introduction untouched
    expect(result).toContain("Introduction paragraph.");
    // Main body line intact (not split)
    expect(result).toContain("Main body of the document with details.");
    // Suggestion inserted after main body paragraph, before conclusion
    expect(result).toContain("- Point one\n- Point two");
    // Conclusion still present
    expect(result).toContain("Conclusion.");
    // Suggestion is between main body and conclusion
    const mainBodyIdx = result.indexOf("Main body");
    const suggestionIdx = result.indexOf("Additional context:");
    const conclusionIdx = result.indexOf("Conclusion.");
    expect(suggestionIdx).toBeGreaterThan(mainBodyIdx);
    expect(conclusionIdx).toBeGreaterThan(suggestionIdx);
  });
});
