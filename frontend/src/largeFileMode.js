/**
 * Large File Mode Extension
 *
 * Detects large files and provides a UI indicator and performance optimizations.
 * Files over LARGE_FILE_THRESHOLD get a visual indicator.
 * Files over HUGE_FILE_THRESHOLD get minimal decorations for maximum performance.
 */

import { StateField, StateEffect, Facet } from "@codemirror/state";
import { EditorView, ViewPlugin, Decoration, showPanel } from "@codemirror/view";
import { LARGE_FILE_BYTES, HUGE_FILE_BYTES } from "./config/performance.js";

export const LARGE_FILE_THRESHOLD = LARGE_FILE_BYTES;
export const HUGE_FILE_THRESHOLD = HUGE_FILE_BYTES;

export const largeFileModeEffect = StateEffect.define();

export const largeFileModeField = StateField.define({
  create(state) {
    return computeFileMode(state.doc.length);
  },
  update(value, tr) {
    if (tr.docChanged) {
      return computeFileMode(tr.state.doc.length);
    }
    for (const e of tr.effects) {
      if (e.is(largeFileModeEffect)) {
        return e.value;
      }
    }
    return value;
  },
});

function computeFileMode(docLength) {
  if (docLength >= HUGE_FILE_THRESHOLD) {
    return "huge";
  } else if (docLength >= LARGE_FILE_THRESHOLD) {
    return "large";
  }
  return "normal";
}

export function isLargeFile(state) {
  const mode = state.field(largeFileModeField, false);
  return mode === "large" || mode === "huge";
}

export function isHugeFile(state) {
  const mode = state.field(largeFileModeField, false);
  return mode === "huge";
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function createPanelDom(mode, docLength) {
  const dom = document.createElement("div");
  dom.className = "cm-large-file-indicator";

  const icon = document.createElement("span");
  icon.className = "cm-large-file-icon";
  icon.textContent = mode === "huge" ? "⚡" : "📄";

  const text = document.createElement("span");
  text.className = "cm-large-file-text";
  const size = formatSize(docLength);

  if (mode === "huge") {
    text.textContent = `Large file mode (${size}) - Minimal decorations enabled`;
    dom.classList.add("cm-huge-file");
  } else {
    text.textContent = `Large file (${size})`;
    dom.classList.add("cm-large-file");
  }

  dom.appendChild(icon);
  dom.appendChild(text);

  return dom;
}

export const largeFilePanelExtension = showPanel.compute([largeFileModeField], (state) => {
  const mode = state.field(largeFileModeField, false);
  if (mode === "normal") return null;
  return (view) => ({
    dom: createPanelDom(mode, view.state.doc.length),
    top: true,
  });
});

const largeFilePanelPlugin = ViewPlugin.fromClass(
  class {
    constructor(view) {
      this.lastMode = view.state.field(largeFileModeField, false);
    }

    update(update) {
      const newMode = update.state.field(largeFileModeField, false);
      if (newMode !== this.lastMode) {
        this.lastMode = newMode;
      }
    }
  }
);

export const largeFileModeStyles = EditorView.baseTheme({
  ".cm-large-file-indicator": {
    display: "flex",
    alignItems: "center",
    gap: "6px",
    padding: "4px 12px",
    fontSize: "12px",
    fontFamily: "system-ui, -apple-system, sans-serif",
    borderBottom: "1px solid #e0e0e0",
    backgroundColor: "#f8f9fa",
  },
  ".cm-large-file-indicator.cm-large-file": {
    backgroundColor: "#fff8e1",
    borderColor: "#ffecb3",
    color: "#8d6e00",
  },
  ".cm-large-file-indicator.cm-huge-file": {
    backgroundColor: "#fff3e0",
    borderColor: "#ffccbc",
    color: "#d84315",
  },
  ".cm-large-file-icon": {
    fontSize: "14px",
  },
  ".cm-large-file-text": {
    fontWeight: "500",
  },
  "&.cm-focused .cm-large-file-indicator": {
    opacity: "0.9",
  },
});

export function skipDecorationsForHugeFiles(decorationExtension) {
  return EditorView.decorations.compute([largeFileModeField], (state) => {
    if (isHugeFile(state)) {
      return Decoration.none;
    }
    return null;
  });
}

export const largeFileModeExtension = [
  largeFileModeField,
  largeFilePanelExtension,
  largeFilePanelPlugin,
  largeFileModeStyles,
];

export function conditionalDecoration(extension, options = {}) {
  const { skipForHuge = true, skipForLarge = false } = options;

  return [
    extension,
    EditorView.decorations.compute([largeFileModeField], (state) => {
      const mode = state.field(largeFileModeField, false);
      if (skipForHuge && mode === "huge") return Decoration.none;
      if (skipForLarge && (mode === "large" || mode === "huge")) return Decoration.none;
      return null;
    }),
  ];
}
