/**
 * Read-only page viewer using the same CodeMirror setup as the editor.
 * This ensures identical rendering between edit and read-only views.
 */

import { markdown } from "@codemirror/lang-markdown";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";

import { decorateCodeBlocks } from "./decorateCodeBlocks.js";
import { decorateEmails } from "./decorateEmails.js";
import { codeFenceField, decorateFormatting } from "./decorateFormatting.js";
import { decorateLinks } from "./decorateLinks.js";
import { markdownTableExtension } from "./markdownTable.js";
import { initTheme } from "./theme.js";

import "./style.css";

function initializeViewer(content, container, filetype = "md") {
  const simpleTheme = EditorView.theme(
    {
      "&": {
        color: "var(--text-primary)",
        backgroundColor: "var(--bg-primary)",
      },
      ".cm-content": {
        caretColor: "var(--text-primary)",
        color: "var(--text-primary)",
      },
      ".cm-line": {
        color: "var(--text-primary)",
      },
      ".cm-cursor": {
        display: "none",
      },
      ".cm-selectionBackground": {
        backgroundColor: "var(--selection-bg)",
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
    ...(isTxt ? [] : [decorateCodeBlocks]),
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
  initTheme();

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
