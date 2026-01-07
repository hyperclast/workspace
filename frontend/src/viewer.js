/**
 * Read-only page viewer using the same CodeMirror setup as the editor.
 * This ensures identical rendering between edit and read-only views.
 */

import { markdown } from "@codemirror/lang-markdown";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";

import { decorateEmails } from "./decorateEmails.js";
import { codeFenceField, decorateFormatting } from "./decorateFormatting.js";
import { decorateLinks } from "./decorateLinks.js";
import { markdownTableExtension } from "./markdownTable.js";

import "./style.css";

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
    ...(isTxt ? [] : [codeFenceField, decorateFormatting]),
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
