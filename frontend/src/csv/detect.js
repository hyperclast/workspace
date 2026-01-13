/**
 * CSV Detection Utility
 *
 * Determines if content appears to be CSV format by analyzing
 * the first line for delimiter patterns.
 */

/**
 * Check if content looks like CSV data.
 *
 * @param {string} content - The text content to analyze
 * @returns {boolean} - True if content appears to be CSV
 *
 * Detection criteria:
 * - Empty content returns false (nothing to analyze)
 * - First line must have at least one comma or tab
 * - Must result in 2+ columns (1+ delimiters)
 */
export function looksLikeCsv(content) {
  if (!content || content.trim() === "") return false;

  const lines = content.split(/\r?\n/).filter((line) => line.trim() !== "");
  if (lines.length === 0) return false;

  const firstLine = lines[0];
  const hasComma = firstLine.includes(",");
  const hasTab = firstLine.includes("\t");

  if (!hasComma && !hasTab) return false;

  const delimiter = hasComma ? "," : "\t";
  const columnCount = firstLine.split(delimiter).length;

  return columnCount >= 2;
}
