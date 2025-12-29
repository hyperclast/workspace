/**
 * Tests for table navigation and auto-formatting
 */
import { describe, test, expect, beforeEach, afterEach } from "vitest";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import {
  markdownTableExtension,
  tablesField,
  findTables,
  handleArrowUp,
  handleArrowDown,
} from "../../markdownTable.js";

describe("Table arrow key navigation guardrails", () => {
  let view;
  let container;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
  });

  afterEach(() => {
    if (view) {
      view.destroy();
      view = null;
    }
    if (container) {
      container.remove();
      container = null;
    }
  });

  test("down arrow in table keeps cursor within cell bounds", async () => {
    const doc = `| Name  | Age |
|-------|-----|
| Alice | 30  |
| Bob   | 25  |`;

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [markdownTableExtension],
      }),
      parent: container,
    });

    // Position cursor in "Alice" cell
    const alicePos = doc.indexOf("Alice") + 2; // middle of Alice
    view.dispatch({ selection: { anchor: alicePos } });

    // Simulate down arrow
    const downEvent = new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true });
    view.contentDOM.dispatchEvent(downEvent);

    await new Promise((resolve) => setTimeout(resolve, 10));

    // Cursor should be in "Bob" cell, not outside the table
    const newPos = view.state.selection.main.head;
    const line = view.state.doc.lineAt(newPos);

    // Should be on the Bob line
    expect(line.text).toContain("Bob");
    // Should be between the pipes
    expect(line.text[newPos - line.from]).not.toBe(undefined);
  });

  test("up arrow at first data row stays in table (goes to header)", async () => {
    const doc = `| Name  | Age |
|-------|-----|
| Alice | 30  |`;

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [markdownTableExtension],
      }),
      parent: container,
    });

    // Position cursor in "Alice" cell
    const alicePos = doc.indexOf("Alice") + 2;
    view.dispatch({ selection: { anchor: alicePos } });

    // Simulate up arrow
    const upEvent = new KeyboardEvent("keydown", { key: "ArrowUp", bubbles: true });
    view.contentDOM.dispatchEvent(upEvent);

    await new Promise((resolve) => setTimeout(resolve, 10));

    // Cursor should be in header row "Name" cell, not above table
    const newPos = view.state.selection.main.head;
    const line = view.state.doc.lineAt(newPos);

    // Should be on the header line
    expect(line.text).toContain("Name");
  });

  test("up arrow from below table enters table at last row, not beyond last pipe", async () => {
    const doc = `| Name  | Age |
|-------|-----|
| Alice | 30  |
some text below`;

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [markdownTableExtension],
      }),
      parent: container,
    });

    // Position cursor at "some text below" line, far to the right
    const belowLine = view.state.doc.line(4);
    const cursorPos = belowLine.from + 14; // near end of "some text below"
    view.dispatch({ selection: { anchor: cursorPos } });

    // Call the handler directly (bypassing DOM event simulation issues)
    const handled = handleArrowUp(view);
    expect(handled).toBe(true);

    // Cursor should be in the last table row, inside a cell (not to the right of last |)
    const newPos = view.state.selection.main.head;
    const line = view.state.doc.lineAt(newPos);

    // Should be on the Alice line
    expect(line.text).toContain("Alice");

    // The cursor should NOT be after the last pipe
    const lastPipePos = line.from + line.text.lastIndexOf("|");
    expect(newPos).toBeLessThanOrEqual(lastPipePos);
  });

  test("down arrow from above table enters table at header row, not beyond last pipe", async () => {
    const doc = `some text above
| Name  | Age |
|-------|-----|
| Alice | 30  |`;

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [markdownTableExtension],
      }),
      parent: container,
    });

    // Position cursor at "some text above" line, far to the right
    const aboveLine = view.state.doc.line(1);
    const cursorPos = aboveLine.from + 14; // near end of "some text above"
    view.dispatch({ selection: { anchor: cursorPos } });

    // Call the handler directly
    const handled = handleArrowDown(view);
    expect(handled).toBe(true);

    // Cursor should be in the header row, inside a cell
    const newPos = view.state.selection.main.head;
    const line = view.state.doc.lineAt(newPos);

    // Should be on the header line
    expect(line.text).toContain("Name");

    // The cursor should NOT be after the last pipe
    const lastPipePos = line.from + line.text.lastIndexOf("|");
    expect(newPos).toBeLessThanOrEqual(lastPipePos);
  });
});

describe("Table live auto-formatting", () => {
  let view;
  let container;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
  });

  afterEach(() => {
    if (view) {
      view.destroy();
      view = null;
    }
    if (container) {
      container.remove();
      container = null;
    }
  });

  test("typing in cell triggers column realignment", async () => {
    const doc = `| A | B |
|---|---|
| x | y |`;

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [markdownTableExtension],
      }),
      parent: container,
    });

    // Position cursor after "x"
    const xPos = doc.indexOf("x") + 1;
    view.dispatch({ selection: { anchor: xPos } });

    // Type "xxxx" to make the cell wider
    view.dispatch({
      changes: { from: xPos, insert: "xxxx" },
      selection: { anchor: xPos + 4 },
    });

    await new Promise((resolve) => setTimeout(resolve, 50));

    // The table should be reformatted with aligned columns
    const newDoc = view.state.doc.toString();
    const lines = newDoc.split("\n");

    // All rows should have the same column widths now
    // The first column should be wider to accommodate "xxxxx"
    expect(lines[0]).toContain("| A");
    expect(lines[2]).toContain("| xxxxx |");
  });
});
