/**
 * Markdown Table Extension for CodeMirror 6
 *
 * Option A: Live Preview (Styled Markdown)
 * - Tables remain as editable markdown text
 * - Visual decorations make them look like tables
 * - Tab navigation between cells
 * - Auto-formatting on Tab (aligns columns)
 */

import { Prec, StateField } from "@codemirror/state";
import { Decoration, keymap, ViewPlugin } from "@codemirror/view";
import { TABLE_SCAN_LIMIT_LINES } from "./config/performance.js";

// ============================================================================
// Table Detection & Parsing
// ============================================================================

/**
 * Represents a parsed markdown table
 * @typedef {Object} Table
 * @property {number} from - Start position in document
 * @property {number} to - End position in document
 * @property {number} startLine - First line number
 * @property {number} endLine - Last line number
 * @property {TableRow[]} rows - All rows (header, separator, data)
 * @property {string[]} alignments - Per-column alignment ('left'|'center'|'right')
 */

/**
 * Represents a row in a table
 * @typedef {Object} TableRow
 * @property {number} line - Line number in document
 * @property {number} from - Start position of line
 * @property {number} to - End position of line
 * @property {TableCell[]} cells - Cells in this row
 * @property {'header'|'separator'|'data'} type - Row type
 */

/**
 * Represents a cell in a table row
 * @typedef {Object} TableCell
 * @property {number} from - Start position (content start, after | and space)
 * @property {number} to - End position (content end, before space and |)
 * @property {number} contentFrom - Start of actual content (trimmed)
 * @property {number} contentTo - End of actual content (trimmed)
 * @property {string} content - Cell text (trimmed)
 * @property {number} colIndex - Column index (0-based)
 */

const TABLE_LINE_REGEX = /^\s*\|.*\|\s*$/;
const SEPARATOR_REGEX = /^\s*\|[\s\-:|]+\|\s*$/;
const SEPARATOR_CELL_REGEX = /^:?-+:?$/;

/**
 * Check if a line looks like a table row
 */
function isTableLine(line) {
  return TABLE_LINE_REGEX.test(line);
}

/**
 * Check if a line is a separator row (|---|---|)
 */
function isSeparatorLine(line) {
  if (!SEPARATOR_REGEX.test(line)) return false;
  const cells = parseRowCells(line, 0, 0);
  return cells.every((cell) => SEPARATOR_CELL_REGEX.test(cell.content.trim()));
}

/**
 * Parse alignment from separator cell
 */
function parseAlignment(cell) {
  const content = cell.trim();
  const startsColon = content.startsWith(":");
  const endsColon = content.endsWith(":");
  if (startsColon && endsColon) return "center";
  if (endsColon) return "right";
  return "left";
}

/**
 * Parse cells from a table row line
 * @param {string} lineText - The line text
 * @param {number} lineStart - Document position where line starts
 * @param {number} lineNumber - Line number in document
 * @returns {TableCell[]}
 */
function parseRowCells(lineText, lineStart, lineNumber) {
  const cells = [];
  let pos = 0;
  let colIndex = 0;

  // Skip leading whitespace
  while (pos < lineText.length && lineText[pos] === " ") pos++;

  // Skip opening pipe
  if (lineText[pos] === "|") pos++;

  while (pos < lineText.length) {
    const cellStart = pos;
    let cellEnd = pos;

    // Find the next pipe (end of cell)
    while (cellEnd < lineText.length && lineText[cellEnd] !== "|") {
      cellEnd++;
    }

    // We found a cell
    if (cellEnd > cellStart || lineText[cellEnd] === "|") {
      const rawContent = lineText.slice(cellStart, cellEnd);
      const trimmedContent = rawContent.trim();

      // Calculate content positions (trimmed)
      const leadingSpaces = rawContent.length - rawContent.trimStart().length;
      const trailingSpaces = rawContent.length - rawContent.trimEnd().length;

      cells.push({
        from: lineStart + cellStart,
        to: lineStart + cellEnd,
        contentFrom: lineStart + cellStart + leadingSpaces,
        contentTo: lineStart + cellEnd - trailingSpaces,
        content: trimmedContent,
        colIndex: colIndex,
      });

      colIndex++;
    }

    // Move past the pipe
    pos = cellEnd + 1;

    // If we're at the end after a pipe, stop (don't create empty cell)
    if (pos >= lineText.length || lineText.slice(pos).trim() === "") {
      break;
    }
  }

  return cells;
}

/**
 * Find all markdown tables in the document
 * @param {EditorState} state - CodeMirror editor state
 * @returns {Table[]}
 */
export function findTables(state) {
  const doc = state.doc;
  const tables = [];
  let currentTable = null;

  for (let lineNum = 1; lineNum <= doc.lines; lineNum++) {
    const line = doc.line(lineNum);
    const lineText = line.text;

    if (isTableLine(lineText)) {
      if (!currentTable) {
        // Check if next line is a separator (required for valid table)
        const nextLine = lineNum < doc.lines ? doc.line(lineNum + 1) : null;
        if (nextLine && isSeparatorLine(nextLine.text)) {
          // Start a new table
          currentTable = {
            from: line.from,
            to: line.to,
            startLine: lineNum,
            endLine: lineNum,
            rows: [],
            alignments: [],
          };

          // Parse header row
          const headerCells = parseRowCells(lineText, line.from, lineNum);
          currentTable.rows.push({
            line: lineNum,
            from: line.from,
            to: line.to,
            cells: headerCells,
            type: "header",
          });

          // Parse separator row
          const sepCells = parseRowCells(nextLine.text, nextLine.from, lineNum + 1);
          currentTable.rows.push({
            line: lineNum + 1,
            from: nextLine.from,
            to: nextLine.to,
            cells: sepCells,
            type: "separator",
          });

          // Extract alignments
          currentTable.alignments = sepCells.map((cell) => parseAlignment(cell.content));

          currentTable.to = nextLine.to;
          currentTable.endLine = lineNum + 1;

          // Skip the separator line in our iteration
          lineNum++;
        }
      } else {
        // Continue existing table with data row
        const cells = parseRowCells(lineText, line.from, lineNum);
        currentTable.rows.push({
          line: lineNum,
          from: line.from,
          to: line.to,
          cells: cells,
          type: "data",
        });
        currentTable.to = line.to;
        currentTable.endLine = lineNum;
      }
    } else if (currentTable) {
      // Non-table line ends the current table
      if (currentTable.rows.length >= 2) {
        tables.push(currentTable);
      }
      currentTable = null;
    }
  }

  // Don't forget table at end of document
  if (currentTable && currentTable.rows.length >= 2) {
    tables.push(currentTable);
  }

  return tables;
}

/**
 * Find which table (if any) contains the given position
 */
export function findTableAtPos(tables, pos) {
  return tables.find((t) => pos >= t.from && pos <= t.to);
}

/**
 * Find which cell (if any) contains the given position
 */
export function findCellAtPos(table, pos) {
  for (const row of table.rows) {
    for (const cell of row.cells) {
      // Check if position is within this cell's range (including the preceding space)
      if (pos >= cell.from && pos <= cell.to) {
        return { cell, row };
      }
    }
  }
  return null;
}

// ============================================================================
// Efficient Table Finding (Viewport/Position-based)
// ============================================================================

/**
 * Find tables only within a specific line range.
 * This is O(range) instead of O(document).
 * @param {EditorState} state
 * @param {number} fromLine - Start line (1-indexed)
 * @param {number} toLine - End line (1-indexed)
 * @returns {Table[]}
 */
function findTablesInRange(state, fromLine, toLine) {
  const doc = state.doc;
  const tables = [];
  let currentTable = null;

  for (let lineNum = fromLine; lineNum <= toLine && lineNum <= doc.lines; lineNum++) {
    const line = doc.line(lineNum);
    const lineText = line.text;

    if (isTableLine(lineText)) {
      if (!currentTable) {
        const nextLine = lineNum < doc.lines ? doc.line(lineNum + 1) : null;
        if (nextLine && isSeparatorLine(nextLine.text)) {
          currentTable = {
            from: line.from,
            to: line.to,
            startLine: lineNum,
            endLine: lineNum,
            rows: [],
            alignments: [],
          };

          const headerCells = parseRowCells(lineText, line.from, lineNum);
          currentTable.rows.push({
            line: lineNum,
            from: line.from,
            to: line.to,
            cells: headerCells,
            type: "header",
          });

          const sepCells = parseRowCells(nextLine.text, nextLine.from, lineNum + 1);
          currentTable.rows.push({
            line: lineNum + 1,
            from: nextLine.from,
            to: nextLine.to,
            cells: sepCells,
            type: "separator",
          });

          currentTable.alignments = sepCells.map((cell) => parseAlignment(cell.content));
          currentTable.to = nextLine.to;
          currentTable.endLine = lineNum + 1;
          lineNum++;
        }
      } else {
        const dataCells = parseRowCells(lineText, line.from, lineNum);
        currentTable.rows.push({
          line: lineNum,
          from: line.from,
          to: line.to,
          cells: dataCells,
          type: "data",
        });
        currentTable.to = line.to;
        currentTable.endLine = lineNum;
      }
    } else {
      if (currentTable) {
        tables.push(currentTable);
        currentTable = null;
      }
    }
  }

  if (currentTable) {
    tables.push(currentTable);
  }

  return tables;
}

/**
 * Find the table containing a specific position by searching around that position.
 * Much more efficient than scanning the entire document - O(searchRadius) instead of O(n).
 *
 * @param {EditorState} state - The editor state
 * @param {number} pos - Position to search around
 * @returns {Table|null} - The table containing the position, or null if not found
 *
 * @note Search radius limitation: This function searches 100 lines above and
 *       below the given position. Tables spanning more than 200 lines may not
 *       be fully detected if the cursor is in the middle, far from both
 *       the table's start and end boundaries. This is an intentional trade-off
 *       for O(1) performance in large documents. For documents under the
 *       TABLE_SCAN_LIMIT_LINES threshold, the tablesField StateField provides
 *       complete table detection as a fallback.
 */
function findTableAtPosition(state, pos) {
  const doc = state.doc;
  const currentLine = doc.lineAt(pos);
  const lineNum = currentLine.number;

  const searchRadius = 100;
  const fromLine = Math.max(1, lineNum - searchRadius);
  const toLine = Math.min(doc.lines, lineNum + searchRadius);

  const tables = findTablesInRange(state, fromLine, toLine);

  for (const table of tables) {
    if (pos >= table.from && pos <= table.to) {
      return table;
    }
  }

  return null;
}

// tablesField - caches all tables in the document
// For LARGE documents (>10K lines), returns empty to avoid O(n) scan
// Production navigation code uses findTableAtPosition instead

const tablesField = StateField.define({
  create(state) {
    if (state.doc.lines > TABLE_SCAN_LIMIT_LINES) {
      return [];
    }
    return findTables(state);
  },
  update(tables, tr) {
    if (tr.docChanged) {
      if (tr.state.doc.lines > TABLE_SCAN_LIMIT_LINES) {
        return [];
      }
      return findTables(tr.state);
    }
    return tables;
  },
});

// ============================================================================
// Decorations
// ============================================================================

function buildDecorations(state, view) {
  const decorations = [];

  // Only find tables in the visible viewport - O(viewport) not O(document)
  const { from: viewFrom, to: viewTo } = view ? view.viewport : { from: 0, to: state.doc.length };
  const fromLine = state.doc.lineAt(viewFrom).number;
  const toLine = state.doc.lineAt(viewTo).number;
  const tables = findTablesInRange(state, fromLine, toLine);

  for (const table of tables) {
    if (table.to < viewFrom || table.from > viewTo) continue;
    const rowCount = table.rows.length;
    let dataRowIndex = 0;

    for (let rowIndex = 0; rowIndex < rowCount; rowIndex++) {
      const row = table.rows[rowIndex];
      const isFirst = rowIndex === 0;
      const isLast = rowIndex === rowCount - 1;

      const lineText = state.doc.lineAt(row.from).text;
      const firstPipe = lineText.indexOf("|");
      const lastPipe = lineText.lastIndexOf("|");
      const contentStart = row.from + firstPipe;
      const contentEnd = row.from + lastPipe + 1;

      let bgClasses = ["cm-table-bg"];
      switch (row.type) {
        case "header":
          bgClasses.push("cm-table-bg-header");
          break;
        case "separator":
          bgClasses.push("cm-table-bg-separator");
          break;
        case "data":
          bgClasses.push(dataRowIndex % 2 === 0 ? "cm-table-bg-even" : "cm-table-bg-odd");
          dataRowIndex++;
          break;
      }

      if (isFirst) bgClasses.push("cm-table-bg-first");
      if (isLast) bgClasses.push("cm-table-bg-last");

      if (firstPipe >= 0 && lastPipe >= 0) {
        decorations.push(
          Decoration.mark({ class: bgClasses.join(" ") }).range(contentStart, contentEnd)
        );
      }

      let lineClasses = [];
      switch (row.type) {
        case "header":
          lineClasses.push("cm-table-header");
          break;
        case "separator":
          lineClasses.push("cm-table-separator");
          break;
        case "data":
          lineClasses.push("cm-table-row");
          break;
      }

      if (isFirst) lineClasses.push("cm-table-first");
      if (isLast) lineClasses.push("cm-table-last");

      decorations.push(Decoration.line({ class: lineClasses.join(" ") }).range(row.from));

      let pos = row.from;
      const pipePositions = [];
      for (let i = 0; i < lineText.length; i++) {
        if (lineText[i] === "|") {
          pipePositions.push(i);
        }
      }

      for (let j = 0; j < pipePositions.length; j++) {
        const i = pipePositions[j];
        const isOuter = j === 0 || j === pipePositions.length - 1;
        const pipeClass = isOuter ? "cm-table-pipe cm-table-pipe-outer" : "cm-table-pipe";
        decorations.push(Decoration.mark({ class: pipeClass }).range(pos + i, pos + i + 1));
      }

      if (row.type === "separator") {
        for (const cell of row.cells) {
          if (cell.content.length > 0) {
            decorations.push(
              Decoration.mark({ class: "cm-table-separator-dash" }).range(
                cell.contentFrom,
                cell.contentTo
              )
            );
          }
        }
      }
    }
  }

  // Sort decorations by from position, then by whether it's a line decoration
  decorations.sort((a, b) => {
    if (a.from !== b.from) return a.from - b.from;
    // Line decorations (point decorations) should come before range decorations
    const aIsPoint = a.from === a.to;
    const bIsPoint = b.from === b.to;
    if (aIsPoint && !bIsPoint) return -1;
    if (!aIsPoint && bIsPoint) return 1;
    return 0;
  });

  return Decoration.set(decorations);
}

const tableDecorations = ViewPlugin.fromClass(
  class {
    constructor(view) {
      this.decorations = buildDecorations(view.state, view);
    }

    update(update) {
      if (update.docChanged || update.viewportChanged) {
        this.decorations = buildDecorations(update.state, update.view);
      }
    }
  },
  {
    decorations: (v) => v.decorations,
  }
);

// ============================================================================
// Auto-Format (Live + on Cursor Leave)
// ============================================================================

const tableAutoFormat = ViewPlugin.fromClass(
  class {
    constructor(view) {
      this.lastTableFrom = null;
      this.pendingFormat = null;
      this.updateTablePosition(view);
    }

    update(update) {
      const prevTableFrom = this.lastTableFrom;

      if (update.docChanged) {
        // Track table position when document changes
        const pos = update.state.selection.main.head;
        const table = findTableAtPosition(update.state, pos);
        this.lastTableFrom = table ? table.from : null;
      } else if (update.selectionSet) {
        this.updateTablePosition(update.view);

        // If cursor left a table, format it
        if (prevTableFrom !== null && prevTableFrom !== this.lastTableFrom) {
          this.scheduleFormat(update.view, prevTableFrom);
        }
      }
    }

    updateTablePosition(view) {
      const pos = view.state.selection.main.head;
      const table = findTableAtPosition(view.state, pos);
      this.lastTableFrom = table ? table.from : null;
    }

    scheduleFormat(view, tableFrom) {
      if (this.pendingFormat) {
        clearTimeout(this.pendingFormat);
      }

      this.pendingFormat = setTimeout(() => {
        this.pendingFormat = null;
        // Find the table near the original position
        const table = findTableAtPosition(view.state, tableFrom);
        if (table && Math.abs(table.from - tableFrom) < 100) {
          formatTable(view, table);
        }
      }, 0);
    }

    destroy() {
      if (this.pendingFormat) {
        clearTimeout(this.pendingFormat);
      }
    }
  }
);

// ============================================================================
// Tab Navigation
// ============================================================================

/**
 * Get the next cell in the table (for Tab navigation)
 */
function getNextCell(table, currentRow, currentCell, direction = "next") {
  const rowIndex = table.rows.indexOf(currentRow);
  const cellIndex = currentCell.colIndex;
  const numCols = table.alignments.length;

  if (direction === "next") {
    // Try next cell in same row
    if (cellIndex + 1 < numCols) {
      const nextCell = currentRow.cells[cellIndex + 1];
      if (nextCell) return { row: currentRow, cell: nextCell };
    }
    // Try first cell of next row
    for (let r = rowIndex + 1; r < table.rows.length; r++) {
      const nextRow = table.rows[r];
      if (nextRow.type !== "separator" && nextRow.cells.length > 0) {
        return { row: nextRow, cell: nextRow.cells[0] };
      }
    }
    // We're at the end
    return null;
  } else {
    // direction === 'prev'
    // Try previous cell in same row
    if (cellIndex > 0) {
      const prevCell = currentRow.cells[cellIndex - 1];
      if (prevCell) return { row: currentRow, cell: prevCell };
    }
    // Try last cell of previous row
    for (let r = rowIndex - 1; r >= 0; r--) {
      const prevRow = table.rows[r];
      if (prevRow.type !== "separator" && prevRow.cells.length > 0) {
        return { row: prevRow, cell: prevRow.cells[prevRow.cells.length - 1] };
      }
    }
    // We're at the beginning
    return null;
  }
}

/**
 * Handle Tab key in tables
 */
function handleTab(view, direction = "next") {
  let state = view.state;
  let pos = state.selection.main.head;

  let table = findTableAtPosition(state, pos);
  if (!table) return false;

  let found = findCellAtPos(table, pos);
  if (!found) return false;

  // Don't navigate in separator row
  if (found.row.type === "separator") return false;

  // Calculate position info before formatting
  const rowIndex = table.rows.indexOf(found.row);
  const colIndex = found.cell.colIndex;
  const offsetInCell = pos - found.cell.contentFrom;

  // Format the table before navigation (with cursor preservation)
  const formatted = formatTable(view, table, {
    anchorRow: rowIndex,
    anchorCol: colIndex,
    anchorOffset: offsetInCell,
    headRow: rowIndex,
    headCol: colIndex,
    headOffset: offsetInCell,
  });

  // Re-find table and cell after formatting (positions may have changed)
  if (formatted) {
    state = view.state;
    pos = state.selection.main.head;
    table = findTableAtPosition(state, pos);
    if (!table) return false;
    found = findCellAtPos(table, pos);
    if (!found) return false;
  }

  const { row, cell } = found;
  const next = getNextCell(table, row, cell, direction);

  if (next) {
    // Move to next/prev cell and select its content
    const { cell: nextCell } = next;

    // Select the cell content (or place cursor if empty)
    if (nextCell.contentFrom < nextCell.contentTo) {
      view.dispatch({
        selection: {
          anchor: nextCell.contentFrom,
          head: nextCell.contentTo,
        },
        scrollIntoView: true,
      });
    } else {
      // Empty cell - place cursor in the middle of the cell
      const cellMiddle = Math.floor((nextCell.from + nextCell.to) / 2);
      view.dispatch({
        selection: { anchor: cellMiddle },
        scrollIntoView: true,
      });
    }
    return true;
  } else if (direction === "next") {
    // At end of table - could add a new row or just move past
    // For now, let's add a new row
    return addNewRow(view, table);
  }

  return false;
}

/**
 * Add a new row at the end of the table
 */
function addNewRow(view, table) {
  const numCols = table.alignments.length;
  const lastRow = table.rows[table.rows.length - 1];

  // Create a new row with empty cells
  // Match the column widths from the last row for alignment
  const colWidths = lastRow.cells.map((cell) => {
    const width = cell.to - cell.from;
    return Math.max(width, 3); // Minimum 3 chars per cell
  });

  let newRowText = "|";
  for (let i = 0; i < numCols; i++) {
    const width = colWidths[i] || 3;
    newRowText += " ".repeat(width) + "|";
  }

  // Insert after the last row
  const insertPos = lastRow.to;
  view.dispatch({
    changes: { from: insertPos, to: insertPos, insert: "\n" + newRowText },
    selection: {
      // Place cursor in first cell of new row
      anchor: insertPos + 2, // After \n|
    },
    scrollIntoView: true,
  });

  return true;
}

/**
 * Handle Enter key in tables - move to same column in next row
 */
function handleEnter(view) {
  let state = view.state;
  let pos = state.selection.main.head;

  let table = findTableAtPosition(state, pos);
  if (!table) return false;

  let found = findCellAtPos(table, pos);
  if (!found) return false;

  if (found.row.type === "separator") return false;

  // Calculate position info before formatting
  const rowIndex = table.rows.indexOf(found.row);
  const colIndex = found.cell.colIndex;
  const offsetInCell = pos - found.cell.contentFrom;

  // Format the table before navigation (with cursor preservation)
  const formatted = formatTable(view, table, {
    anchorRow: rowIndex,
    anchorCol: colIndex,
    anchorOffset: offsetInCell,
    headRow: rowIndex,
    headCol: colIndex,
    headOffset: offsetInCell,
  });

  // Re-find table and cell after formatting
  if (formatted) {
    state = view.state;
    pos = state.selection.main.head;
    table = findTableAtPosition(state, pos);
    if (!table) return false;
    found = findCellAtPos(table, pos);
    if (!found) return false;
  }

  const { row, cell } = found;

  // Find same column in next data row
  const currentRowIndex = table.rows.indexOf(row);
  for (let r = currentRowIndex + 1; r < table.rows.length; r++) {
    const nextRow = table.rows[r];
    if (nextRow.type === "data" && nextRow.cells[cell.colIndex]) {
      const nextCell = nextRow.cells[cell.colIndex];
      if (nextCell.contentFrom < nextCell.contentTo) {
        view.dispatch({
          selection: {
            anchor: nextCell.contentFrom,
            head: nextCell.contentTo,
          },
          scrollIntoView: true,
        });
      } else {
        const cellMiddle = Math.floor((nextCell.from + nextCell.to) / 2);
        view.dispatch({
          selection: { anchor: cellMiddle },
          scrollIntoView: true,
        });
      }
      return true;
    }
  }

  // No next row - add one and stay in same column
  return addNewRow(view, table);
}

/**
 * Handle ArrowDown in tables - move to same column in next row, stay within bounds
 */
function handleArrowDown(view) {
  let state = view.state;
  let pos = state.selection.main.head;
  const currentLine = state.doc.lineAt(pos);

  let table = findTableAtPosition(state, pos);

  if (table) {
    let found = findCellAtPos(table, pos);
    if (!found) return false;

    // Calculate position info before formatting
    const rowIndex = table.rows.indexOf(found.row);
    const colIndex = found.cell.colIndex;
    const offsetInCell = pos - found.cell.contentFrom;

    // Format the table before navigation (with cursor preservation)
    const formatted = formatTable(view, table, {
      anchorRow: rowIndex,
      anchorCol: colIndex,
      anchorOffset: offsetInCell,
      headRow: rowIndex,
      headCol: colIndex,
      headOffset: offsetInCell,
    });

    // Re-find table and cell after formatting
    if (formatted) {
      state = view.state;
      pos = state.selection.main.head;
      table = findTableAtPosition(state, pos);
      if (!table) return false;
      found = findCellAtPos(table, pos);
      if (!found) return false;
    }

    const { row, cell } = found;
    const currentRowIndex = table.rows.indexOf(row);

    for (let r = currentRowIndex + 1; r < table.rows.length; r++) {
      const nextRow = table.rows[r];
      if (nextRow.type !== "separator" && nextRow.cells[cell.colIndex]) {
        const nextCell = nextRow.cells[cell.colIndex];
        const relativePos = Math.min(pos - cell.from, nextCell.to - nextCell.from);
        const newPos = nextCell.from + relativePos;

        view.dispatch({
          selection: { anchor: newPos },
          scrollIntoView: true,
        });
        return true;
      }
    }

    const tableLine = state.doc.lineAt(table.to);
    if (tableLine.number < state.doc.lines) {
      const nextLine = state.doc.line(tableLine.number + 1);
      const offsetInCell = pos - cell.from;
      const newPos = Math.min(nextLine.from + offsetInCell, nextLine.to);
      view.dispatch({
        selection: { anchor: newPos },
        scrollIntoView: true,
      });
      return true;
    }

    return false;
  }

  const lineCount = state.doc.lines;
  if (currentLine.number < lineCount) {
    const nextLine = state.doc.line(currentLine.number + 1);
    const tableBelow = findTableAtPosition(state, nextLine.from);

    if (tableBelow) {
      const firstRow = tableBelow.rows.find((r) => r.type !== "separator");

      if (firstRow && firstRow.cells.length > 0) {
        const offsetInLine = pos - currentLine.from;

        let targetCell = firstRow.cells[0];
        for (const cell of firstRow.cells) {
          const cellOffset = cell.from - firstRow.from;
          if (cellOffset <= offsetInLine) {
            targetCell = cell;
          }
        }

        const cellWidth = targetCell.to - targetCell.from;
        const relativeOffset = Math.min(
          offsetInLine - (targetCell.from - firstRow.from),
          cellWidth
        );
        const newPos = targetCell.from + Math.max(0, relativeOffset);

        view.dispatch({
          selection: { anchor: Math.min(newPos, targetCell.to) },
          scrollIntoView: true,
        });
        return true;
      }
    }
  }

  return false;
}

/**
 * Handle ArrowUp in tables - move to same column in previous row, stay within bounds
 * Also handles entering a table from below
 */
function handleArrowUp(view) {
  let state = view.state;
  let pos = state.selection.main.head;
  const currentLine = state.doc.lineAt(pos);

  // Check if cursor is currently in a table
  let table = findTableAtPosition(state, pos);

  if (table) {
    // Already in a table - navigate within it
    let found = findCellAtPos(table, pos);
    if (!found) return false;

    // Calculate position info before formatting
    const rowIndex = table.rows.indexOf(found.row);
    const colIndex = found.cell.colIndex;
    const offsetInCell = pos - found.cell.contentFrom;

    // Format the table before navigation (with cursor preservation)
    const formatted = formatTable(view, table, {
      anchorRow: rowIndex,
      anchorCol: colIndex,
      anchorOffset: offsetInCell,
      headRow: rowIndex,
      headCol: colIndex,
      headOffset: offsetInCell,
    });

    // Re-find table and cell after formatting
    if (formatted) {
      state = view.state;
      pos = state.selection.main.head;
      table = findTableAtPosition(state, pos);
      if (!table) return false;
      found = findCellAtPos(table, pos);
      if (!found) return false;
    }

    const { row, cell } = found;
    const currentRowIndex = table.rows.indexOf(row);

    // Find same column in previous non-separator row
    for (let r = currentRowIndex - 1; r >= 0; r--) {
      const prevRow = table.rows[r];
      if (prevRow.type !== "separator" && prevRow.cells[cell.colIndex]) {
        const prevCell = prevRow.cells[cell.colIndex];
        const relativePos = Math.min(pos - cell.from, prevCell.to - prevCell.from);
        const newPos = prevCell.from + relativePos;

        view.dispatch({
          selection: { anchor: newPos },
          scrollIntoView: true,
        });
        return true;
      }
    }

    // At first row - exit table upward
    const tableLine = state.doc.lineAt(table.from);
    if (tableLine.number > 1) {
      const prevLine = state.doc.line(tableLine.number - 1);
      const offsetInCell = pos - cell.from;
      const newPos = Math.min(prevLine.from + offsetInCell, prevLine.to);
      view.dispatch({
        selection: { anchor: newPos },
        scrollIntoView: true,
      });
      return true;
    }

    return false;
  }

  // Not in a table - check if line above is the last row of a table
  if (currentLine.number > 1) {
    const prevLine = state.doc.line(currentLine.number - 1);
    const tableAbove = findTableAtPosition(state, prevLine.from);

    if (tableAbove) {
      // There's a table above - enter it at the last row
      const lastRow = tableAbove.rows[tableAbove.rows.length - 1];

      // Calculate which column to land in based on horizontal position
      const offsetInLine = pos - currentLine.from;

      // Find the cell that best matches this horizontal position
      let targetCell = lastRow.cells[0];
      for (const cell of lastRow.cells) {
        const cellOffset = cell.from - lastRow.from;
        if (cellOffset <= offsetInLine) {
          targetCell = cell;
        }
      }

      if (targetCell) {
        // Position cursor within the cell
        const cellWidth = targetCell.to - targetCell.from;
        const relativeOffset = Math.min(offsetInLine - (targetCell.from - lastRow.from), cellWidth);
        const newPos = targetCell.from + Math.max(0, relativeOffset);

        view.dispatch({
          selection: { anchor: Math.min(newPos, targetCell.to) },
          scrollIntoView: true,
        });
        return true;
      }
    }
  }

  return false;
}

// ============================================================================
// Row/Column Insert & Delete Operations
// ============================================================================

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

function insertRowBelow(view) {
  const state = view.state;
  const pos = state.selection.main.head;
  const table = findTableAtPosition(state, pos);
  if (!table) return false;

  const found = findCellAtPos(table, pos);
  if (!found) return false;

  const { row, cell } = found;
  const colIndex = cell.colIndex;
  const numCols = table.alignments.length;

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

  const insertPos = insertAfterRow.to;
  const newRowStart = insertPos + 1;
  const firstCellStart = newRowStart + 2;

  view.dispatch({
    changes: { from: insertPos, insert: "\n" + newRowText },
    selection: { anchor: firstCellStart },
  });

  return true;
}

function insertRowAbove(view) {
  const state = view.state;
  const pos = state.selection.main.head;
  const table = findTableAtPosition(state, pos);
  if (!table) return false;

  const found = findCellAtPos(table, pos);
  if (!found) return false;

  const { row } = found;
  if (row.type === "header" || row.type === "separator") return false;

  const colWidths = calculateColumnWidths(table);
  const newRowCells = colWidths.map((w) => " ".repeat(w));
  const newRowText = "| " + newRowCells.join(" | ") + " |";

  const firstCellStart = row.from + 2;

  view.dispatch({
    changes: { from: row.from, insert: newRowText + "\n" },
    selection: { anchor: firstCellStart },
  });

  return true;
}

function insertColumnRight(view) {
  const state = view.state;
  const pos = state.selection.main.head;
  const table = findTableAtPosition(state, pos);
  if (!table) return false;

  const found = findCellAtPos(table, pos);
  if (!found) return false;

  const colIndex = found.cell.colIndex;
  const currentRow = found.row;
  const changes = [];
  let cursorOffset = 0;

  for (const row of table.rows) {
    const cells = row.cells.map((c) => c.content);
    const newContent = row.type === "separator" ? "---" : "";
    cells.splice(colIndex + 1, 0, newContent);

    const newLine = "| " + cells.join(" | ") + " |";
    changes.push({ from: row.from, to: row.to, insert: newLine });

    if (row === currentRow) {
      let offset = 2;
      for (let i = 0; i <= colIndex; i++) {
        offset += cells[i].length + 3;
      }
      cursorOffset = row.from + offset;
    }
  }

  view.dispatch({
    changes,
    selection: { anchor: cursorOffset },
  });

  setTimeout(() => {
    const newTable = findTableAtPosition(view.state, table.from);
    if (newTable && Math.abs(newTable.from - table.from) < 100) formatTable(view, newTable);
  }, 0);

  return true;
}

function insertColumnLeft(view) {
  const state = view.state;
  const pos = state.selection.main.head;
  const table = findTableAtPosition(state, pos);
  if (!table) return false;

  const found = findCellAtPos(table, pos);
  if (!found) return false;

  const colIndex = found.cell.colIndex;
  const currentRow = found.row;
  const changes = [];
  let cursorOffset = 0;

  for (const row of table.rows) {
    const cells = row.cells.map((c) => c.content);
    const newContent = row.type === "separator" ? "---" : "";
    cells.splice(colIndex, 0, newContent);

    const newLine = "| " + cells.join(" | ") + " |";
    changes.push({ from: row.from, to: row.to, insert: newLine });

    if (row === currentRow) {
      let offset = 2;
      for (let i = 0; i < colIndex; i++) {
        offset += cells[i].length + 3;
      }
      cursorOffset = row.from + offset;
    }
  }

  view.dispatch({
    changes,
    selection: { anchor: cursorOffset },
  });

  setTimeout(() => {
    const newTable = findTableAtPosition(view.state, table.from);
    if (newTable && Math.abs(newTable.from - table.from) < 100) formatTable(view, newTable);
  }, 0);

  return true;
}

function deleteRow(view) {
  const state = view.state;
  const pos = state.selection.main.head;
  const table = findTableAtPosition(state, pos);
  if (!table) return false;

  const found = findCellAtPos(table, pos);
  if (!found) return false;

  const { row, rowIndex } = found;
  if (row.type === "header" || row.type === "separator") return false;

  const dataRows = table.rows.filter((r) => r.type === "data");
  if (dataRows.length <= 1) return false;

  const lineStart = row.from;
  const lineEnd = row.to;
  const deleteFrom = lineStart > 0 ? lineStart - 1 : lineStart;

  const nextRow = table.rows[rowIndex + 1];
  const prevDataRow = dataRows[dataRows.indexOf(row) - 1];
  const targetRow = nextRow && nextRow.type === "data" ? nextRow : prevDataRow;

  let newCursorPos = table.from + 2;
  if (targetRow) {
    if (targetRow === nextRow) {
      newCursorPos = targetRow.from + 2 - (lineEnd - deleteFrom + 1);
    } else {
      newCursorPos = targetRow.from + 2;
    }
  }

  view.dispatch({
    changes: { from: deleteFrom, to: lineEnd },
    selection: { anchor: Math.max(0, newCursorPos) },
  });

  return true;
}

function deleteColumn(view) {
  const state = view.state;
  const pos = state.selection.main.head;
  const table = findTableAtPosition(state, pos);
  if (!table) return false;

  const found = findCellAtPos(table, pos);
  if (!found) return false;

  if (table.alignments.length <= 1) return false;

  const colIndex = found.cell.colIndex;
  const rowIndex = found.rowIndex;
  const changes = [];

  for (const row of table.rows) {
    const cell = row.cells[colIndex];
    if (!cell) continue;

    const deleteFrom = colIndex === 0 ? cell.from - 1 : cell.from - 1;
    const deleteTo = cell.to;
    changes.push({ from: deleteFrom, to: deleteTo });
  }

  changes.sort((a, b) => b.from - a.from);
  view.dispatch({ changes });

  setTimeout(() => {
    const updatedTable = findTableAtPosition(view.state, table.from);
    if (updatedTable && Math.abs(updatedTable.from - table.from) < 100) {
      formatTable(view, updatedTable);
      setTimeout(() => {
        const finalTable = findTableAtPosition(view.state, table.from);
        if (
          finalTable &&
          Math.abs(finalTable.from - table.from) < 100 &&
          rowIndex < finalTable.rows.length
        ) {
          const targetRow = finalTable.rows[rowIndex];
          const targetColIndex = Math.min(colIndex, targetRow.cells.length - 1);
          if (targetRow && targetRow.cells[targetColIndex]) {
            view.dispatch({ selection: { anchor: targetRow.cells[targetColIndex].from } });
          }
        }
      }, 10);
    }
  }, 10);
  return true;
}

const tableKeymap = Prec.high(
  keymap.of([
    {
      key: "Tab",
      run: (view) => handleTab(view, "next"),
    },
    {
      key: "Shift-Tab",
      run: (view) => handleTab(view, "prev"),
    },
    {
      key: "Enter",
      run: handleEnter,
    },
    {
      key: "ArrowDown",
      run: handleArrowDown,
    },
    {
      key: "ArrowUp",
      run: handleArrowUp,
    },
    {
      key: "Mod-Enter",
      run: insertRowBelow,
    },
    {
      key: "Mod-Shift-Enter",
      run: insertRowAbove,
    },
    {
      key: "Mod-Shift-ArrowRight",
      run: insertColumnRight,
    },
    {
      key: "Mod-Shift-ArrowLeft",
      run: insertColumnLeft,
    },
  ])
);

// ============================================================================
// Table Formatting
// ============================================================================

/**
 * Format/align a table (called manually or could be automatic)
 */
export function formatTable(view, table, preserveSelection = null) {
  const state = view.state;
  const doc = state.doc;

  // Calculate max width for each column
  const numCols = table.alignments.length;
  const colWidths = new Array(numCols).fill(3); // Minimum width

  for (const row of table.rows) {
    if (row.type === "separator") continue;
    for (let i = 0; i < row.cells.length && i < numCols; i++) {
      colWidths[i] = Math.max(colWidths[i], row.cells[i].content.length);
    }
  }

  // Build formatted table text
  const lines = [];

  for (const row of table.rows) {
    let lineText = "|";

    if (row.type === "separator") {
      // Build separator with alignment markers
      // The dashes + colons should equal the column width
      for (let i = 0; i < numCols; i++) {
        const width = colWidths[i];
        const align = table.alignments[i];
        let sep;

        if (align === "center") {
          // :---: format: 2 colons, so width-2 dashes (minimum 1 dash)
          const dashCount = Math.max(1, width - 2);
          sep = ":" + "-".repeat(dashCount) + ":";
        } else if (align === "right") {
          // ---: format: 1 colon on right, so width-1 dashes
          const dashCount = Math.max(1, width - 1);
          sep = "-".repeat(dashCount) + ":";
        } else {
          // :--- format: 1 colon on left, so width-1 dashes
          const dashCount = Math.max(1, width - 1);
          sep = ":" + "-".repeat(dashCount);
        }

        lineText += " " + sep + " |";
      }
    } else {
      // Data/header row
      for (let i = 0; i < numCols; i++) {
        const cell = row.cells[i];
        const content = cell ? cell.content : "";
        const width = colWidths[i];
        const align = table.alignments[i];

        let padded;
        if (align === "right") {
          padded = content.padStart(width);
        } else if (align === "center") {
          const totalPad = width - content.length;
          const leftPad = Math.floor(totalPad / 2);
          const rightPad = totalPad - leftPad;
          padded = " ".repeat(leftPad) + content + " ".repeat(rightPad);
        } else {
          padded = content.padEnd(width);
        }

        lineText += " " + padded + " |";
      }
    }

    lines.push(lineText);
  }

  const newText = lines.join("\n");
  const oldText = doc.sliceString(table.from, table.to);

  if (newText !== oldText) {
    const dispatchSpec = {
      changes: { from: table.from, to: table.to, insert: newText },
    };

    if (preserveSelection) {
      const { anchorRow, anchorCol, anchorOffset, headRow, headCol, headOffset } =
        preserveSelection;

      const newLines = newText.split("\n");
      let newAnchor = table.from;
      let newHead = table.from;

      let pos = table.from;
      for (let i = 0; i < newLines.length; i++) {
        const line = newLines[i];
        const cells = line.split("|").slice(1, -1);

        for (let c = 0; c < cells.length; c++) {
          const cellStart = pos + line.indexOf(cells[c]);
          const cellContent = cells[c].trim();
          const contentStart = cellStart + cells[c].indexOf(cellContent);

          if (i === anchorRow && c === anchorCol) {
            newAnchor = Math.min(contentStart + anchorOffset, contentStart + cellContent.length);
          }
          if (i === headRow && c === headCol) {
            newHead = Math.min(contentStart + headOffset, contentStart + cellContent.length);
          }
        }
        pos += line.length + 1;
      }

      dispatchSpec.selection = { anchor: newAnchor, head: newHead };
    }

    view.dispatch(dispatchSpec);
    return true;
  }

  return false;
}

// ============================================================================
// Table Creation Helper
// ============================================================================

/**
 * Generate markdown for a new table
 * @param {number} rows - Number of data rows
 * @param {number} cols - Number of columns
 * @returns {string}
 */
export function generateTable(rows, cols) {
  const lines = [];

  // Header row
  const headers = [];
  for (let i = 0; i < cols; i++) {
    headers.push(`Header ${i + 1}`);
  }
  lines.push("| " + headers.join(" | ") + " |");

  // Separator row
  const seps = [];
  for (let i = 0; i < cols; i++) {
    seps.push("-".repeat(headers[i].length));
  }
  lines.push("| " + seps.join(" | ") + " |");

  // Data rows
  for (let r = 0; r < rows; r++) {
    const cells = [];
    for (let c = 0; c < cols; c++) {
      cells.push(" ".repeat(headers[c].length));
    }
    lines.push("| " + cells.join(" | ") + " |");
  }

  return lines.join("\n");
}

/**
 * Insert a new table at the current cursor position
 */
export function insertTable(view, rows = 2, cols = 2) {
  const pos = view.state.selection.main.head;
  const tableText = generateTable(rows, cols);

  const doc = view.state.doc;
  const line = doc.lineAt(pos);
  const needsNewlineBefore = line.text.trim().length > 0;
  const needsNewlineAfter = pos < doc.length;

  const insert = (needsNewlineBefore ? "\n\n" : "") + tableText + (needsNewlineAfter ? "\n" : "");

  const headerStart = pos + (needsNewlineBefore ? 2 : 0) + 2;
  const headerEnd = headerStart + "Header 1".length;

  view.dispatch({
    changes: { from: pos, insert },
    selection: {
      anchor: headerStart,
      head: headerEnd,
    },
  });
}

// ============================================================================
// Compatibility Helpers (for use by other modules like decorateSectionHeaders)
// ============================================================================

/**
 * Find markdown table ranges in raw text (for use without EditorState)
 * @param {string} text - Raw document text
 * @returns {Array<{from: number, to: number}>}
 */
export function findTableRanges(text) {
  const tables = [];
  const lines = text.split("\n");
  let currentTable = null;
  let pos = 0;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const nextLine = lines[i + 1];

    const isTableRow = TABLE_LINE_REGEX.test(line);
    const isSep = nextLine && isSeparatorLine(nextLine);

    if (isTableRow && !currentTable && isSep) {
      currentTable = { from: pos, lines: [line, nextLine] };
      i++;
      pos += line.length + 1 + nextLine.length + 1;
      continue;
    } else if (currentTable && isTableRow) {
      currentTable.lines.push(line);
    } else if (currentTable && !isTableRow) {
      currentTable.to = pos;
      if (currentTable.lines.length >= 2) {
        tables.push({ from: currentTable.from, to: currentTable.to });
      }
      currentTable = null;
    }

    pos += line.length + 1;
  }

  if (currentTable) {
    currentTable.to = pos - 1;
    if (currentTable.lines.length >= 2) {
      tables.push({ from: currentTable.from, to: currentTable.to });
    }
  }

  return tables;
}

/**
 * Check if a position is inside any table range
 * @param {number} pos - Position to check
 * @param {Array<{from: number, to: number}>} tableRanges
 * @returns {boolean}
 */
export function isInsideTable(pos, tableRanges) {
  return tableRanges.some((t) => pos >= t.from && pos <= t.to);
}

// ============================================================================
// Context Menu
// ============================================================================

let activeContextMenu = null;

function hideContextMenu() {
  if (activeContextMenu) {
    activeContextMenu.remove();
    activeContextMenu = null;
  }
}

function showTableContextMenu(view, x, y, table, cellInfo) {
  hideContextMenu();

  const isMac = /Mac|iPhone|iPad|iPod/.test(navigator.platform);
  const modKey = isMac ? "⌘" : "Ctrl";

  const menu = document.createElement("div");
  menu.className = "table-context-menu";
  menu.innerHTML = `
    <button data-action="insert-row-above">
      <span>Insert row above</span>
      <span class="shortcut">${modKey}⇧↵</span>
    </button>
    <button data-action="insert-row-below">
      <span>Insert row below</span>
      <span class="shortcut">${modKey}↵</span>
    </button>
    <div class="table-context-menu-divider"></div>
    <button data-action="insert-col-left">
      <span>Insert column left</span>
      <span class="shortcut">${modKey}⇧←</span>
    </button>
    <button data-action="insert-col-right">
      <span>Insert column right</span>
      <span class="shortcut">${modKey}⇧→</span>
    </button>
    <div class="table-context-menu-divider"></div>
    <button data-action="delete-row" class="danger">
      <span>Delete row</span>
    </button>
    <button data-action="delete-col" class="danger">
      <span>Delete column</span>
    </button>
  `;

  menu.style.left = `${x}px`;
  menu.style.top = `${y}px`;

  const isHeaderOrSep = cellInfo.row.type === "header" || cellInfo.row.type === "separator";
  const isSingleDataRow = table.rows.filter((r) => r.type === "data").length <= 1;
  const isSingleColumn = table.alignments.length <= 1;

  if (isHeaderOrSep) {
    menu.querySelector('[data-action="insert-row-above"]').disabled = true;
    menu.querySelector('[data-action="delete-row"]').disabled = true;
  }
  if (isSingleDataRow) {
    menu.querySelector('[data-action="delete-row"]').disabled = true;
  }
  if (isSingleColumn) {
    menu.querySelector('[data-action="delete-col"]').disabled = true;
  }

  menu.addEventListener("click", (e) => {
    const button = e.target.closest("button");
    if (!button) return;

    const action = button.dataset.action;
    if (!action || button.disabled) return;

    hideContextMenu();
    view.focus();

    switch (action) {
      case "insert-row-above":
        insertRowAbove(view);
        break;
      case "insert-row-below":
        insertRowBelow(view);
        break;
      case "insert-col-left":
        insertColumnLeft(view);
        break;
      case "insert-col-right":
        insertColumnRight(view);
        break;
      case "delete-row":
        deleteRow(view);
        break;
      case "delete-col":
        deleteColumn(view);
        break;
    }
  });

  document.body.appendChild(menu);
  activeContextMenu = menu;

  const cleanup = (e) => {
    if (!menu.contains(e.target)) {
      hideContextMenu();
      document.removeEventListener("mousedown", cleanup);
    }
  };
  setTimeout(() => document.addEventListener("mousedown", cleanup), 0);
}

const tableContextMenu = ViewPlugin.fromClass(
  class {
    constructor(view) {
      this.view = view;
      this.handleContextMenu = this.handleContextMenu.bind(this);
      view.dom.addEventListener("contextmenu", this.handleContextMenu);
    }

    handleContextMenu(e) {
      const pos = this.view.posAtCoords({ x: e.clientX, y: e.clientY });
      if (pos === null) return;

      const table = findTableAtPosition(this.view.state, pos);
      if (!table) return;

      const cellInfo = findCellAtPos(table, pos);
      if (!cellInfo) return;

      e.preventDefault();
      showTableContextMenu(this.view, e.clientX, e.clientY, table, cellInfo);
    }

    destroy() {
      this.view.dom.removeEventListener("contextmenu", this.handleContextMenu);
      hideContextMenu();
    }
  }
);

// ============================================================================
// Export Extension
// ============================================================================

export const markdownTableExtension = [
  tablesField,
  tableDecorations,
  tableAutoFormat,
  tableKeymap,
  tableContextMenu,
];

// Also export individual pieces for testing
export { tableAutoFormat, tableContextMenu, tableDecorations, tableKeymap, tablesField };

// Export handlers for testing
export { handleArrowDown, handleArrowUp };

// Export row/column operations for external use
export {
  deleteColumn,
  deleteRow,
  insertColumnLeft,
  insertColumnRight,
  insertRowAbove,
  insertRowBelow,
};
