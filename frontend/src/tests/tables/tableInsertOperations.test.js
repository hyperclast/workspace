import { describe, it, expect } from "vitest";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { markdownTableExtension, tablesField, formatTable } from "../../markdownTable.js";

function createEditorWithTable(tableText) {
  const state = EditorState.create({
    doc: tableText,
    extensions: [markdownTableExtension],
  });
  return new EditorView({ state });
}

function setCursor(view, pos) {
  view.dispatch({ selection: { anchor: pos } });
}

function getCursorPos(view) {
  return view.state.selection.main.head;
}

function getDocText(view) {
  return view.state.doc.toString();
}

function findCellAtPosInTable(table, pos) {
  for (let rowIndex = 0; rowIndex < table.rows.length; rowIndex++) {
    const row = table.rows[rowIndex];
    for (const cell of row.cells) {
      if (pos >= cell.from && pos <= cell.to) {
        return { row, cell, rowIndex };
      }
    }
  }
  return null;
}

function calculateColumnWidths(table) {
  const numCols = table.alignments.length;
  const colWidths = new Array(numCols).fill(3);
  for (const row of table.rows) {
    if (row.type === "separator") continue;
    for (let i = 0; i < row.cells.length && i < numCols; i++) {
      colWidths[i] = Math.max(colWidths[i], row.cells[i].content.length);
    }
  }
  return colWidths;
}

function simulateInsertRowBelow(view) {
  const tables = view.state.field(tablesField);
  const pos = view.state.selection.main.head;
  const table = tables.find((t) => pos >= t.from && pos <= t.to);
  if (!table) return false;

  const found = findCellAtPosInTable(table, pos);
  if (!found) return false;

  const { row, cell } = found;
  const colIndex = cell.colIndex;

  let insertAfterRow = row;
  let targetRowIndexAfterInsert;

  if (row.type === "header" || row.type === "separator") {
    const separatorRow = table.rows.find((r) => r.type === "separator");
    if (!separatorRow) return false;
    insertAfterRow = separatorRow;
    targetRowIndexAfterInsert = table.rows.indexOf(separatorRow) + 1;
  } else {
    targetRowIndexAfterInsert = found.rowIndex + 1;
  }

  const colWidths = calculateColumnWidths(table);
  const newRowCells = colWidths.map((w) => " ".repeat(w));
  const newRowText = "| " + newRowCells.join(" | ") + " |";

  view.dispatch({
    changes: { from: insertAfterRow.to, insert: "\n" + newRowText },
  });

  return { found, table, targetRowIndexAfterInsert, colIndex };
}

function simulateInsertColumnRight(view) {
  const tables = view.state.field(tablesField);
  const pos = view.state.selection.main.head;
  const table = tables.find((t) => pos >= t.from && pos <= t.to);
  if (!table) return false;

  const found = findCellAtPosInTable(table, pos);
  if (!found) return false;

  const colIndex = found.cell.colIndex;
  const changes = [];

  for (const row of table.rows) {
    const cells = row.cells.map((c) => c.content);
    const newContent = row.type === "separator" ? "---" : "";
    cells.splice(colIndex + 1, 0, newContent);

    const newLine = "| " + cells.join(" | ") + " |";
    changes.push({ from: row.from, to: row.to, insert: newLine });
  }

  view.dispatch({ changes });
  return { found, table, colIndex };
}

describe("insertRowBelow - from header row", () => {
  it("should insert row AFTER separator when called from header", () => {
    const table = `| Header 1 | Header 2 |
| :------- | :------- |
| Data 1   | Data 2   |`;

    const view = createEditorWithTable(table);

    const headerStart = table.indexOf("Header 1");
    setCursor(view, headerStart);

    const result = simulateInsertRowBelow(view);
    const newDoc = getDocText(view);

    console.log("After inserting from header row:");
    console.log(newDoc);

    const lines = newDoc.split("\n");

    expect(lines.length).toBe(4);
    expect(lines[0]).toContain("Header 1");
    expect(lines[1]).toMatch(/^[\|\:\-\s]+$/);
    expect(lines[2]).toMatch(/^\|[\s\|]+\|$/);
    expect(lines[3]).toContain("Data 1");
  });
});

describe("insertRowBelow - from data row", () => {
  it("should insert row directly after current data row", () => {
    const table = `| Header 1 | Header 2 |
| :------- | :------- |
| Data 1   | Data 2   |`;

    const view = createEditorWithTable(table);

    const data1Start = table.indexOf("Data 1");
    setCursor(view, data1Start);

    simulateInsertRowBelow(view);
    const newDoc = getDocText(view);

    console.log("After inserting from data row:");
    console.log(newDoc);

    const lines = newDoc.split("\n");

    expect(lines.length).toBe(4);
    expect(lines[2]).toContain("Data 1");
    expect(lines[3]).toMatch(/^\|[\s\|]+\|$/);
  });
});

describe("insertColumnRight - separator integrity", () => {
  it("should produce valid separator after column insert and format", () => {
    const table = `| Header 1 | Header 2 |
| :------- | :------- |
| Data 1   | Data 2   |`;

    const view = createEditorWithTable(table);

    const data1Start = table.indexOf("Data 1");
    setCursor(view, data1Start);

    simulateInsertColumnRight(view);

    const newTables = view.state.field(tablesField);
    if (newTables.length > 0) {
      formatTable(view, newTables[0]);
    }

    const formattedDoc = getDocText(view);
    console.log("After column insert + format:");
    console.log(formattedDoc);

    const lines = formattedDoc.split("\n");
    const separatorLine = lines[1];

    expect(separatorLine).toMatch(/^[\|\:\-\s]+$/);
    expect(separatorLine).not.toContain("Header");
    expect(separatorLine).not.toContain("Data");

    const pipeCounts = lines.map((line) => (line.match(/\|/g) || []).length);
    expect(new Set(pipeCounts).size).toBe(1);
  });
});

describe("cursor positioning after operations", () => {
  it("should position cursor in new row after insertRowBelow", async () => {
    const table = `| Header 1 | Header 2 |
| :------- | :------- |
| Data 1   | Data 2   |`;

    const view = createEditorWithTable(table);

    const data1Start = table.indexOf("Data 1");
    setCursor(view, data1Start + 2);

    const result = simulateInsertRowBelow(view);

    await new Promise((r) => setTimeout(r, 50));

    const newTable = view.state.field(tablesField)[0];
    if (newTable && result.targetRowIndexAfterInsert < newTable.rows.length) {
      const targetRow = newTable.rows[result.targetRowIndexAfterInsert];
      if (targetRow && targetRow.cells[result.colIndex]) {
        view.dispatch({ selection: { anchor: targetRow.cells[result.colIndex].from } });
      }
    }

    await new Promise((r) => setTimeout(r, 10));

    const finalCursor = getCursorPos(view);
    const doc = getDocText(view);
    const lines = doc.split("\n");

    console.log("Final doc:", doc);
    console.log("Final cursor position:", finalCursor);

    const headerLineEnd = lines[0].length;
    expect(finalCursor).toBeGreaterThan(headerLineEnd);

    const cursorLine = view.state.doc.lineAt(finalCursor).number;
    console.log("Cursor is on line:", cursorLine);

    expect(cursorLine).toBeGreaterThan(2);
  });
});
