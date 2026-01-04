/**
 * Read-only page viewer using the same CodeMirror setup as the editor.
 * This ensures identical rendering between edit and read-only views.
 */

import { markdown } from "@codemirror/lang-markdown";
import { EditorState } from "@codemirror/state";
import { Decoration, EditorView, ViewPlugin } from "@codemirror/view";

import { decorateEmails } from "./decorateEmails.js";
import {
  codeFenceField,
  HEADING_REGEX,
  CHECKBOX_REGEX,
  BULLET_REGEX,
} from "./decorateFormatting.js";
import { decorateLinks } from "./decorateLinks.js";
import { markdownTableExtension } from "./markdownTable.js";

import "./style.css";

const readOnlyFormatting = ViewPlugin.fromClass(
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

      for (const { from, to } of view.visibleRanges) {
        const startLine = state.doc.lineAt(from).number;
        const endLine = state.doc.lineAt(to).number;

        for (let i = startLine; i <= endLine; i++) {
          const line = state.doc.line(i);

          const headingMatch = line.text.match(HEADING_REGEX);
          if (headingMatch) {
            const level = headingMatch[1].length;
            const hashEnd = line.from + headingMatch[1].length + 1;

            builder.push(Decoration.replace({}).range(line.from, hashEnd));

            if (line.to > hashEnd) {
              builder.push(
                Decoration.mark({ class: `format-heading format-h${level}` }).range(
                  hashEnd,
                  line.to
                )
              );
            }

            builder.push(
              Decoration.line({ class: `format-heading-line format-h${level}-line` }).range(
                line.from
              )
            );
            continue;
          }

          const checkboxMatch = line.text.match(CHECKBOX_REGEX);
          if (checkboxMatch) {
            const indent = checkboxMatch[1].length;
            const indentLevel = Math.floor(indent / 2);
            const isChecked = checkboxMatch[2].toLowerCase() === "x";
            const checkboxStart = line.from + indent;
            const checkboxEnd = checkboxStart + 6; // "- [ ] " is 6 chars
            const textStart = checkboxEnd;

            // Hide indent
            if (indent > 0) {
              builder.push(Decoration.replace({}).range(line.from, line.from + indent));
            }

            // Replace "- [ ] " with checkbox widget
            builder.push(
              Decoration.replace({ widget: new CheckboxWidget(isChecked) }).range(
                checkboxStart,
                checkboxEnd
              )
            );

            const classes = ["format-list-item", "format-checkbox-item"];
            if (indentLevel > 0) classes.push(`format-indent-${Math.min(indentLevel, 10)}`);

            builder.push(Decoration.line({ class: classes.join(" ") }).range(line.from));

            // Strike through checked items
            if (isChecked && line.to > textStart) {
              builder.push(
                Decoration.mark({ class: "format-checkbox-checked" }).range(textStart, line.to)
              );
            }
            continue;
          }

          const bulletMatch = line.text.match(BULLET_REGEX);
          if (bulletMatch) {
            const indent = bulletMatch[1].length;
            const indentLevel = Math.floor(indent / 2);
            const dashPos = line.from + indent;

            // Hide indent
            if (indent > 0) {
              builder.push(Decoration.replace({}).range(line.from, line.from + indent));
            }

            // Replace "-" with bullet widget
            builder.push(
              Decoration.replace({ widget: new BulletWidget() }).range(dashPos, dashPos + 1)
            );

            const classes = ["format-list-item", "format-bullet-item"];
            if (indentLevel > 0) classes.push(`format-indent-${Math.min(indentLevel, 10)}`);

            builder.push(Decoration.line({ class: classes.join(" ") }).range(line.from));
            continue;
          }
        }
      }

      return Decoration.set(builder, true);
    }
  },
  { decorations: (v) => v.decorations }
);

import { WidgetType } from "@codemirror/view";

class CheckboxWidget extends WidgetType {
  constructor(checked) {
    super();
    this.checked = checked;
  }

  toDOM() {
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = this.checked;
    checkbox.disabled = true;
    checkbox.className = "format-checkbox";
    return checkbox;
  }

  eq(other) {
    return other.checked === this.checked;
  }
}

class BulletWidget extends WidgetType {
  toDOM() {
    const span = document.createElement("span");
    span.className = "format-bullet";
    span.textContent = "•";
    return span;
  }

  eq() {
    return true;
  }
}

function initializeViewer(content, container, filetype = "md") {
  const simpleTheme = EditorView.theme(
    {
      "&": {
        color: "black",
        backgroundColor: "white",
      },
      ".cm-content": {
        caretColor: "black",
        color: "black",
      },
      ".cm-line": {
        color: "black",
      },
      ".cm-cursor": {
        display: "none",
      },
      ".cm-selectionBackground": {
        backgroundColor: "#b3d7ff",
      },
    },
    { dark: false }
  );

  const monospaceTheme = EditorView.theme({
    ".cm-content": {
      fontFamily: '"SF Mono", "Monaco", "Inconsolata", "Roboto Mono", "Source Code Pro", monospace',
      fontSize: "14px",
      lineHeight: "1.5",
    },
    ".cm-line": {
      fontFamily: '"SF Mono", "Monaco", "Inconsolata", "Roboto Mono", "Source Code Pro", monospace',
    },
  });

  const isTxt = filetype === "txt";

  const extensions = [
    simpleTheme,
    ...(isTxt ? [monospaceTheme] : []),
    EditorView.lineWrapping,
    EditorView.editable.of(false),
    EditorState.readOnly.of(true),
    ...(isTxt ? [] : [markdown(), markdownTableExtension]),
    ...(isTxt ? [] : [codeFenceField, readOnlyFormatting]),
    decorateEmails,
    decorateLinks,
  ];

  const view = new EditorView({
    parent: container,
    state: EditorState.create({
      doc: content || "",
      extensions,
    }),
  });

  return view;
}

// Initialize viewer when DOM is ready
document.addEventListener("DOMContentLoaded", () => {
  const container = document.getElementById("viewer");
  const dataEl = document.getElementById("page-data");

  if (container && dataEl) {
    try {
      const data = JSON.parse(dataEl.textContent || "{}");
      const content = data.content || "";
      const filetype = data.filetype || "md";
      initializeViewer(content, container, filetype);
    } catch (e) {
      console.error("Failed to parse page data:", e);
      container.textContent = "Error loading page content";
    }
  }
});
