import { describe, test, expect, vi, beforeEach } from "vitest";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";

// Mock Yjs — we're testing the pure logic layer, not Yjs internals
vi.mock("yjs", () => ({
  decodeRelativePosition: vi.fn(),
  createAbsolutePositionFromRelativePosition: vi.fn(),
  createRelativePositionFromTypeIndex: vi.fn(() => new Uint8Array([1, 2, 3])),
  encodeRelativePosition: vi.fn(() => new Uint8Array([4, 5, 6])),
}));

// Mock the API — updateComment is called for deferred resolution
vi.mock("../../api.js", () => ({
  updateComment: vi.fn(() => Promise.resolve()),
}));

// Mock decorateComments — resolveCommentAnchors imports symbols from it
vi.mock("../../decorateComments.js", () => ({
  setCommentHighlights: { of: vi.fn() },
  setActiveComment: { of: vi.fn() },
}));

import { resolveCommentAnchors } from "../../commentAnchors.js";
import { updateComment } from "../../api.js";
import * as Y from "yjs";

function makeComment(overrides = {}) {
  return {
    external_id: "c1",
    parent_id: null,
    anchor_from_b64: null,
    anchor_to_b64: null,
    anchor_text: "",
    ai_persona: "",
    ...overrides,
  };
}

describe("resolveCommentAnchors — pure logic", () => {
  let view;

  function createView(doc) {
    view = new EditorView({
      state: EditorState.create({ doc }),
      parent: document.createElement("div"),
    });
    return view;
  }

  beforeEach(() => {
    vi.clearAllMocks();
    if (view && !view.destroyed) {
      view.destroy();
    }
  });

  test("returns empty array when view is null", () => {
    const result = resolveCommentAnchors([makeComment()], "page1", null, null, null);
    expect(result).toEqual([]);
  });

  test("returns empty array when comments is empty", () => {
    createView("Hello world");
    const result = resolveCommentAnchors([], "page1", view, null, null);
    expect(result).toEqual([]);
  });

  test("returns empty array when comments is null", () => {
    createView("Hello world");
    const result = resolveCommentAnchors(null, "page1", view, null, null);
    expect(result).toEqual([]);
  });

  test("skips reply comments (with parent_id)", () => {
    createView("Hello world, this is a test document.");
    const reply = makeComment({
      parent_id: "parent1",
      anchor_text: "Hello world",
    });
    const result = resolveCommentAnchors([reply], "page1", view, null, null);
    expect(result).toEqual([]);
  });

  test("resolves anchor_text via text search when binary anchors are null", () => {
    createView("Hello world, this is a test document.");
    const comment = makeComment({
      anchor_text: "this is a test",
    });

    const result = resolveCommentAnchors([comment], "page1", view, null, null);

    expect(result).toHaveLength(1);
    expect(result[0].from).toBe(13); // "Hello world, " is 13 chars
    expect(result[0].to).toBe(27); // "this is a test" is 14 chars
    expect(result[0].commentId).toBe("c1");
    expect(result[0].isAi).toBe(false);
  });

  test("text search miss returns empty ranges", () => {
    createView("Hello world.");
    const comment = makeComment({
      anchor_text: "not found anywhere",
    });
    const result = resolveCommentAnchors([comment], "page1", view, null, null);
    expect(result).toEqual([]);
  });

  test("sets isAi flag for AI persona comments", () => {
    createView("Hello world, this is a test document.");
    const comment = makeComment({
      anchor_text: "Hello world",
      ai_persona: "socrates",
    });

    const result = resolveCommentAnchors([comment], "page1", view, null, null);

    expect(result).toHaveLength(1);
    expect(result[0].isAi).toBe(true);
  });

  test("multiple comments produce multiple ranges", () => {
    createView("First sentence. Second sentence. Third sentence.");
    const comments = [
      makeComment({
        external_id: "c1",
        anchor_text: "First sentence",
      }),
      makeComment({
        external_id: "c2",
        anchor_text: "Third sentence",
      }),
    ];

    const result = resolveCommentAnchors(comments, "page1", view, null, null);

    expect(result).toHaveLength(2);
    expect(result[0].commentId).toBe("c1");
    expect(result[1].commentId).toBe("c2");
  });

  test("comment with empty anchor_text and no binary anchors produces no range", () => {
    createView("Hello world.");
    const comment = makeComment({
      anchor_text: "",
      anchor_from_b64: null,
      anchor_to_b64: null,
    });
    const result = resolveCommentAnchors([comment], "page1", view, null, null);
    expect(result).toEqual([]);
  });

  // --- Clamping tests (BUG-2 fixed: clamp before from < to check) ---

  test("negative from with to=0 produces no range after clamping", () => {
    createView("Hello world.");

    // Simulate binary anchors that resolve to from=-5, to=0
    Y.decodeRelativePosition.mockReturnValue("mock");
    Y.createAbsolutePositionFromRelativePosition
      .mockReturnValueOnce({ index: -5 }) // from
      .mockReturnValueOnce({ index: 0 }); // to

    const ydoc = {}; // mock ydoc
    const comment = makeComment({
      anchor_from_b64: "AAAA",
      anchor_to_b64: "BBBB",
    });

    const result = resolveCommentAnchors([comment], "page1", view, ydoc, null);

    // After clamping: from=0, to=0 → from < to fails → no range
    expect(result).toEqual([]);
  });

  test("to beyond doc.length gets clamped to doc.length", () => {
    createView("Short"); // doc.length = 5

    Y.decodeRelativePosition.mockReturnValue("mock");
    Y.createAbsolutePositionFromRelativePosition
      .mockReturnValueOnce({ index: 3 }) // from
      .mockReturnValueOnce({ index: 100 }); // to (beyond doc.length)

    const ydoc = {};
    const comment = makeComment({
      anchor_from_b64: "AAAA",
      anchor_to_b64: "BBBB",
    });

    const result = resolveCommentAnchors([comment], "page1", view, ydoc, null);

    // Clamping: from=3, to=min(5,100)=5 → from < to passes → valid range
    expect(result).toHaveLength(1);
    expect(result[0].from).toBe(3);
    expect(result[0].to).toBe(5);
  });

  test("from equals to produces no range", () => {
    createView("Hello world.");

    Y.decodeRelativePosition.mockReturnValue("mock");
    Y.createAbsolutePositionFromRelativePosition
      .mockReturnValueOnce({ index: 5 })
      .mockReturnValueOnce({ index: 5 });

    const ydoc = {};
    const comment = makeComment({
      anchor_from_b64: "AAAA",
      anchor_to_b64: "BBBB",
    });

    const result = resolveCommentAnchors([comment], "page1", view, ydoc, null);
    expect(result).toEqual([]);
  });

  test("from greater than to produces no range", () => {
    createView("Hello world.");

    Y.decodeRelativePosition.mockReturnValue("mock");
    Y.createAbsolutePositionFromRelativePosition
      .mockReturnValueOnce({ index: 10 })
      .mockReturnValueOnce({ index: 5 });

    const ydoc = {};
    const comment = makeComment({
      anchor_from_b64: "AAAA",
      anchor_to_b64: "BBBB",
    });

    const result = resolveCommentAnchors([comment], "page1", view, ydoc, null);
    expect(result).toEqual([]);
  });

  // --- Binary anchor resolution ---

  test("resolves binary anchors via Yjs when ydoc is provided", () => {
    createView("Hello world, this is a test.");

    Y.decodeRelativePosition.mockReturnValue("mock");
    Y.createAbsolutePositionFromRelativePosition
      .mockReturnValueOnce({ index: 6 }) // from
      .mockReturnValueOnce({ index: 11 }); // to

    const ydoc = {};
    const comment = makeComment({
      anchor_from_b64: "AAAA",
      anchor_to_b64: "BBBB",
    });

    const result = resolveCommentAnchors([comment], "page1", view, ydoc, null);

    expect(result).toHaveLength(1);
    expect(result[0].from).toBe(6);
    expect(result[0].to).toBe(11);
    expect(Y.decodeRelativePosition).toHaveBeenCalledTimes(2);
  });

  test("falls back to text search when binary anchor resolution returns null", () => {
    createView("Hello world, this is a test.");

    Y.decodeRelativePosition.mockReturnValue("mock");
    Y.createAbsolutePositionFromRelativePosition.mockReturnValue(null);

    const ydoc = {};
    const comment = makeComment({
      anchor_from_b64: "AAAA",
      anchor_to_b64: "BBBB",
      anchor_text: "this is a test",
    });

    const result = resolveCommentAnchors([comment], "page1", view, ydoc, null);

    // Binary anchors failed (returned null), should fall back to text search
    expect(result).toHaveLength(1);
    expect(result[0].from).toBe(13);
    expect(result[0].to).toBe(27);
  });

  test("skips binary anchors when ydoc is null", () => {
    createView("Hello world, this is a test.");
    const comment = makeComment({
      anchor_from_b64: "AAAA",
      anchor_to_b64: "BBBB",
      anchor_text: "this is a test",
    });

    const result = resolveCommentAnchors([comment], "page1", view, null, null);

    // ydoc is null, so binary path is skipped, falls back to text search
    expect(Y.decodeRelativePosition).not.toHaveBeenCalled();
    expect(result).toHaveLength(1);
    expect(result[0].from).toBe(13);
  });

  // --- Deferred resolution (PATCH back to server) ---

  test("triggers deferred resolution PATCH when text found and no binary anchors", () => {
    createView("Hello world, this is a test.");

    const mockYtext = {}; // mock ytext
    const comment = makeComment({
      anchor_from_b64: null,
      anchor_to_b64: null,
      anchor_text: "this is a test",
    });

    resolveCommentAnchors([comment], "page1", view, null, mockYtext);

    expect(updateComment).toHaveBeenCalledWith("page1", "c1", {
      anchor_from_b64: expect.any(String),
      anchor_to_b64: expect.any(String),
    });
  });

  test("does not trigger PATCH when binary anchors already exist", () => {
    createView("Hello world, this is a test.");

    Y.decodeRelativePosition.mockReturnValue("mock");
    Y.createAbsolutePositionFromRelativePosition
      .mockReturnValueOnce({ index: 13 })
      .mockReturnValueOnce({ index: 27 });

    const ydoc = {};
    const mockYtext = {};
    const comment = makeComment({
      anchor_from_b64: "AAAA",
      anchor_to_b64: "BBBB",
      anchor_text: "this is a test",
    });

    resolveCommentAnchors([comment], "page1", view, ydoc, mockYtext);

    // Binary anchors resolved successfully, no PATCH needed
    expect(updateComment).not.toHaveBeenCalled();
  });

  test("does not trigger PATCH when ytext is null", () => {
    createView("Hello world, this is a test.");
    const comment = makeComment({
      anchor_from_b64: null,
      anchor_to_b64: null,
      anchor_text: "this is a test",
    });

    resolveCommentAnchors([comment], "page1", view, null, null);

    // No ytext means we can't create RelativePositions, so no PATCH
    expect(updateComment).not.toHaveBeenCalled();
  });

  // --- Mixed scenarios ---

  test("processes mix of root and reply comments correctly", () => {
    createView("First part. Second part. Third part.");
    const comments = [
      makeComment({
        external_id: "root1",
        anchor_text: "First part",
      }),
      makeComment({
        external_id: "reply1",
        parent_id: "root1",
        anchor_text: "Second part",
      }),
      makeComment({
        external_id: "root2",
        anchor_text: "Third part",
      }),
    ];

    const result = resolveCommentAnchors(comments, "page1", view, null, null);

    // Only root comments produce ranges, reply is skipped
    expect(result).toHaveLength(2);
    expect(result[0].commentId).toBe("root1");
    expect(result[1].commentId).toBe("root2");
  });
});
