import { describe, it, expect } from "vitest";
import { EditorState, EditorSelection } from "@codemirror/state";
import { EditorView } from "@codemirror/view";

import { smartHomePosition, cursorSmartHomeLeft, selectSmartHomeLeft } from "../smartHomeKeymap.js";

describe("smartHomePosition", () => {
  const cases = [
    ["plain text", "hello world", 0],
    ["empty line", "", 0],
    ["leading whitespace only", "    foo", 4],
    ["bullet (-)", "- whatever", 2],
    ["bullet (*)", "* whatever", 2],
    ["bullet (+)", "+ whatever", 2],
    ["indented bullet", "  - whatever", 4],
    ["bullet with checkbox unchecked", "- [ ] task", 6],
    ["bullet with checkbox checked", "- [x] task", 6],
    ["bullet with checkbox uppercase", "- [X] task", 6],
    ["numbered list 1.", "1. whatever", 3],
    ["numbered list 12.", "12. whatever", 4],
    ["h1", "# whatever", 2],
    ["h3", "### whatever", 4],
    ["h6", "###### whatever", 7],
    ["blockquote", "> whatever", 2],
    ["nested blockquote", "> > whatever", 4],
    ["blockquote + bullet", "> - whatever", 4],
    ["dash without space (not a bullet)", "-whatever", 0],
    ["heading without space (not a heading)", "#whatever", 0],
    ["only marker no content", "### ", 4],
    ["only whitespace", "    ", 4],
    ["tab indent", "\t- foo", 3],
  ];

  for (const [name, input, expected] of cases) {
    it(name, () => {
      expect(smartHomePosition(input)).toBe(expected);
    });
  }
});

function makeView(doc, anchor) {
  return new EditorView({
    state: EditorState.create({
      doc,
      selection: EditorSelection.cursor(anchor),
    }),
  });
}

describe("cursorSmartHomeLeft", () => {
  it("moves cursor past bullet on `- foo`", () => {
    const view = makeView("- foo", 5);
    const handled = cursorSmartHomeLeft(view);
    expect(handled).toBe(true);
    expect(view.state.selection.main.head).toBe(2);
    expect(view.state.selection.main.anchor).toBe(2);
    view.destroy();
  });

  it("moves cursor past `### ` on heading", () => {
    const view = makeView("### foo", 7);
    cursorSmartHomeLeft(view);
    expect(view.state.selection.main.head).toBe(4);
    view.destroy();
  });

  it("respects line offset on multiline doc", () => {
    const doc = "first line\n- bullet here";
    const view = makeView(doc, doc.length);
    cursorSmartHomeLeft(view);
    // line 2 starts at 11 ("first line\n" = 11 chars), prefix `- ` is 2 chars
    expect(view.state.selection.main.head).toBe(13);
    view.destroy();
  });

  it("goes to position 0 on plain text line", () => {
    const view = makeView("plain text", 5);
    cursorSmartHomeLeft(view);
    expect(view.state.selection.main.head).toBe(0);
    view.destroy();
  });

  it("stays at smart-home position when already there", () => {
    const view = makeView("- foo", 2);
    cursorSmartHomeLeft(view);
    expect(view.state.selection.main.head).toBe(2);
    view.destroy();
  });

  it("collapses selection to cursor", () => {
    const view = new EditorView({
      state: EditorState.create({
        doc: "- foo bar",
        selection: EditorSelection.range(3, 9),
      }),
    });
    cursorSmartHomeLeft(view);
    const { head, anchor } = view.state.selection.main;
    expect(head).toBe(2);
    expect(anchor).toBe(2);
    view.destroy();
  });
});

describe("selectSmartHomeLeft", () => {
  it("extends selection from cursor to smart-home position", () => {
    const view = makeView("- foo bar", 9);
    selectSmartHomeLeft(view);
    const { head, anchor } = view.state.selection.main;
    expect(head).toBe(2);
    expect(anchor).toBe(9);
    view.destroy();
  });

  it("preserves anchor when extending from existing selection", () => {
    const view = new EditorView({
      state: EditorState.create({
        doc: "### heading text",
        selection: EditorSelection.range(4, 12),
      }),
    });
    selectSmartHomeLeft(view);
    const { head, anchor } = view.state.selection.main;
    expect(anchor).toBe(4);
    expect(head).toBe(4);
    view.destroy();
  });
});
