import { StateField, StateEffect } from "@codemirror/state";
import { Decoration, EditorView } from "@codemirror/view";

/**
 * Effect to set comment highlight ranges.
 * Dispatched externally when comments are loaded/updated and anchors resolved.
 * Each range: { from: number, to: number, commentId: string, isAi: boolean }
 */
export const setCommentHighlights = StateEffect.define();

/**
 * Effect to set the active (focused) comment ID.
 */
export const setActiveComment = StateEffect.define();

const commentLine = Decoration.line({ class: "cm-comment-bar" });
const commentLineAi = Decoration.line({ class: "cm-comment-bar cm-comment-bar-ai" });
const commentLineActive = Decoration.line({ class: "cm-comment-bar cm-comment-bar-active" });

/**
 * StateField that holds comment highlight decorations.
 * Updated via setCommentHighlights effect — not by scanning document content.
 */
export const commentHighlightField = StateField.define({
  create() {
    return { decorations: Decoration.none, activeId: null, ranges: [] };
  },

  update(value, tr) {
    let ranges = value.ranges;
    let activeId = value.activeId;
    let changed = false;

    for (const effect of tr.effects) {
      if (effect.is(setCommentHighlights)) {
        ranges = effect.value;
        changed = true;
      }
      if (effect.is(setActiveComment)) {
        activeId = effect.value;
        changed = true;
      }
    }

    // If the document changed, keep stale decorations until CommentsTab
    // re-resolves anchors via its debounced editorContentChanged listener.
    if (tr.docChanged && !changed) {
      return value;
    }

    if (!changed) return value;

    // Build line decorations for each line spanned by a comment range
    const lineSet = new Map(); // lineStart -> decoration (highest priority wins)
    for (const range of ranges) {
      if (range.from >= range.to) continue;
      if (range.from < 0 || range.to > tr.state.doc.length) continue;

      let deco = range.isAi ? commentLineAi : commentLine;
      if (range.commentId === activeId) {
        deco = commentLineActive;
      }

      // Add a line decoration for each line in the range
      const startLine = tr.state.doc.lineAt(range.from).number;
      const endLine = tr.state.doc.lineAt(range.to).number;
      for (let ln = startLine; ln <= endLine; ln++) {
        const lineStart = tr.state.doc.line(ln).from;
        // Active takes priority over any other decoration
        const existing = lineSet.get(lineStart);
        if (!existing || deco === commentLineActive) {
          lineSet.set(lineStart, deco);
        }
      }
    }

    // Sort by position (required by RangeSet)
    const decorationRanges = Array.from(lineSet.entries())
      .sort((a, b) => a[0] - b[0])
      .map(([pos, deco]) => deco.range(pos));

    return {
      decorations: Decoration.set(decorationRanges),
      activeId,
      ranges,
    };
  },

  provide(field) {
    return EditorView.decorations.from(field, (value) => value.decorations);
  },
});

/**
 * Theme for comment highlights.
 */
export const commentHighlightTheme = EditorView.baseTheme({
  ".cm-comment-bar": {
    borderRight: "3px solid rgba(255, 180, 0, 0.4)",
    position: "relative",
  },
  ".cm-comment-bar::after": {
    content: '""',
    position: "absolute",
    top: "0",
    right: "-3px",
    bottom: "0",
    width: "19px",
    cursor: "pointer",
  },
  ".cm-comment-bar-ai": {
    borderRight: "3px solid rgba(124, 58, 237, 0.35)",
  },
  ".cm-comment-bar-active": {
    borderRight: "3px solid rgba(255, 180, 0, 0.8)",
  },
});

/**
 * Click handler: clicking on a comment-decorated line in the editor
 * focuses that comment in the sidebar.
 */
const commentBarClickHandler = EditorView.domEventHandlers({
  click(event, view) {
    const pos = view.posAtCoords({ x: event.clientX, y: event.clientY });
    if (pos === null) return false;

    const clickedLine = view.state.doc.lineAt(pos).number;
    const field = view.state.field(commentHighlightField);

    const range = field.ranges.find((r) => {
      if (r.from >= r.to) return false;
      const startLine = view.state.doc.lineAt(r.from).number;
      const endLine = view.state.doc.lineAt(r.to).number;
      return clickedLine >= startLine && clickedLine <= endLine;
    });

    if (!range) return false;

    view.dispatch({ effects: setActiveComment.of(range.commentId) });
    window.dispatchEvent(
      new CustomEvent("commentFocused", {
        detail: { commentId: range.commentId },
      })
    );

    return false;
  },
});

/**
 * Combined extension for comment decorations.
 * Add this to the editor's extensions array.
 */
export const decorateComments = [
  commentHighlightField,
  commentHighlightTheme,
  commentBarClickHandler,
];
