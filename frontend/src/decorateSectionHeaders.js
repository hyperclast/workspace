import { Decoration, ViewPlugin } from "@codemirror/view";

const HEADING_REGEX = /^(#{1,6})\s+(.*)$/;
const TABLE_HEADER_REGEX = /^\|.*\|$/;
const TABLE_SEPARATOR_REGEX = /^\|[\s:-]+\|$/;

function isTableLine(text) {
  return TABLE_HEADER_REGEX.test(text) || TABLE_SEPARATOR_REGEX.test(text);
}

function isInsideTableContext(doc, lineNumber) {
  if (lineNumber > 1) {
    const prevLine = doc.line(lineNumber - 1);
    if (isTableLine(prevLine.text)) return true;
  }

  if (lineNumber < doc.lines) {
    const nextLine = doc.line(lineNumber + 1);
    if (TABLE_SEPARATOR_REGEX.test(nextLine.text)) return true;
  }

  return false;
}

export const decorateSectionHeaders = ViewPlugin.fromClass(
  class {
    constructor(view) {
      this.decorations = this.computeDecorations(view);
    }

    update(update) {
      if (update.docChanged || update.viewportChanged) {
        this.decorations = this.computeDecorations(update.view);
      }
    }

    computeDecorations(view) {
      const builder = [];
      const { state } = view;
      const headDeco = Decoration.line({ class: "section-header" });

      for (const { from, to } of view.visibleRanges) {
        const startLine = state.doc.lineAt(from).number;
        const endLine = state.doc.lineAt(to).number;

        for (let lineNum = startLine; lineNum <= endLine; lineNum++) {
          const line = state.doc.line(lineNum);
          const match = line.text.match(HEADING_REGEX);

          if (match && !isInsideTableContext(state.doc, lineNum)) {
            builder.push(headDeco.range(line.from));
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
