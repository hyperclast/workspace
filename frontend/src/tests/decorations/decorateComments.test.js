import { describe, test, expect, afterEach } from "vitest";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import {
  decorateComments,
  setCommentHighlights,
  setActiveComment,
  commentHighlightField,
} from "../../decorateComments.js";

describe("decorateComments — line bar decorations", () => {
  let view;

  function createView(doc) {
    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [decorateComments],
      }),
      parent: document.createElement("div"),
    });
    return view;
  }

  afterEach(() => {
    if (view && !view.destroyed) {
      view.destroy();
    }
  });

  test("no decorations by default", () => {
    createView("Line one\nLine two\nLine three");

    const field = view.state.field(commentHighlightField);
    expect(field.decorations.size).toBe(0);
    expect(field.ranges).toEqual([]);
  });

  test("adds line bar for a single-line comment range", () => {
    createView("Line one\nLine two\nLine three");

    // Comment anchored to "Line two" (positions 9-17)
    view.dispatch({
      effects: setCommentHighlights.of([{ from: 9, to: 17, commentId: "c1", isAi: false }]),
    });

    const field = view.state.field(commentHighlightField);
    expect(field.decorations.size).toBe(1);

    // The decorated line should have the bar class
    const lines = view.dom.querySelectorAll(".cm-comment-bar");
    expect(lines.length).toBe(1);
  });

  test("adds line bars for multi-line comment range", () => {
    createView("Line one\nLine two\nLine three\nLine four");

    // Comment spanning lines 2-3 (positions 9-27)
    view.dispatch({
      effects: setCommentHighlights.of([{ from: 9, to: 27, commentId: "c1", isAi: false }]),
    });

    const lines = view.dom.querySelectorAll(".cm-comment-bar");
    expect(lines.length).toBe(2);
  });

  test("AI comment gets ai class", () => {
    createView("Line one\nLine two");

    view.dispatch({
      effects: setCommentHighlights.of([{ from: 9, to: 17, commentId: "c1", isAi: true }]),
    });

    const aiLines = view.dom.querySelectorAll(".cm-comment-bar-ai");
    expect(aiLines.length).toBe(1);
  });

  test("active comment gets active class", () => {
    createView("Line one\nLine two\nLine three");

    view.dispatch({
      effects: [
        setCommentHighlights.of([
          { from: 0, to: 8, commentId: "c1", isAi: false },
          { from: 9, to: 17, commentId: "c2", isAi: false },
        ]),
        setActiveComment.of("c2"),
      ],
    });

    const activeLines = view.dom.querySelectorAll(".cm-comment-bar-active");
    expect(activeLines.length).toBe(1);

    // Non-active comment still has regular bar
    const regularLines = view.dom.querySelectorAll(".cm-comment-bar:not(.cm-comment-bar-active)");
    expect(regularLines.length).toBe(1);
  });

  test("active takes priority when comments overlap on same line", () => {
    createView("Line one\nLine two\nLine three");

    // Both comments cover line 2
    view.dispatch({
      effects: [
        setCommentHighlights.of([
          { from: 9, to: 17, commentId: "c1", isAi: false },
          { from: 9, to: 17, commentId: "c2", isAi: true },
        ]),
        setActiveComment.of("c1"),
      ],
    });

    // Line 2 should have active class (not AI class)
    const activeLines = view.dom.querySelectorAll(".cm-comment-bar-active");
    expect(activeLines.length).toBe(1);
    const aiLines = view.dom.querySelectorAll(".cm-comment-bar-ai");
    expect(aiLines.length).toBe(0);
  });

  test("clearing highlights removes all bars", () => {
    createView("Line one\nLine two");

    view.dispatch({
      effects: setCommentHighlights.of([{ from: 0, to: 8, commentId: "c1", isAi: false }]),
    });
    expect(view.dom.querySelectorAll(".cm-comment-bar").length).toBe(1);

    view.dispatch({
      effects: setCommentHighlights.of([]),
    });
    expect(view.dom.querySelectorAll(".cm-comment-bar").length).toBe(0);
  });

  test("ignores invalid ranges", () => {
    createView("Line one\nLine two");

    view.dispatch({
      effects: setCommentHighlights.of([
        { from: 10, to: 5, commentId: "c1", isAi: false }, // from > to
        { from: -1, to: 5, commentId: "c2", isAi: false }, // negative from
        { from: 0, to: 999, commentId: "c3", isAi: false }, // to > doc length
      ]),
    });

    expect(view.dom.querySelectorAll(".cm-comment-bar").length).toBe(0);
  });

  test("decorations persist through unrelated document changes", () => {
    createView("Line one\nLine two\nLine three");

    view.dispatch({
      effects: setCommentHighlights.of([{ from: 9, to: 17, commentId: "c1", isAi: false }]),
    });

    const field = view.state.field(commentHighlightField);
    expect(field.ranges.length).toBe(1);

    // Type at end of document — decorations should persist (not be cleared)
    view.dispatch({ changes: { from: view.state.doc.length, insert: "\nNew line" } });

    const fieldAfter = view.state.field(commentHighlightField);
    expect(fieldAfter.ranges.length).toBe(1);
  });
});
