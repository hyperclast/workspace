import { describe, test, expect, afterEach } from "vitest";
import { flattenDiffChunks, makeDiffDecorationExtension } from "../../rewind/diffDecorations.js";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";

describe("flattenDiffChunks", () => {
  test("produces correct text and lineTypes", () => {
    const chunks = [
      { type: "unchanged", lines: ["a"] },
      { type: "added", lines: ["b", "c"] },
      { type: "removed", lines: ["d"] },
    ];

    const result = flattenDiffChunks(chunks);

    expect(result.text).toBe("a\nb\nc\nd");
    expect(result.lineTypes).toEqual(["unchanged", "added", "added", "removed"]);
    expect(result.firstChangedLine).toBe(2);
  });

  test("returns null firstChangedLine when all unchanged", () => {
    const chunks = [{ type: "unchanged", lines: ["a", "b"] }];

    const result = flattenDiffChunks(chunks);

    expect(result.text).toBe("a\nb");
    expect(result.lineTypes).toEqual(["unchanged", "unchanged"]);
    expect(result.firstChangedLine).toBeNull();
  });

  test("handles empty chunks array", () => {
    const result = flattenDiffChunks([]);

    expect(result.text).toBe("");
    expect(result.lineTypes).toEqual([]);
    expect(result.firstChangedLine).toBeNull();
  });
});

describe("makeDiffDecorationExtension", () => {
  let view;

  afterEach(() => {
    if (view && !view.destroyed) {
      view.destroy();
    }
  });

  test("applies correct CSS classes to diff lines", () => {
    const lineTypes = ["added", "unchanged", "removed"];
    const plugin = makeDiffDecorationExtension(lineTypes);

    view = new EditorView({
      state: EditorState.create({
        doc: "line1\nline2\nline3",
        extensions: [plugin],
      }),
      parent: document.createElement("div"),
    });

    const lines = view.dom.querySelectorAll(".cm-line");
    expect(lines.length).toBe(3);

    expect(lines[0].classList.contains("rewind-cm-line-added")).toBe(true);
    expect(lines[1].classList.contains("rewind-cm-line-added")).toBe(false);
    expect(lines[1].classList.contains("rewind-cm-line-removed")).toBe(false);
    expect(lines[2].classList.contains("rewind-cm-line-removed")).toBe(true);
  });
});
