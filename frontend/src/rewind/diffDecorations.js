/**
 * CodeMirror diff decoration helpers for formatted diff view.
 *
 * - flattenDiffChunks: converts diff chunks into a unified document string
 *   with per-line type annotations.
 * - makeDiffDecorationExtension: ViewPlugin that applies line-level background
 *   decorations (green/red) for added/removed lines, viewport-aware.
 */

import { Decoration, ViewPlugin } from "@codemirror/view";

/**
 * Flatten diff chunks into a single document string and a per-line type array.
 *
 * @param {Array<{type: 'added'|'removed'|'unchanged', lines: string[]}>} chunks
 * @returns {{ text: string, lineTypes: string[], firstChangedLine: number|null }}
 *   - text: all lines joined by \n (suitable for EditorState.create({ doc }))
 *   - lineTypes[i]: type for line i+1 (1-indexed lines, 0-indexed array)
 *   - firstChangedLine: 1-indexed line number of the first add/remove, or null
 */
export function flattenDiffChunks(chunks) {
  const allLines = [];
  const lineTypes = [];
  let firstChangedLine = null;

  for (const chunk of chunks) {
    for (const line of chunk.lines) {
      allLines.push(line);
      lineTypes.push(chunk.type);
      if (firstChangedLine === null && chunk.type !== "unchanged") {
        firstChangedLine = allLines.length; // 1-indexed
      }
    }
  }

  return {
    text: allLines.join("\n"),
    lineTypes,
    firstChangedLine,
  };
}

/**
 * Create a ViewPlugin that decorates lines with diff background colors.
 *
 * Follows the decorateSectionHeaders.js pattern:
 * - Pre-allocates Decoration.line singletons
 * - Iterates only view.visibleRanges
 * - Rebuilds on viewportChanged (doc is read-only, so docChanged is rare)
 *
 * @param {string[]} lineTypes - per-line type array from flattenDiffChunks
 * @returns {ViewPlugin}
 */
export function makeDiffDecorationExtension(lineTypes) {
  const addedDeco = Decoration.line({ class: "rewind-cm-line-added" });
  const removedDeco = Decoration.line({ class: "rewind-cm-line-removed" });

  return ViewPlugin.fromClass(
    class {
      constructor(view) {
        this.decorations = this.computeDecorations(view);
      }

      update(update) {
        if (update.viewportChanged || update.docChanged) {
          this.decorations = this.computeDecorations(update.view);
        }
      }

      computeDecorations(view) {
        const builder = [];
        const { state } = view;

        for (const { from, to } of view.visibleRanges) {
          const startLine = state.doc.lineAt(from).number;
          const endLine = state.doc.lineAt(to).number;

          for (let lineNum = startLine; lineNum <= endLine; lineNum++) {
            const type = lineTypes[lineNum - 1];
            if (type === "added") {
              builder.push(addedDeco.range(state.doc.line(lineNum).from));
            } else if (type === "removed") {
              builder.push(removedDeco.range(state.doc.line(lineNum).from));
            }
          }
        }

        return Decoration.set(builder, true);
      }
    },
    {
      decorations: (v) => v.decorations,
    }
  );
}
