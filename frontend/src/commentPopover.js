/**
 * Inline comment popover — appears when text is selected in the editor.
 *
 * Flow: select text → comment button appears → click → textarea form opens →
 * user types and submits → comment created via API → popover closes.
 *
 * Uses CodeMirror's showTooltip facet so the popover lives inside the editor
 * DOM and does not steal focus or clear the selection.
 */

import * as Y from "yjs";
import { StateField, StateEffect } from "@codemirror/state";
import { showTooltip, Decoration, EditorView, keymap } from "@codemirror/view";
import { createComment } from "./api.js";

// --- Effects ---

const openCommentForm = StateEffect.define();
const closeCommentPopover = StateEffect.define();

// --- State ---

const IDLE = { stage: "idle" };

function makeFormState(from, to, text, anchorFromB64, anchorToB64) {
  return { stage: "form", from, to, text, anchorFromB64, anchorToB64 };
}

// --- Tooltip DOM builders ---

function stripTooltipChrome(dom) {
  // CM wraps tooltip content in a .cm-tooltip div with default bg/border/shadow.
  // We strip those styles once the tooltip is mounted.
  requestAnimationFrame(() => {
    const wrapper = dom.closest(".cm-tooltip");
    if (wrapper) {
      wrapper.style.background = "none";
      wrapper.style.border = "none";
      wrapper.style.boxShadow = "none";
    }
  });
}

function createButtonTooltip(view) {
  const dom = document.createElement("div");
  dom.className = "cm-comment-popover-button";
  // Commented aria-label below as it is shown as mouseover text by Firefox, which messes up the UI
  // Button text can be used for accessibility
  // dom.setAttribute("aria-label", "Add comment");
  stripTooltipChrome(dom);

  const btn = document.createElement("button");
  btn.type = "button";
  const isMac = /Mac|iPhone|iPad/.test(navigator.platform);
  const shortcut = isMac ? "\u2318\u2325M" : "Ctrl+Alt+M";
  btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg><span>Comment</span><span class="cm-comment-popover-shortcut">${shortcut}</span>`;
  btn.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();

    const sel = view.state.selection.main;
    if (sel.from === sel.to) return;

    const text = view.state.doc.sliceString(sel.from, sel.to);
    let anchorFromB64 = null;
    let anchorToB64 = null;

    if (window.ydoc && window.ytext) {
      try {
        const fromRelPos = Y.createRelativePositionFromTypeIndex(window.ytext, sel.from);
        const toRelPos = Y.createRelativePositionFromTypeIndex(window.ytext, sel.to);
        anchorFromB64 = btoa(String.fromCharCode(...Y.encodeRelativePosition(fromRelPos)));
        anchorToB64 = btoa(String.fromCharCode(...Y.encodeRelativePosition(toRelPos)));
      } catch (e) {
        console.error("[CommentPopover] Failed to create RelativePositions:", e);
      }
    }

    view.dispatch({
      effects: openCommentForm.of({ from: sel.from, to: sel.to, text, anchorFromB64, anchorToB64 }),
    });
  });

  dom.appendChild(btn);
  return { dom };
}

function createFormTooltip(view) {
  const state = view.state.field(commentPopoverField);
  const dom = document.createElement("div");
  dom.className = "cm-comment-popover-form";

  // Override the CM tooltip wrapper to be transparent — the form provides its own chrome
  requestAnimationFrame(() => {
    const wrapper = dom.closest(".cm-tooltip");
    if (wrapper) {
      wrapper.style.border = "none";
    }
  });

  // Quoted anchor text
  const quote = document.createElement("div");
  quote.className = "cm-comment-popover-quote";
  const quoteText = state.text.length > 80 ? state.text.slice(0, 77) + "..." : state.text;
  quote.textContent = `"${quoteText}"`;
  dom.appendChild(quote);

  // Textarea
  const textarea = document.createElement("textarea");
  textarea.className = "cm-comment-popover-textarea";
  textarea.placeholder = "Add a comment...";
  textarea.rows = 3;
  dom.appendChild(textarea);

  // Error message area
  const errorEl = document.createElement("div");
  errorEl.className = "cm-comment-popover-error";
  dom.appendChild(errorEl);

  // Actions
  const actions = document.createElement("div");
  actions.className = "cm-comment-popover-actions";

  const cancelBtn = document.createElement("button");
  cancelBtn.type = "button";
  cancelBtn.className = "cm-comment-popover-cancel";
  cancelBtn.textContent = "Cancel";
  cancelBtn.addEventListener("click", (e) => {
    e.preventDefault();
    view.dispatch({ effects: closeCommentPopover.of(null) });
    view.focus();
  });

  const submitBtn = document.createElement("button");
  submitBtn.type = "button";
  submitBtn.className = "cm-comment-popover-submit";
  submitBtn.textContent = "Comment";
  submitBtn.addEventListener("click", async (e) => {
    e.preventDefault();
    const body = textarea.value.trim();
    if (!body) return;

    const pageId = window.getCurrentPage?.()?.external_id;
    if (!pageId) return;

    submitBtn.disabled = true;
    submitBtn.textContent = "...";

    try {
      await createComment(pageId, {
        body,
        anchor_text: state.text,
        anchor_from_b64: state.anchorFromB64,
        anchor_to_b64: state.anchorToB64,
        parent_id: null,
      });
      const sel = view.state.selection.main;
      view.dispatch({
        effects: closeCommentPopover.of(null),
        selection: { anchor: sel.to },
      });
      view.focus();
      window.dispatchEvent(new CustomEvent("commentsUpdated"));
    } catch (err) {
      console.error("[CommentPopover] Submit failed:", err);
      errorEl.textContent = "Failed to post comment.";
      submitBtn.disabled = false;
      submitBtn.textContent = "Comment";
    }
  });

  actions.appendChild(cancelBtn);
  actions.appendChild(submitBtn);
  dom.appendChild(actions);

  // Keyboard shortcut hint
  const hint = document.createElement("div");
  hint.className = "cm-comment-popover-hint";
  const isMac = /Mac|iPhone|iPad/.test(navigator.platform);
  hint.textContent = isMac ? "\u2318 Enter" : "Ctrl + Enter";
  dom.appendChild(hint);

  // Keyboard: Escape to cancel, Cmd/Ctrl+Enter to submit
  textarea.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      e.preventDefault();
      view.dispatch({ effects: closeCommentPopover.of(null) });
      view.focus();
    }
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      submitBtn.click();
    }
  });

  // Auto-focus textarea after tooltip is mounted
  requestAnimationFrame(() => textarea.focus());

  return { dom };
}

// --- StateField ---

const selectionHighlightMark = Decoration.mark({ class: "cm-comment-popover-selection" });

const commentPopoverField = StateField.define({
  create() {
    return IDLE;
  },

  update(value, tr) {
    for (const effect of tr.effects) {
      if (effect.is(openCommentForm)) {
        const { from, to, text, anchorFromB64, anchorToB64 } = effect.value;
        return makeFormState(from, to, text, anchorFromB64, anchorToB64);
      }
      if (effect.is(closeCommentPopover)) {
        return IDLE;
      }
    }
    return value;
  },

  provide(field) {
    return [
      showTooltip.compute([field], (state) => {
        const val = state.field(field);
        if (val.stage === "form") {
          return {
            pos: val.from,
            end: val.to,
            above: true,
            strictSide: false,
            arrow: false,
            create: (view) => createFormTooltip(view),
          };
        }
        return null;
      }),
      EditorView.decorations.compute([field], (state) => {
        const val = state.field(field);
        if (val.stage === "form" && val.from < val.to) {
          return Decoration.set([selectionHighlightMark.range(val.from, val.to)]);
        }
        return Decoration.none;
      }),
    ];
  },
});

// --- Selection watcher: shows button tooltip when text is selected ---

const commentButtonTooltip = StateField.define({
  create() {
    return null;
  },

  update(value, tr) {
    // If the form is open, hide the button
    const popoverState = tr.state.field(commentPopoverField);
    if (popoverState.stage === "form") return null;

    // Show button when there's a non-empty selection
    const sel = tr.state.selection.main;
    if (sel.from !== sel.to) {
      // Anchor to the end of the last line of the selection (not sel.to,
      // which may be on a distant line after trailing blank lines).
      const lastLine = tr.state.doc.lineAt(sel.to);
      const anchorPos =
        sel.to === lastLine.from && sel.to > sel.from
          ? tr.state.doc.lineAt(sel.to - 1).to // sel.to is at line start — use previous line end
          : sel.to;
      return {
        pos: anchorPos,
        above: false,
        arrow: false,
        create: (view) => createButtonTooltip(view),
      };
    }
    return null;
  },

  provide(field) {
    return showTooltip.from(field);
  },
});

// --- Theme ---

const commentPopoverTheme = EditorView.baseTheme({
  ".cm-comment-popover-button": {
    padding: "0",
  },
  ".cm-comment-popover-button button": {
    borderRadius: "6px",
    border: "none",
    background: "#2383e2",
    color: "#fff",
    fontSize: "13px",
    fontWeight: "500",
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    gap: "6px",
    padding: "6px 12px",
    boxShadow: "0 2px 8px rgba(35, 131, 226, 0.3)",
    lineHeight: "1",
    whiteSpace: "nowrap",
    transition: "background 0.1s",
  },
  ".cm-comment-popover-button button:hover": {
    background: "#1a6fc2",
  },
  ".cm-comment-popover-form": {
    width: "320px",
    padding: "12px 14px",
    background: "#fff",
    borderRadius: "8px",
    boxShadow: "0 4px 16px rgba(0,0,0,0.08), 0 0 0 1px rgba(55,53,47,0.06)",
    border: "none",
    display: "flex",
    flexDirection: "column",
    gap: "8px",
  },
  ".cm-comment-popover-quote": {
    fontSize: "13px",
    color: "rgba(55, 53, 47, 0.5)",
    fontStyle: "italic",
    borderLeft: "2px solid rgba(55, 53, 47, 0.12)",
    paddingLeft: "8px",
    maxHeight: "38px",
    overflow: "hidden",
    textOverflow: "ellipsis",
    lineHeight: "1.4",
  },
  ".cm-comment-popover-textarea": {
    width: "100%",
    minHeight: "60px",
    padding: "8px 10px",
    border: "1px solid rgba(55, 53, 47, 0.12)",
    borderRadius: "4px",
    fontSize: "14px",
    fontFamily: "inherit",
    resize: "vertical",
    boxSizing: "border-box",
    outline: "none",
    lineHeight: "1.5",
    color: "#37352f",
    transition: "border-color 0.1s, box-shadow 0.1s",
  },
  ".cm-comment-popover-textarea:focus": {
    borderColor: "#2383e2",
    boxShadow: "0 0 0 2px rgba(35, 131, 226, 0.15)",
  },
  ".cm-comment-popover-error": {
    fontSize: "13px",
    color: "#eb5757",
    minHeight: "0",
  },
  ".cm-comment-popover-actions": {
    display: "flex",
    justifyContent: "flex-end",
    alignItems: "center",
    gap: "6px",
  },
  ".cm-comment-popover-cancel": {
    fontSize: "13px",
    color: "rgba(55, 53, 47, 0.5)",
    background: "none",
    border: "none",
    cursor: "pointer",
    padding: "5px 10px",
    borderRadius: "4px",
    transition: "background 0.1s",
  },
  ".cm-comment-popover-cancel:hover": {
    background: "rgba(55, 53, 47, 0.06)",
  },
  ".cm-comment-popover-submit": {
    fontSize: "13px",
    fontWeight: "500",
    color: "#fff",
    background: "#2383e2",
    border: "none",
    borderRadius: "4px",
    cursor: "pointer",
    padding: "5px 14px",
    transition: "background 0.1s",
  },
  ".cm-comment-popover-submit:hover": {
    background: "#1a6fc2",
  },
  ".cm-comment-popover-submit:disabled": {
    opacity: "0.5",
    cursor: "not-allowed",
  },
  ".cm-comment-popover-hint": {
    fontSize: "12px",
    color: "rgba(55, 53, 47, 0.35)",
    textAlign: "right",
  },
  ".cm-comment-popover-shortcut": {
    fontSize: "12px",
    color: "rgba(255, 255, 255, 0.6)",
    marginLeft: "2px",
  },
  ".cm-comment-popover-selection": {
    backgroundColor: "rgba(255, 212, 0, 0.25)",
    borderRadius: "2px",
  },
  // Dark mode
  "&dark .cm-comment-popover-button button": {
    background: "#529cca",
    boxShadow: "0 2px 8px rgba(82, 156, 202, 0.3)",
  },
  "&dark .cm-comment-popover-button button:hover": {
    background: "#6bb3dd",
  },
  "&dark .cm-comment-popover-form": {
    background: "#202020",
    boxShadow: "0 4px 16px rgba(0,0,0,0.3), 0 0 0 1px rgba(255,255,255,0.06)",
  },
  "&dark .cm-comment-popover-quote": {
    color: "rgba(255, 255, 255, 0.4)",
    borderLeftColor: "rgba(255, 255, 255, 0.1)",
  },
  "&dark .cm-comment-popover-textarea": {
    background: "#191919",
    borderColor: "rgba(255,255,255,0.1)",
    color: "#ebebeb",
  },
  "&dark .cm-comment-popover-textarea:focus": {
    borderColor: "#529cca",
    boxShadow: "0 0 0 2px rgba(82, 156, 202, 0.2)",
  },
  "&dark .cm-comment-popover-cancel": {
    color: "rgba(255, 255, 255, 0.4)",
  },
  "&dark .cm-comment-popover-cancel:hover": {
    background: "rgba(255, 255, 255, 0.06)",
  },
  "&dark .cm-comment-popover-submit": {
    background: "#529cca",
  },
  "&dark .cm-comment-popover-submit:hover": {
    background: "#6bb3dd",
  },
  "&dark .cm-comment-popover-shortcut": {
    color: "rgba(255, 255, 255, 0.6)",
  },
  "&dark .cm-comment-popover-hint": {
    color: "rgba(255, 255, 255, 0.25)",
  },
  "&dark .cm-comment-popover-selection": {
    backgroundColor: "rgba(255, 212, 0, 0.15)",
  },
});

// --- Keybinding: Cmd+Alt+M (Ctrl+Alt+M on Win/Linux) opens comment form ---

function openCommentFormCommand(view) {
  const sel = view.state.selection.main;
  if (sel.from === sel.to) return false;

  const text = view.state.doc.sliceString(sel.from, sel.to);
  let anchorFromB64 = null;
  let anchorToB64 = null;

  if (window.ydoc && window.ytext) {
    try {
      const fromRelPos = Y.createRelativePositionFromTypeIndex(window.ytext, sel.from);
      const toRelPos = Y.createRelativePositionFromTypeIndex(window.ytext, sel.to);
      anchorFromB64 = btoa(String.fromCharCode(...Y.encodeRelativePosition(fromRelPos)));
      anchorToB64 = btoa(String.fromCharCode(...Y.encodeRelativePosition(toRelPos)));
    } catch (e) {
      console.error("[CommentPopover] Failed to create RelativePositions:", e);
    }
  }

  view.dispatch({
    effects: openCommentForm.of({ from: sel.from, to: sel.to, text, anchorFromB64, anchorToB64 }),
  });
  return true;
}

const commentKeymap = keymap.of([{ key: "Mod-Alt-m", run: openCommentFormCommand }]);

// --- Exported extension ---

export const commentPopover = [
  commentPopoverField,
  commentButtonTooltip,
  commentPopoverTheme,
  commentKeymap,
];
