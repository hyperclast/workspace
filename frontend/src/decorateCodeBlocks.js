import { Decoration, ViewPlugin, WidgetType, EditorView } from "@codemirror/view";
import { showToast } from "./lib/toast.js";
import { highlightTree } from "@lezer/highlight";
import { classHighlighter } from "@lezer/highlight";
import {
  getLanguage,
  isLanguageSupported,
  languageDisplayNames,
  languageOptions,
} from "./codeSyntax/languageLoader.js";

const CODE_FENCE_REGEX = /^```(\w*)$/;

// Cache for loaded language parsers
const loadedLanguages = new Map();
// Track pending language loads to avoid duplicates
const pendingLoads = new Set();

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
    btn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>`;
    btn.dataset.codeBlockStart = this.codeBlockStart;
    btn.dataset.codeBlockEnd = this.codeBlockEnd;
    btn.dataset.unclosed = this.unclosed ? "true" : "false";
    return btn;
  }

  ignoreEvent() {
    return false;
  }
}

class LanguageSelectorWidget extends WidgetType {
  constructor(fenceLine, lang) {
    super();
    this.fenceLine = fenceLine;
    this.lang = lang || "";
  }

  eq(other) {
    return this.fenceLine === other.fenceLine && this.lang === other.lang;
  }

  toDOM() {
    const wrapper = document.createElement("div");
    wrapper.className = "code-block-lang-selector";

    const displayName = languageDisplayNames[this.lang?.toLowerCase()] || this.lang || "Plain Text";

    const btn = document.createElement("button");
    btn.className = "lang-selector-btn";
    btn.dataset.fenceLine = this.fenceLine;
    btn.innerHTML = `<span class="lang-name">${displayName}</span><span class="lang-chevron">▾</span>`;

    wrapper.appendChild(btn);
    wrapper.dataset.fenceLine = this.fenceLine;
    wrapper.dataset.currentLang = this.lang || "";

    return wrapper;
  }

  ignoreEvent() {
    return false;
  }
}

function computeCodeFencesInRange(state, startLine, endLine) {
  const fences = [];
  let inCodeBlock = false;
  let codeBlockStart = null;
  let codeBlockLang = null;

  for (let i = startLine; i <= endLine; i++) {
    const line = state.doc.line(i);
    const match = CODE_FENCE_REGEX.exec(line.text);
    if (match) {
      if (!inCodeBlock) {
        inCodeBlock = true;
        codeBlockStart = i;
        codeBlockLang = match[1] || null;
      } else {
        fences.push({ start: codeBlockStart, end: i, unclosed: false, lang: codeBlockLang });
        inCodeBlock = false;
        codeBlockStart = null;
        codeBlockLang = null;
      }
    }
  }

  if (inCodeBlock && codeBlockStart !== null) {
    fences.push({ start: codeBlockStart, end: endLine, unclosed: true, lang: codeBlockLang });
  }

  return fences;
}

function highlightCodeBlock(state, block, langSupport) {
  const decorations = [];
  const contentStart = block.start + 1;
  const contentEnd = block.unclosed ? block.end : block.end - 1;

  if (contentStart > contentEnd) return decorations;

  // Extract code content
  const lines = [];
  let codeStartPos = null;
  for (let i = contentStart; i <= contentEnd; i++) {
    if (i > state.doc.lines) break;
    const line = state.doc.line(i);
    if (codeStartPos === null) codeStartPos = line.from;
    lines.push(line.text);
  }

  if (lines.length === 0 || codeStartPos === null) return decorations;

  const code = lines.join("\n");
  const parser = langSupport.language.parser;

  // Parse the code
  const tree = parser.parse(code);

  // Walk the syntax tree and create decorations
  highlightTree(tree, classHighlighter, (from, to, classes) => {
    if (classes) {
      decorations.push(
        Decoration.mark({ class: classes }).range(codeStartPos + from, codeStartPos + to)
      );
    }
  });

  return decorations;
}

export const decorateCodeBlocks = ViewPlugin.fromClass(
  class {
    constructor(view) {
      this.decorations = this.computeDecorations(view);
    }

    update(update) {
      // Recompute on doc change, viewport change, or any transaction (for async language loads)
      if (update.docChanged || update.viewportChanged || update.transactions.length > 0) {
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

          // Add language selector widget
          builder.push(
            Decoration.widget({
              widget: new LanguageSelectorWidget(block.start, block.lang),
              side: 1,
            }).range(contentStartLine.from)
          );

          // Add copy button widget
          builder.push(
            Decoration.widget({
              widget: new CopyButtonWidget(block.start, block.end, block.unclosed),
              side: 1,
            }).range(contentStartLine.from)
          );

          // Add syntax highlighting if language is supported and loaded
          if (block.lang && isLanguageSupported(block.lang)) {
            const langKey = block.lang.toLowerCase();
            if (loadedLanguages.has(langKey)) {
              const langSupport = loadedLanguages.get(langKey);
              const highlightDecos = highlightCodeBlock(state, block, langSupport);
              builder.push(...highlightDecos);
            } else if (!pendingLoads.has(langKey)) {
              // Start loading the language
              pendingLoads.add(langKey);
              getLanguage(block.lang).then((langSupport) => {
                if (langSupport) {
                  loadedLanguages.set(langKey, langSupport);
                  // Trigger re-render by dispatching an empty transaction
                  view.dispatch({});
                }
                pendingLoads.delete(langKey);
              });
            }
          }
        }
      }

      return Decoration.set(
        builder.sort((a, b) => a.from - b.from),
        true
      );
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
    btn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>`;
    showToast("Copied to clipboard", "success", 2000);

    setTimeout(() => {
      btn.classList.remove("copied");
      btn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>`;
    }, 2000);
  } catch (err) {
    console.error("Failed to copy:", err);
    showToast("Failed to copy to clipboard", "error");
  }
}

function showLanguageDropdown(button, fenceLine, currentLang) {
  // Remove any existing dropdown
  document.querySelector(".lang-dropdown-menu")?.remove();

  const menu = document.createElement("div");
  menu.className = "lang-dropdown-menu";

  for (const { code, name } of languageOptions) {
    const item = document.createElement("button");
    item.className = "lang-dropdown-item";
    if (code === currentLang || (code === "" && !currentLang)) {
      item.classList.add("selected");
    }
    item.textContent = name;
    item.dataset.langCode = code;
    item.dataset.fenceLine = fenceLine;
    menu.appendChild(item);
  }

  // Position near the button
  const rect = button.getBoundingClientRect();
  menu.style.position = "fixed";
  menu.style.top = `${rect.bottom + 4}px`;
  menu.style.left = `${rect.left}px`;

  document.body.appendChild(menu);

  // Close on outside click (use setTimeout to avoid immediate close)
  setTimeout(() => {
    const closeMenu = (e) => {
      if (!menu.contains(e.target) && !button.contains(e.target)) {
        menu.remove();
        document.removeEventListener("click", closeMenu, true);
      }
    };
    document.addEventListener("click", closeMenu, true);
  }, 0);
}

function changeCodeBlockLanguage(view, fenceLine, newLang) {
  const line = view.state.doc.line(fenceLine);
  const newText = "```" + newLang;

  view.dispatch({
    changes: {
      from: line.from,
      to: line.to,
      insert: newText,
    },
  });
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

// Language selector click handlers
let langSelectorHandlerAttached = false;

function setupGlobalLangSelectorHandler() {
  if (langSelectorHandlerAttached) return;
  langSelectorHandlerAttached = true;

  // Handle language selector button click
  document.addEventListener(
    "click",
    (event) => {
      const langBtn = event.target.closest(".lang-selector-btn");
      if (langBtn) {
        event.preventDefault();
        event.stopPropagation();
        const fenceLine = parseInt(langBtn.dataset.fenceLine, 10);
        const wrapper = langBtn.closest(".code-block-lang-selector");
        const currentLang = wrapper?.dataset.currentLang || "";
        showLanguageDropdown(langBtn, fenceLine, currentLang);
        return;
      }

      // Handle dropdown item click
      const dropdownItem = event.target.closest(".lang-dropdown-item");
      if (dropdownItem) {
        event.preventDefault();
        event.stopPropagation();
        const newLang = dropdownItem.dataset.langCode;
        const fenceLine = parseInt(dropdownItem.dataset.fenceLine, 10);

        // Find editor view from the DOM
        const cmContent = document.querySelector(".cm-content");
        if (cmContent) {
          const editorView = EditorView.findFromDOM(cmContent);
          if (editorView) {
            changeCodeBlockLanguage(editorView, fenceLine, newLang);
          }
        }

        // Close dropdown
        document.querySelector(".lang-dropdown-menu")?.remove();
      }
    },
    true
  );

  // Prevent mousedown from moving cursor when clicking selector
  document.addEventListener(
    "mousedown",
    (event) => {
      const langBtn = event.target.closest(".lang-selector-btn");
      const dropdownItem = event.target.closest(".lang-dropdown-item");
      if (langBtn || dropdownItem) {
        event.stopPropagation();
      }
    },
    true
  );
}

setupGlobalLangSelectorHandler();
