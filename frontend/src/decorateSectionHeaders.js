import { Decoration, ViewPlugin } from "@codemirror/view";
import { getSections } from "./getSections.js";
import { findTableRanges, isInsideTable } from "./markdownTable.js";

const DEBOUNCE_MS = 200;

export const decorateSectionHeaders = ViewPlugin.fromClass(
  class {
    constructor(view) {
      this.view = view;
      this.decorations = this.computeDecorations(view);
      this.timeout = null;
    }

    update(update) {
      if (update.docChanged || update.viewportChanged) {
        clearTimeout(this.timeout);

        this.timeout = setTimeout(() => {
          // Check if view is destroyed before attempting update
          if (!this.view || this.view.destroyed) {
            clearTimeout(this.timeout);
            return;
          }

          this.decorations = this.computeDecorations(this.view);

          // Force a redraw so CodeMirror applies our updated decorations.
          // (We're not changing document content — this is an idiomatic CM pattern
          // when decorations are updated outside a transaction.)
          // See the "Decorations" section in the official guide for context.
          this.view.update([]);
        }, DEBOUNCE_MS);
      }
    }

    computeDecorations(view) {
      const builder = [];
      const { state } = view;
      const headDeco = Decoration.line({ class: "section-header" });

      const sections = getSections(state.doc);
      const text = state.doc.toString();
      const tableRanges = findTableRanges(text);

      for (const section of sections) {
        // Skip section headers that are inside markdown tables
        if (!isInsideTable(section.from, tableRanges)) {
          builder.push(headDeco.range(section.from));
        }
      }

      return Decoration.set(builder, true);
    }

    destroy() {
      clearTimeout(this.timeout);
    }
  },
  {
    decorations: (v) => v.decorations,
  },
);
