/**
 * CSV Parser
 * Handles RFC 4180 compliant CSV parsing including:
 * - Quoted fields
 * - Escaped quotes (doubled quotes)
 * - Newlines within quoted fields
 * - Empty cells
 */

export function parseCSV(text) {
  if (!text || typeof text !== "string") {
    return { headers: [], rows: [] };
  }

  const rows = [];
  let currentRow = [];
  let currentCell = "";
  let inQuotes = false;
  let i = 0;

  while (i < text.length) {
    const char = text[i];
    const nextChar = text[i + 1];

    if (inQuotes) {
      if (char === '"') {
        if (nextChar === '"') {
          currentCell += '"';
          i += 2;
          continue;
        } else {
          inQuotes = false;
          i++;
          continue;
        }
      } else {
        currentCell += char;
        i++;
        continue;
      }
    }

    if (char === '"') {
      inQuotes = true;
      i++;
      continue;
    }

    if (char === ",") {
      currentRow.push(currentCell);
      currentCell = "";
      i++;
      continue;
    }

    if (char === "\r" && nextChar === "\n") {
      currentRow.push(currentCell);
      rows.push(currentRow);
      currentRow = [];
      currentCell = "";
      i += 2;
      continue;
    }

    if (char === "\n") {
      currentRow.push(currentCell);
      rows.push(currentRow);
      currentRow = [];
      currentCell = "";
      i++;
      continue;
    }

    currentCell += char;
    i++;
  }

  if (currentCell || currentRow.length > 0) {
    currentRow.push(currentCell);
    rows.push(currentRow);
  }

  if (rows.length === 0) {
    return { headers: [], rows: [] };
  }

  const headers = rows[0];
  const dataRows = rows.slice(1).filter((row) => row.some((cell) => cell.trim() !== ""));

  const maxCols = Math.max(headers.length, ...dataRows.map((r) => r.length));
  const normalizedHeaders = [...headers];
  while (normalizedHeaders.length < maxCols) {
    normalizedHeaders.push(`Column ${normalizedHeaders.length + 1}`);
  }

  const normalizedRows = dataRows.map((row) => {
    const normalized = [...row];
    while (normalized.length < maxCols) {
      normalized.push("");
    }
    return normalized;
  });

  return {
    headers: normalizedHeaders,
    rows: normalizedRows,
  };
}

export function sortRows(rows, columnIndex, direction) {
  if (columnIndex < 0) return rows;

  return [...rows].sort((a, b) => {
    const aVal = a[columnIndex] ?? "";
    const bVal = b[columnIndex] ?? "";

    const aNum = parseFloat(aVal);
    const bNum = parseFloat(bVal);
    const bothNumeric = !isNaN(aNum) && !isNaN(bNum) && aVal.trim() !== "" && bVal.trim() !== "";

    let comparison;
    if (bothNumeric) {
      comparison = aNum - bNum;
    } else {
      comparison = aVal.localeCompare(bVal, undefined, { numeric: true, sensitivity: "base" });
    }

    return direction === "desc" ? -comparison : comparison;
  });
}

export function filterRows(rows, query) {
  if (!query || query.trim() === "") return rows;

  const lowerQuery = query.toLowerCase();
  return rows.filter((row) => row.some((cell) => cell.toLowerCase().includes(lowerQuery)));
}
