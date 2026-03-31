/**
 * Pure-logic helpers for applying AI comment suggestions into a CodeMirror document.
 *
 * Extracted from CommentsTab.svelte so they can be unit-tested independently.
 */

import { SearchCursor } from "@codemirror/search";

/**
 * Resolve the anchor range for a comment, first checking the pre-computed
 * highlight ranges in the editor state field, then falling back to a plain
 * text search for anchor_text.
 *
 * @param {import("@codemirror/state").EditorState} state
 * @param {Array<{from: number, to: number, commentId: string}>} highlightRanges
 * @param {{ external_id: string, anchor_text: string }} comment
 * @returns {{ from: number, to: number } | null}
 */
export function resolveAnchorRange(state, highlightRanges, comment) {
  // Check pre-computed highlight ranges first
  const highlighted = highlightRanges.find((r) => r.commentId === comment.external_id);
  if (highlighted) {
    return { from: highlighted.from, to: highlighted.to };
  }

  // Fallback: text search using SearchCursor (avoids O(n) doc.toString())
  if (comment.anchor_text) {
    const cursor = new SearchCursor(state.doc, comment.anchor_text);
    if (cursor.next().done === false) {
      return { from: cursor.value.from, to: cursor.value.to };
    }
  }

  return null;
}

/**
 * Compute the CodeMirror change spec for inserting a suggestion body after the
 * paragraph that contains the anchor.
 *
 * A paragraph boundary is a blank line (empty or whitespace-only) or end of
 * document. This handles hard-wrapped text (e.g. from PDF imports) where a
 * single paragraph spans multiple lines separated by single newlines.
 *
 * @param {import("@codemirror/state").EditorState} state
 * @param {{ from: number, to: number }} range - Resolved anchor range
 * @param {string} body - Comment body text to insert
 * @returns {{ from: number, insert: string }} Change spec for EditorView.dispatch
 */
export function buildSuggestionChange(state, range, body) {
  // Walk forward from the anchor line until we hit a blank line or end of doc
  let line = state.doc.lineAt(range.to);
  while (line.number < state.doc.lines) {
    const next = state.doc.line(line.number + 1);
    if (next.text.trim() === "") break;
    line = next;
  }
  const insertPos = line.to;
  return {
    from: insertPos,
    insert: "\n\n" + body.trim() + "\n",
  };
}
