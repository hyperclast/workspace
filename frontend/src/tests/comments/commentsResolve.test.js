/**
 * Comments Resolve — Sidebar Behavior Tests
 *
 * Tests for the resolve/unresolve feature in CommentsTab.svelte:
 * 1. Source-level verification of structural patterns (resolve button placement,
 *    resolved card class, localStorage key)
 * 2. Pure logic tests for getVisibleComments and getResolvedCount
 *    (re-implemented here since they're internal to the Svelte component)
 */

import { describe, test, expect, vi, beforeEach, afterEach } from "vitest";
import { readFileSync } from "fs";
import { resolve } from "path";

const source = readFileSync(
  resolve(__dirname, "../../lib/components/sidebar/CommentsTab.svelte"),
  "utf-8"
);

// --- Pure logic: re-implement the internal filter/count functions ---
// These mirror the logic in CommentsTab.svelte exactly.

function getVisibleComments(comments, showResolved) {
  if (showResolved) return comments;
  return comments.filter((c) => !c.is_resolved);
}

function getResolvedCount(comments) {
  return comments.filter((c) => !c.parent_id && c.is_resolved).length;
}

function canResolve(currentPageRole) {
  return currentPageRole === "admin" || currentPageRole === "editor";
}

// --- Fixtures ---

function makeComment(overrides = {}) {
  return {
    external_id: "c1",
    parent_id: null,
    is_resolved: false,
    body: "A comment",
    ai_persona: null,
    ...overrides,
  };
}

// =============================================================================
// 1. Source-Level Pattern Verification
// =============================================================================

describe("CommentsTab resolve — source patterns", () => {
  test("resolve button is inside a root-only + canResolve guard", () => {
    // The resolve button (.comment-resolve-btn) must only render for root
    // comments when the user has edit access.
    const guardPattern =
      /\{#if !comment\.parent_id && canResolve\(\)\}[\s\S]*?comment-resolve-btn[\s\S]*?\{\/if\}/;
    expect(source).toMatch(guardPattern);
  });

  test("canResolve checks currentPageRole for admin or editor", () => {
    const canResolveFn = source.match(/function canResolve\(\)\s*\{[\s\S]*?\}/);
    expect(canResolveFn).not.toBeNull();
    expect(canResolveFn[0]).toContain('currentPageRole === "admin"');
    expect(canResolveFn[0]).toContain('currentPageRole === "editor"');
  });

  test("currentPageRole is set from window.getCurrentPage on page change", () => {
    // Verify that the page change handler reads role from the global page object
    expect(source).toContain("window.getCurrentPage?.()?.role");
  });

  test("resolve button does NOT appear in the renderReply snippet", () => {
    // Extract the renderReply snippet body
    const snippetMatch = source.match(/\{#snippet renderReply\([\s\S]*?\{\/snippet\}/);
    expect(snippetMatch).not.toBeNull();
    const renderReplySource = snippetMatch[0];
    expect(renderReplySource).not.toContain("comment-resolve-btn");
  });

  test("comment-card-resolved class is applied via class directive", () => {
    // Verify the resolved class is bound reactively with class:comment-card-resolved
    expect(source).toContain("class:comment-card-resolved={comment.is_resolved}");
  });

  test("localStorage key for showResolved is 'comments-show-resolved'", () => {
    // Verify the localStorage key used for persistence
    expect(source).toContain('localStorage.getItem("comments-show-resolved")');
    expect(source).toContain('localStorage.setItem("comments-show-resolved"');
  });

  test("toggleShowResolved calls resolveAndHighlight after toggling", () => {
    // Verify that editor highlights are refreshed when toggling visibility
    const toggleFn = source.match(/function toggleShowResolved\(\)\s*\{[\s\S]*?\}/);
    expect(toggleFn).not.toBeNull();
    expect(toggleFn[0]).toContain("resolveAndHighlight()");
  });

  test("root Reply button is disabled when comment.is_resolved", () => {
    // The root comment's Reply button should check is_resolved
    // Look for the pattern in the main comment card (not in renderReply snippet)
    const rootReplyPattern = /disabled=\{comment\.is_resolved \|\| comment\.can_reply === false\}/;
    expect(source).toMatch(rootReplyPattern);
  });

  test("reply Reply button receives threadResolved parameter", () => {
    // renderReply's Reply button should use the threadResolved parameter
    const replyBtnPattern = /disabled=\{threadResolved \|\| reply\.can_reply === false\}/;
    expect(source).toMatch(replyBtnPattern);
  });

  test("handleResolve shows specific 403 toast", () => {
    const resolveFn = source.match(/async function handleResolve[\s\S]*?^  \}/m);
    expect(resolveFn).not.toBeNull();
    expect(resolveFn[0]).toContain("e.status === 403");
    expect(resolveFn[0]).toContain("edit access to resolve");
  });

  test("handleUnresolve shows specific 403 toast with 'unresolve' wording", () => {
    const unresolveFn = source.match(/async function handleUnresolve[\s\S]*?^  \}/m);
    expect(unresolveFn).not.toBeNull();
    expect(unresolveFn[0]).toContain("e.status === 403");
    expect(unresolveFn[0]).toContain("edit access to unresolve");
  });
});

// =============================================================================
// 2. Pure Logic Tests — getVisibleComments
// =============================================================================

describe("getVisibleComments", () => {
  test("returns all comments when showResolved is true", () => {
    const comments = [
      makeComment({ external_id: "c1", is_resolved: false }),
      makeComment({ external_id: "c2", is_resolved: true }),
      makeComment({ external_id: "c3", is_resolved: false }),
    ];

    const result = getVisibleComments(comments, true);
    expect(result).toHaveLength(3);
    expect(result).toBe(comments); // same reference, not a copy
  });

  test("filters out resolved comments when showResolved is false", () => {
    const comments = [
      makeComment({ external_id: "c1", is_resolved: false }),
      makeComment({ external_id: "c2", is_resolved: true }),
      makeComment({ external_id: "c3", is_resolved: false }),
    ];

    const result = getVisibleComments(comments, false);
    expect(result).toHaveLength(2);
    expect(result.map((c) => c.external_id)).toEqual(["c1", "c3"]);
  });

  test("returns empty array when all are resolved and showResolved is false", () => {
    const comments = [
      makeComment({ external_id: "c1", is_resolved: true }),
      makeComment({ external_id: "c2", is_resolved: true }),
    ];

    const result = getVisibleComments(comments, false);
    expect(result).toHaveLength(0);
  });

  test("returns all when none are resolved and showResolved is false", () => {
    const comments = [
      makeComment({ external_id: "c1", is_resolved: false }),
      makeComment({ external_id: "c2", is_resolved: false }),
    ];

    const result = getVisibleComments(comments, false);
    expect(result).toHaveLength(2);
  });

  test("handles empty comments array", () => {
    expect(getVisibleComments([], true)).toEqual([]);
    expect(getVisibleComments([], false)).toEqual([]);
  });
});

// =============================================================================
// 3. Pure Logic Tests — getResolvedCount
// =============================================================================

describe("getResolvedCount", () => {
  test("counts only resolved root comments", () => {
    const comments = [
      makeComment({ external_id: "c1", is_resolved: true, parent_id: null }),
      makeComment({ external_id: "c2", is_resolved: false, parent_id: null }),
      makeComment({ external_id: "c3", is_resolved: true, parent_id: null }),
    ];

    expect(getResolvedCount(comments)).toBe(2);
  });

  test("ignores replies even if is_resolved is true", () => {
    // Replies always have is_resolved: false from the backend (DB constraint),
    // but this tests the filter defensively.
    const comments = [
      makeComment({ external_id: "root1", is_resolved: true, parent_id: null }),
      makeComment({ external_id: "reply1", is_resolved: true, parent_id: "root1" }),
    ];

    expect(getResolvedCount(comments)).toBe(1);
  });

  test("returns 0 when no comments are resolved", () => {
    const comments = [
      makeComment({ external_id: "c1", is_resolved: false }),
      makeComment({ external_id: "c2", is_resolved: false }),
    ];

    expect(getResolvedCount(comments)).toBe(0);
  });

  test("returns 0 for empty array", () => {
    expect(getResolvedCount([])).toBe(0);
  });

  test("counts correctly with mixed roots and replies", () => {
    const comments = [
      makeComment({ external_id: "root1", is_resolved: true, parent_id: null }),
      makeComment({ external_id: "root2", is_resolved: false, parent_id: null }),
      makeComment({ external_id: "root3", is_resolved: true, parent_id: null }),
      makeComment({ external_id: "reply1", is_resolved: false, parent_id: "root1" }),
      makeComment({ external_id: "reply2", is_resolved: false, parent_id: "root2" }),
    ];

    expect(getResolvedCount(comments)).toBe(2);
  });
});

// =============================================================================
// 4. Pure Logic Tests — canResolve
// =============================================================================

describe("canResolve", () => {
  test("returns true for admin role", () => {
    expect(canResolve("admin")).toBe(true);
  });

  test("returns true for editor role", () => {
    expect(canResolve("editor")).toBe(true);
  });

  test("returns false for viewer role", () => {
    expect(canResolve("viewer")).toBe(false);
  });

  test("returns false for null role", () => {
    expect(canResolve(null)).toBe(false);
  });

  test("returns false for undefined role", () => {
    expect(canResolve(undefined)).toBe(false);
  });

  test("returns false for empty string role", () => {
    expect(canResolve("")).toBe(false);
  });
});
