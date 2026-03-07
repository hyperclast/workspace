import { describe, test, expect } from "vitest";
import { computeDiff } from "../../rewind/diff.js";

describe("computeDiff", () => {
  describe("identical content", () => {
    test("returns empty chunks and zero stats for identical strings", () => {
      const result = computeDiff("hello\nworld", "hello\nworld");
      expect(result.chunks).toEqual([]);
      expect(result.stats.added).toBe(0);
      expect(result.stats.removed).toBe(0);
    });

    test("returns empty for both empty strings", () => {
      const result = computeDiff("", "");
      expect(result.chunks).toEqual([]);
      expect(result.stats.added).toBe(0);
      expect(result.stats.removed).toBe(0);
    });
  });

  describe("additions only", () => {
    test("empty to content counts all lines as added", () => {
      const result = computeDiff("", "line1\nline2\nline3\n");
      expect(result.stats.added).toBe(3);
      expect(result.stats.removed).toBe(0);
    });

    test("appending lines counts only new lines", () => {
      const result = computeDiff("line1\n", "line1\nline2\nline3\n");
      expect(result.stats.added).toBe(2);
      expect(result.stats.removed).toBe(0);
    });

    test("single line addition", () => {
      const result = computeDiff("a\nc\n", "a\nb\nc\n");
      expect(result.stats.added).toBe(1);
      expect(result.stats.removed).toBe(0);
    });
  });

  describe("deletions only", () => {
    test("content to empty counts all lines as removed", () => {
      const result = computeDiff("line1\nline2\nline3\n", "");
      expect(result.stats.removed).toBe(3);
      expect(result.stats.added).toBe(0);
    });

    test("removing lines from middle", () => {
      const result = computeDiff("a\nb\nc\n", "a\nc\n");
      expect(result.stats.removed).toBe(1);
      expect(result.stats.added).toBe(0);
    });
  });

  describe("replacements (mixed add/delete)", () => {
    test("replacing one line counts as 1 added + 1 removed", () => {
      const result = computeDiff("old\n", "new\n");
      expect(result.stats.added).toBe(1);
      expect(result.stats.removed).toBe(1);
    });

    test("replacing multiple lines", () => {
      const result = computeDiff("a\nb\nc\n", "x\ny\nz\n");
      expect(result.stats.added).toBe(3);
      expect(result.stats.removed).toBe(3);
    });
  });

  describe("chunks structure", () => {
    test("added lines produce added chunks", () => {
      const result = computeDiff("", "new line\n");
      const addedChunks = result.chunks.filter((c) => c.type === "added");
      expect(addedChunks.length).toBeGreaterThan(0);
      expect(addedChunks[0].lines).toContain("new line");
    });

    test("removed lines produce removed chunks", () => {
      const result = computeDiff("old line\n", "");
      const removedChunks = result.chunks.filter((c) => c.type === "removed");
      expect(removedChunks.length).toBeGreaterThan(0);
      expect(removedChunks[0].lines).toContain("old line");
    });

    test("unchanged lines produce unchanged chunks", () => {
      const result = computeDiff("keep\nadd\n", "keep\nchange\n");
      const unchangedChunks = result.chunks.filter((c) => c.type === "unchanged");
      expect(unchangedChunks.length).toBeGreaterThan(0);
    });
  });

  describe("tooLarge flag", () => {
    test("not set for small diffs", () => {
      const result = computeDiff("a\n", "b\n");
      expect(result.tooLarge).toBe(false);
    });

    test("set when changed lines exceed MAX_DIFF_LINES", () => {
      // MAX_DIFF_LINES = 5000; generate 5001 added lines (all-addition diff is
      // O(n) and avoids the O(n*m) worst-case of diffLines with fully-changed content)
      const newLines = Array.from({ length: 5001 }, (_, i) => `line${i}`).join("\n") + "\n";
      const result = computeDiff("", newLines);
      expect(result.tooLarge).toBe(true);
    });
  });

  describe("null/undefined handling", () => {
    test("null old content treated as empty", () => {
      const result = computeDiff(null, "line1\n");
      expect(result.stats.added).toBe(1);
      expect(result.stats.removed).toBe(0);
    });

    test("null new content treated as empty", () => {
      const result = computeDiff("line1\n", null);
      expect(result.stats.removed).toBe(1);
      expect(result.stats.added).toBe(0);
    });
  });
});
