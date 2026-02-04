/**
 * List formatting utilities for multi-line selections.
 * Extracted from Toolbar.svelte for testability.
 */

/**
 * Toggle a line prefix (like "- " for bullets, "> " for blockquotes) on all selected lines.
 * If all lines have the prefix, removes it. Otherwise, adds it to all lines.
 *
 * @param {EditorView} view - The CodeMirror EditorView
 * @param {string} prefix - The prefix to toggle (e.g., "- ", "> ", "# ")
 * @returns {boolean} - Always returns true
 */
export function toggleLinePrefix(view, prefix) {
  const { state } = view;
  const { from, to } = state.selection.main;

  const startLine = state.doc.lineAt(from);
  const endLine = state.doc.lineAt(to);

  const changes = [];
  let allHavePrefix = true;

  // Check if all lines already have the prefix
  for (let lineNum = startLine.number; lineNum <= endLine.number; lineNum++) {
    const line = state.doc.line(lineNum);
    if (!line.text.startsWith(prefix)) {
      allHavePrefix = false;
      break;
    }
  }

  const headingPrefixes = ["# ", "## ", "### ", "#### ", "##### ", "###### "];
  const isHeadingPrefix = headingPrefixes.includes(prefix);

  // Build changes - CodeMirror expects positions from the original document
  for (let lineNum = startLine.number; lineNum <= endLine.number; lineNum++) {
    const line = state.doc.line(lineNum);

    if (allHavePrefix) {
      // Remove the prefix from all lines
      changes.push({
        from: line.from,
        to: line.from + prefix.length,
        insert: "",
      });
    } else {
      // Add the prefix to lines that don't have it
      let insertAt = line.from;
      let removeEnd = line.from;

      // For headings, replace existing heading prefix if present
      if (isHeadingPrefix) {
        const existingHeading = headingPrefixes.find((p) => line.text.startsWith(p));
        if (existingHeading) {
          removeEnd = line.from + existingHeading.length;
        }
      }

      changes.push({
        from: insertAt,
        to: removeEnd,
        insert: prefix,
      });
    }
  }

  view.dispatch({ changes });
  return true;
}

/**
 * Toggle ordered list numbering on all selected lines.
 * If all lines are numbered, removes numbering. Otherwise, adds sequential numbers.
 *
 * @param {EditorView} view - The CodeMirror EditorView
 * @returns {boolean} - Always returns true
 */
export function toggleOrderedList(view) {
  const { state } = view;
  const { from, to } = state.selection.main;

  const startLine = state.doc.lineAt(from);
  const endLine = state.doc.lineAt(to);

  const changes = [];
  const olPattern = /^(\d+)\.\s/;
  let allHavePrefix = true;

  // Check if all lines already have ordered list numbering
  for (let lineNum = startLine.number; lineNum <= endLine.number; lineNum++) {
    const line = state.doc.line(lineNum);
    if (!olPattern.test(line.text)) {
      allHavePrefix = false;
      break;
    }
  }

  let itemNum = 1;

  // Build changes - CodeMirror expects positions from the original document
  for (let lineNum = startLine.number; lineNum <= endLine.number; lineNum++) {
    const line = state.doc.line(lineNum);
    const match = line.text.match(olPattern);

    if (allHavePrefix && match) {
      // Remove the numbered prefix from all lines
      changes.push({
        from: line.from,
        to: line.from + match[0].length,
        insert: "",
      });
    } else {
      // Add or update numbering
      const prefix = `${itemNum}. `;
      let removeLen = 0;

      if (match) {
        // Replace existing number with correct sequence
        removeLen = match[0].length;
      }

      changes.push({
        from: line.from,
        to: line.from + removeLen,
        insert: prefix,
      });
      itemNum++;
    }
  }

  view.dispatch({ changes });
  return true;
}

/**
 * Toggle bullet list on all selected lines.
 * Convenience wrapper for toggleLinePrefix with "- ".
 *
 * @param {EditorView} view - The CodeMirror EditorView
 * @returns {boolean} - Always returns true
 */
export function toggleBulletList(view) {
  return toggleLinePrefix(view, "- ");
}

/**
 * Toggle blockquote on all selected lines.
 * Convenience wrapper for toggleLinePrefix with "> ".
 *
 * @param {EditorView} view - The CodeMirror EditorView
 * @returns {boolean} - Always returns true
 */
export function toggleBlockquote(view) {
  return toggleLinePrefix(view, "> ");
}
