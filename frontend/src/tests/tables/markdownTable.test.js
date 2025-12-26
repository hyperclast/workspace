/**
 * Tests for the new markdownTable.js extension
 */
import { describe, test, expect, beforeEach, afterEach } from "vitest";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import {
  findTables,
  findTableAtPos,
  findCellAtPos,
  findTableRanges,
  isInsideTable,
  generateTable,
  markdownTableExtension,
  tablesField,
} from "../../markdownTable.js";

// ============================================================================
// Table Detection Tests
// ============================================================================

describe("findTables", () => {
  function createState(doc) {
    return EditorState.create({
      doc,
      extensions: [tablesField],
    });
  }

  test("finds a simple table", () => {
    const state = createState(`| Name | Age |
|------|-----|
| Alice | 30 |`);

    const tables = findTables(state);
    expect(tables).toHaveLength(1);
    expect(tables[0].rows).toHaveLength(3);
    expect(tables[0].rows[0].type).toBe("header");
    expect(tables[0].rows[1].type).toBe("separator");
    expect(tables[0].rows[2].type).toBe("data");
  });

  test("parses header cells correctly", () => {
    const state = createState(`| Name | Age | City |
|------|-----|------|
| Alice | 30 | NYC |`);

    const tables = findTables(state);
    const headerRow = tables[0].rows[0];

    expect(headerRow.cells).toHaveLength(3);
    expect(headerRow.cells[0].content).toBe("Name");
    expect(headerRow.cells[1].content).toBe("Age");
    expect(headerRow.cells[2].content).toBe("City");
  });

  test("parses data cells correctly", () => {
    const state = createState(`| Name | Age |
|------|-----|
| Alice | 30 |
| Bob | 25 |`);

    const tables = findTables(state);
    expect(tables[0].rows).toHaveLength(4);

    const dataRow1 = tables[0].rows[2];
    expect(dataRow1.cells[0].content).toBe("Alice");
    expect(dataRow1.cells[1].content).toBe("30");

    const dataRow2 = tables[0].rows[3];
    expect(dataRow2.cells[0].content).toBe("Bob");
    expect(dataRow2.cells[1].content).toBe("25");
  });

  test("detects alignment from separator row", () => {
    const state = createState(`| Left | Center | Right |
|:-----|:------:|------:|
| A | B | C |`);

    const tables = findTables(state);
    expect(tables[0].alignments).toEqual(["left", "center", "right"]);
  });

  test("finds multiple tables in document", () => {
    const state = createState(`Some text

| Table 1 |
|---------|
| Data 1 |

More text

| Table 2 |
|---------|
| Data 2 |`);

    const tables = findTables(state);
    expect(tables).toHaveLength(2);
  });

  test("ignores non-table content", () => {
    const state = createState(`Just some text
with multiple lines
but no tables`);

    const tables = findTables(state);
    expect(tables).toHaveLength(0);
  });

  test("requires separator row to identify table", () => {
    const state = createState(`| Not a table |
| Because no separator |`);

    const tables = findTables(state);
    expect(tables).toHaveLength(0);
  });

  test("handles table at end of document", () => {
    const state = createState(`Some text

| Name |
|------|
| End |`);

    const tables = findTables(state);
    expect(tables).toHaveLength(1);
  });

  test("handles table at start of document", () => {
    const state = createState(`| Name |
|------|
| Start |

Some text after`);

    const tables = findTables(state);
    expect(tables).toHaveLength(1);
    expect(tables[0].from).toBe(0);
  });

  test("stops table at non-table line", () => {
    const state = createState(`| Name |
|------|
| Data |
This is not a table row
| More data |`);

    const tables = findTables(state);
    expect(tables).toHaveLength(1);
    expect(tables[0].rows).toHaveLength(3);
  });

  test("handles empty cells", () => {
    const state = createState(`| A | B | C |
|---|---|---|
|   |   |   |`);

    const tables = findTables(state);
    const dataRow = tables[0].rows[2];
    expect(dataRow.cells[0].content).toBe("");
    expect(dataRow.cells[1].content).toBe("");
    expect(dataRow.cells[2].content).toBe("");
  });

  test("calculates correct cell positions", () => {
    const state = createState(`| Name | Age |
|------|-----|
| Alice | 30 |`);

    const tables = findTables(state);
    const dataRow = tables[0].rows[2];

    // Check that cell positions point to actual content
    const doc = state.doc;
    const nameCell = dataRow.cells[0];
    const ageCell = dataRow.cells[1];

    expect(doc.sliceString(nameCell.contentFrom, nameCell.contentTo)).toBe("Alice");
    expect(doc.sliceString(ageCell.contentFrom, ageCell.contentTo)).toBe("30");
  });
});

// ============================================================================
// Cell Finding Tests
// ============================================================================

describe("findTableAtPos", () => {
  test("finds table containing position", () => {
    const state = EditorState.create({
      doc: `Text before

| Name |
|------|
| Data |

Text after`,
      extensions: [tablesField],
    });

    const tables = findTables(state);
    const tableStart = state.doc.toString().indexOf("| Name |");

    expect(findTableAtPos(tables, tableStart)).toBe(tables[0]);
    expect(findTableAtPos(tables, 0)).toBeUndefined();
  });
});

describe("findCellAtPos", () => {
  test("finds cell at cursor position", () => {
    const state = EditorState.create({
      doc: `| Name | Age |
|------|-----|
| Alice | 30 |`,
      extensions: [tablesField],
    });

    const tables = findTables(state);
    const table = tables[0];

    // Find position in "Alice" cell
    const alicePos = state.doc.toString().indexOf("Alice");
    const found = findCellAtPos(table, alicePos);

    expect(found).not.toBeNull();
    expect(found.cell.content).toBe("Alice");
    expect(found.row.type).toBe("data");
  });
});

// ============================================================================
// Table Range Helpers (for compatibility)
// ============================================================================

describe("findTableRanges", () => {
  test("finds table ranges in raw text", () => {
    const text = `Some text

| Name |
|------|
| Data |

More text`;

    const ranges = findTableRanges(text);
    expect(ranges).toHaveLength(1);
    expect(ranges[0].from).toBeGreaterThan(0);
    expect(ranges[0].to).toBeGreaterThan(ranges[0].from);
  });

  test("returns empty array for no tables", () => {
    const text = "Just some text\nwith no tables";
    const ranges = findTableRanges(text);
    expect(ranges).toHaveLength(0);
  });
});

describe("isInsideTable", () => {
  test("returns true for position inside table", () => {
    const text = `Text

| Name |
|------|
| Data |`;

    const ranges = findTableRanges(text);
    const tableStart = text.indexOf("| Name |");

    expect(isInsideTable(tableStart, ranges)).toBe(true);
    expect(isInsideTable(tableStart + 5, ranges)).toBe(true);
  });

  test("returns false for position outside table", () => {
    const text = `Text before

| Name |
|------|
| Data |

Text after`;

    const ranges = findTableRanges(text);

    expect(isInsideTable(0, ranges)).toBe(false);
    expect(isInsideTable(text.length - 1, ranges)).toBe(false);
  });
});

// ============================================================================
// Table Generation Tests
// ============================================================================

describe("generateTable", () => {
  test("generates table with correct structure", () => {
    const table = generateTable(2, 3);
    const lines = table.split("\n");

    expect(lines).toHaveLength(4); // header + separator + 2 data rows
    expect(lines[0]).toMatch(/^\|.*\|$/);
    expect(lines[1]).toMatch(/^\|.*-.*\|$/);
  });

  test("generates correct number of columns", () => {
    const table = generateTable(1, 4);
    const headerLine = table.split("\n")[0];
    const pipes = (headerLine.match(/\|/g) || []).length;

    expect(pipes).toBe(5); // 4 columns = 5 pipes
  });

  test("generates correct number of rows", () => {
    const table = generateTable(5, 2);
    const lines = table.split("\n");

    expect(lines).toHaveLength(7); // header + separator + 5 data rows
  });

  test("generated table has valid header labels", () => {
    const table = generateTable(1, 3);

    expect(table).toContain("Header 1");
    expect(table).toContain("Header 2");
    expect(table).toContain("Header 3");
  });

  test("generated table can be parsed", () => {
    const table = generateTable(2, 3);
    const state = EditorState.create({
      doc: table,
      extensions: [tablesField],
    });

    const tables = findTables(state);
    expect(tables).toHaveLength(1);
    expect(tables[0].rows).toHaveLength(4); // header + sep + 2 data
    expect(tables[0].alignments).toHaveLength(3);
  });
});

// ============================================================================
// Extension Integration Tests
// ============================================================================

describe("markdownTableExtension integration", () => {
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

  test("extension loads without errors", () => {
    expect(() => {
      view = new EditorView({
        state: EditorState.create({
          doc: "Hello world",
          extensions: [markdownTableExtension],
        }),
        parent: container,
      });
    }).not.toThrow();
  });

  test("tables field is accessible from state", () => {
    view = new EditorView({
      state: EditorState.create({
        doc: `| Name |
|------|
| Data |`,
        extensions: [markdownTableExtension],
      }),
      parent: container,
    });

    const tables = view.state.field(tablesField);
    expect(tables).toHaveLength(1);
  });

  test("decorations are applied to table lines", () => {
    view = new EditorView({
      state: EditorState.create({
        doc: `| Name |
|------|
| Data |`,
        extensions: [markdownTableExtension],
      }),
      parent: container,
    });

    // Check that decoration classes are applied
    const headerLine = view.dom.querySelector(".cm-table-header");
    const separatorLine = view.dom.querySelector(".cm-table-separator");
    const dataLine = view.dom.querySelector(".cm-table-row");

    expect(headerLine).not.toBeNull();
    expect(separatorLine).not.toBeNull();
    expect(dataLine).not.toBeNull();
  });

  test("pipe characters are decorated", () => {
    view = new EditorView({
      state: EditorState.create({
        doc: `| Name |
|------|
| Data |`,
        extensions: [markdownTableExtension],
      }),
      parent: container,
    });

    const pipes = view.dom.querySelectorAll(".cm-table-pipe");
    expect(pipes.length).toBeGreaterThan(0);
  });
});

// ============================================================================
// Alignment Parsing Tests
// ============================================================================

describe("alignment parsing", () => {
  function getAlignments(doc) {
    const state = EditorState.create({
      doc,
      extensions: [tablesField],
    });
    const tables = findTables(state);
    return tables[0]?.alignments || [];
  }

  test("default alignment is left", () => {
    const alignments = getAlignments(`| Col |
|-----|
| Data |`);

    expect(alignments).toEqual(["left"]);
  });

  test("colon on left means left align", () => {
    const alignments = getAlignments(`| Col |
|:----|
| Data |`);

    expect(alignments).toEqual(["left"]);
  });

  test("colon on right means right align", () => {
    const alignments = getAlignments(`| Col |
|----:|
| Data |`);

    expect(alignments).toEqual(["right"]);
  });

  test("colons on both sides means center align", () => {
    const alignments = getAlignments(`| Col |
|:---:|
| Data |`);

    expect(alignments).toEqual(["center"]);
  });

  test("mixed alignments", () => {
    const alignments = getAlignments(`| Left | Center | Right | Default |
|:-----|:------:|------:|---------|
| A | B | C | D |`);

    expect(alignments).toEqual(["left", "center", "right", "left"]);
  });
});

// ============================================================================
// Edge Cases
// ============================================================================

describe("edge cases", () => {
  test("handles table with only header and separator", () => {
    const state = EditorState.create({
      doc: `| Header |
|--------|`,
      extensions: [tablesField],
    });

    const tables = findTables(state);
    expect(tables).toHaveLength(1);
    expect(tables[0].rows).toHaveLength(2);
  });

  test("handles table with many columns", () => {
    const state = EditorState.create({
      doc: `| A | B | C | D | E | F | G | H |
|---|---|---|---|---|---|---|---|
| 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |`,
      extensions: [tablesField],
    });

    const tables = findTables(state);
    expect(tables[0].alignments).toHaveLength(8);
    expect(tables[0].rows[0].cells).toHaveLength(8);
  });

  test("handles table with very long cell content", () => {
    const longContent = "A".repeat(100);
    const state = EditorState.create({
      doc: `| ${longContent} |
|${"-".repeat(102)}|
| Data |`,
      extensions: [tablesField],
    });

    const tables = findTables(state);
    expect(tables).toHaveLength(1);
    expect(tables[0].rows[0].cells[0].content).toBe(longContent);
  });

  test("handles special characters in cells", () => {
    const state = EditorState.create({
      doc: `| Special |
|---------|
| <>&"' |`,
      extensions: [tablesField],
    });

    const tables = findTables(state);
    expect(tables[0].rows[2].cells[0].content).toBe("<>&\"'");
  });

  test("handles unicode in cells", () => {
    const state = EditorState.create({
      doc: `| 日本語 | Émoji |
|--------|-------|
| こんにちは | 🎉🚀 |`,
      extensions: [tablesField],
    });

    const tables = findTables(state);
    expect(tables[0].rows[0].cells[0].content).toBe("日本語");
    expect(tables[0].rows[2].cells[1].content).toBe("🎉🚀");
  });
});
