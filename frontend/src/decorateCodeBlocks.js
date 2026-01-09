import { Decoration, ViewPlugin, WidgetType, EditorView } from "@codemirror/view";
import { showToast } from "./lib/toast.js";

const CODE_FENCE_REGEX = /^```(\w*)$/;

class CopyButtonWidget extends WidgetType {
  constructor(codeBlockStart, codeBlockEnd, unclosed) {
    super();
    this.codeBlockStart = codeBlockStart;
    this.codeBlockEnd = codeBlockEnd;
    this.unclosed = unclosed;
  }

  eq(other) {
    return (
      other.codeBlockStart === this.codeBlockStart &&
      other.codeBlockEnd === this.codeBlockEnd &&
      other.unclosed === this.unclosed
    );
  }

  toDOM() {
    const btn = document.createElement("button");
    btn.className = "code-block-copy-btn";
    btn.title = "Copy code";
    btn.setAttribute("aria-label", "Copy code");
    btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>`;
    btn.dataset.codeBlockStart = this.codeBlockStart;
    btn.dataset.codeBlockEnd = this.codeBlockEnd;
    btn.dataset.unclosed = this.unclosed ? "true" : "false";
    return btn;
  }

  ignoreEvent() {
    return false;
  }
}

function computeCodeFencesInRange(state, startLine, endLine) {
  const fences = [];
  let inCodeBlock = false;
  let codeBlockStart = null;

  for (let i = startLine; i <= endLine; i++) {
    const line = state.doc.line(i);
    if (CODE_FENCE_REGEX.test(line.text)) {
      if (!inCodeBlock) {
        inCodeBlock = true;
        codeBlockStart = i;
      } else {
        fences.push({ start: codeBlockStart, end: i, unclosed: false });
        inCodeBlock = false;
        codeBlockStart = null;
      }
    }
  }

  if (inCodeBlock && codeBlockStart !== null) {
    fences.push({ start: codeBlockStart, end: endLine, unclosed: true });
  }

  return fences;
}

export const decorateCodeBlocks = ViewPlugin.fromClass(
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
      const processedBlocks = new Set();

      for (const { from, to } of view.visibleRanges) {
        const startLine = state.doc.lineAt(from).number;
        const endLine = state.doc.lineAt(to).number;

        const codeBlocks = computeCodeFencesInRange(state, startLine, endLine);

        for (const block of codeBlocks) {
          const blockKey = `${block.start}-${block.end}`;
          if (processedBlocks.has(blockKey)) continue;
          processedBlocks.add(blockKey);

          const firstContentLine = block.start + 1;
          if (firstContentLine > block.end) continue;
          if (block.unclosed && firstContentLine > state.doc.lines) continue;

          const contentStartLine = state.doc.line(firstContentLine);

          builder.push(
            Decoration.widget({
              widget: new CopyButtonWidget(block.start, block.end, block.unclosed),
              side: 1,
            }).range(contentStartLine.from)
          );
        }
      }

      return Decoration.set(builder, true);
    }
  },
  {
    decorations: (v) => v.decorations,
  }
);

function extractCodeContent(view, startLine, endLine, unclosed) {
  const state = view.state;
  const lines = [];

  const contentStart = startLine + 1;
  const contentEnd = unclosed ? endLine : endLine - 1;

  for (let i = contentStart; i <= contentEnd; i++) {
    if (i > state.doc.lines) break;
    const line = state.doc.line(i);
    lines.push(line.text);
  }

  return lines.join("\n");
}

async function handleCopyClick(btn) {
  const startLine = parseInt(btn.dataset.codeBlockStart, 10);
  const endLine = parseInt(btn.dataset.codeBlockEnd, 10);
  const unclosed = btn.dataset.unclosed === "true";

  const cmContent = btn.closest(".cm-content");
  if (!cmContent) return;

  const editorView = EditorView.findFromDOM(cmContent);
  if (!editorView) return;

  const code = extractCodeContent(editorView, startLine, endLine, unclosed);

  try {
    await navigator.clipboard.writeText(code);
    btn.classList.add("copied");
    btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>`;
    showToast("Copied to clipboard", "success", 2000);

    setTimeout(() => {
      btn.classList.remove("copied");
      btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>`;
    }, 2000);
  } catch (err) {
    console.error("Failed to copy:", err);
    showToast("Failed to copy to clipboard", "error");
  }
}

let copyHandlerAttached = false;

function setupGlobalCopyHandler() {
  if (copyHandlerAttached) return;
  copyHandlerAttached = true;

  document.addEventListener(
    "click",
    (event) => {
      const btn = event.target.closest(".code-block-copy-btn");
      if (!btn) return;
      event.preventDefault();
      event.stopPropagation();
      handleCopyClick(btn);
    },
    true
  );

  document.addEventListener(
    "mousedown",
    (event) => {
      const btn = event.target.closest(".code-block-copy-btn");
      if (!btn) return;
      event.stopPropagation();
    },
    true
  );
}

setupGlobalCopyHandler();
