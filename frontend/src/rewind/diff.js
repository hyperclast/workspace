/**
 * Client-side diff computation using jsdiff.
 * Compares old content (rewind snapshot) against current HEAD content.
 */

import { diffLines } from "diff";

const MAX_DIFF_LINES = 5000;

/**
 * Compute a line-level diff between old and new content.
 * @param {string} oldContent - Content from the rewind snapshot
 * @param {string} newContent - Current HEAD content from editor
 * @returns {{ chunks: Array<{type: 'added'|'removed'|'unchanged', lines: string[]}>, stats: {added: number, removed: number}, tooLarge: boolean }}
 */
export function computeDiff(oldContent, newContent) {
  if (oldContent === newContent) {
    return { chunks: [], stats: { added: 0, removed: 0 }, tooLarge: false };
  }

  const changes = diffLines(oldContent || "", newContent || "");

  let totalChanged = 0;
  const chunks = [];
  const stats = { added: 0, removed: 0 };

  for (const change of changes) {
    const lines = change.value.split("\n");
    // diffLines includes trailing newline in segments, remove empty last element
    if (lines.length > 0 && lines[lines.length - 1] === "") {
      lines.pop();
    }

    if (change.added) {
      stats.added += lines.length;
      totalChanged += lines.length;
      chunks.push({ type: "added", lines });
    } else if (change.removed) {
      stats.removed += lines.length;
      totalChanged += lines.length;
      chunks.push({ type: "removed", lines });
    } else {
      chunks.push({ type: "unchanged", lines });
    }
  }

  return {
    chunks,
    stats,
    tooLarge: totalChanged > MAX_DIFF_LINES,
  };
}
