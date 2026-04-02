/**
 * Comment anchor resolution — converts between Yjs RelativePositions and
 * absolute document positions, and drives editor highlight decorations.
 */

import * as Y from "yjs";
import { setCommentHighlights, setActiveComment } from "./decorateComments.js";
import { updateComment } from "./api.js";

/**
 * Resolve a base64-encoded Yjs RelativePosition to an absolute index.
 * @param {string} b64 - Base64-encoded RelativePosition
 * @param {Y.Doc} ydoc - The Yjs document
 * @returns {number|null} Absolute position, or null if resolution fails
 */
function resolveRelativePosition(b64, ydoc) {
  try {
    const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
    const relPos = Y.decodeRelativePosition(bytes);
    const absPos = Y.createAbsolutePositionFromRelativePosition(relPos, ydoc);
    return absPos ? absPos.index : null;
  } catch (e) {
    console.error("[CommentAnchors] Failed to resolve RelativePosition:", e);
    return null;
  }
}

/**
 * Search for anchor_text in the document and return the range of the first match.
 * @param {string} anchorText - The text to find
 * @param {import("@codemirror/state").Text} doc - CodeMirror document
 * @returns {{ from: number, to: number }|null}
 */
function findAnchorTextInDoc(anchorText, doc) {
  if (!anchorText) return null;

  // O(n) over the full document. Acceptable here because this runs once per
  // comment load (not per keystroke) and only for comments lacking binary anchors.
  const fullText = doc.toString();
  const idx = fullText.indexOf(anchorText);
  if (idx === -1) return null;

  return { from: idx, to: idx + anchorText.length };
}

/**
 * Create Yjs RelativePositions for a given absolute range.
 * @param {number} from - Start position
 * @param {number} to - End position
 * @param {Y.Text} ytext - The Yjs shared text
 * @returns {{ fromB64: string, toB64: string }}
 */
function createRelativePositions(from, to, ytext) {
  const fromRelPos = Y.createRelativePositionFromTypeIndex(ytext, from);
  const toRelPos = Y.createRelativePositionFromTypeIndex(ytext, to, -1);
  const fromB64 = btoa(String.fromCharCode(...Y.encodeRelativePosition(fromRelPos)));
  const toB64 = btoa(String.fromCharCode(...Y.encodeRelativePosition(toRelPos)));
  return { fromB64, toB64 };
}

/**
 * Resolve all comment anchors and update editor highlights.
 *
 * For comments with binary anchors (anchor_from_b64/anchor_to_b64):
 *   - Resolve to absolute positions via Yjs
 *
 * For comments with only anchor_text (AI comments, deferred resolution):
 *   - Search the document for the text
 *   - If found, create RelativePositions and PATCH back to the server
 *
 * @param {Array} comments - Flat list of root comments (with replies)
 * @param {string} pageExternalId - Current page external ID
 * @param {import("@codemirror/view").EditorView} [view] - EditorView instance
 * @param {Y.Doc} [ydoc] - Yjs document
 * @param {Y.Text} [ytext] - Yjs shared text
 * @returns {Array} Resolved ranges: [{ from, to, commentId, isAi, isResolved }]
 */
export function resolveCommentAnchors(comments, pageExternalId, view, ydoc, ytext) {
  if (!view || !comments?.length) return [];

  const doc = view.state.doc;
  const ranges = [];

  for (const comment of comments) {
    // Only root comments have anchors
    if (comment.parent_id) continue;

    let from = null;
    let to = null;

    // Try binary anchors first (already resolved)
    if (comment.anchor_from_b64 && comment.anchor_to_b64 && ydoc) {
      from = resolveRelativePosition(comment.anchor_from_b64, ydoc);
      to = resolveRelativePosition(comment.anchor_to_b64, ydoc);
    }

    // Fallback: search for anchor_text (deferred resolution for AI comments)
    if ((from === null || to === null) && comment.anchor_text) {
      const match = findAnchorTextInDoc(comment.anchor_text, doc);
      if (match) {
        from = match.from;
        to = match.to;

        // Deferred resolution: create RelativePositions and PATCH back
        if (!comment.anchor_from_b64 && !comment.anchor_to_b64 && ytext) {
          try {
            const { fromB64, toB64 } = createRelativePositions(from, to, ytext);
            // Fire-and-forget PATCH — don't block rendering
            updateComment(pageExternalId, comment.external_id, {
              anchor_from_b64: fromB64,
              anchor_to_b64: toB64,
            }).catch((e) => {
              console.error("[CommentAnchors] Deferred resolution PATCH failed:", e);
            });
          } catch (e) {
            console.error("[CommentAnchors] Failed to create RelativePositions:", e);
          }
        }
      }
    }

    if (from !== null && to !== null) {
      // Clamp to document bounds before validation
      from = Math.max(0, from);
      to = Math.min(doc.length, to);
      if (from < to) {
        ranges.push({
          from,
          to,
          commentId: comment.external_id,
          isAi: !!comment.ai_persona,
          isResolved: !!comment.is_resolved,
        });
      }
    }
  }

  return ranges;
}

/**
 * Dispatch highlight updates to the editor.
 * @param {import("@codemirror/view").EditorView} view
 * @param {Array} ranges - From resolveCommentAnchors
 */
export function updateCommentHighlights(view, ranges) {
  if (!view) return;
  view.dispatch({
    effects: setCommentHighlights.of(ranges),
  });
}

/**
 * Set the active (focused) comment in the editor.
 * @param {import("@codemirror/view").EditorView} view
 * @param {string|null} commentId
 */
export function setActiveCommentHighlight(view, commentId) {
  if (!view) return;
  view.dispatch({
    effects: setActiveComment.of(commentId),
  });
}
