<script>
  /**
   * Selection-driven comment popover for PDF pages.
   *
   * Subscribes to the `selection` store published by PdfPageView via
   * `PDF_PAGE_CONTEXT`. On selection:
   *   1. Shows a small "Comment" button next to the selection.
   *   2. On click, expands to a textarea form.
   *   3. On submit, POSTs to /api/v1/pages/{id}/comments/ with a pdf_anchor.
   *
   * v1 scope: rejects multi-page selections.
   */
  import { getContext, onMount } from "svelte";
  import { createComment } from "../api.js";
  import { rangeToPdfAnchor, rangeSpansMultiplePages } from "./pdfAnchor.js";
  import { PDF_PAGE_CONTEXT } from "./pdfPageContext.js";

  let { pageId } = $props();

  const ctx = getContext(PDF_PAGE_CONTEXT);
  let pagesSnapshot = []; // mirrors ctx.pages so handleSelection can look up viewports synchronously

  let open = $state(false);
  let stage = $state("button"); // "button" | "form"
  let style = $state("");
  let body = $state("");
  let submitting = $state(false);
  let errorMsg = $state("");

  // Captured at the moment selection became valid:
  let pendingAnchor = null;
  let pendingViewport = null;
  let pendingPage = null;

  function showAt(rect) {
    // The PDF viewer scrolls inside .pdf-page-view (overflow: auto), so
    // window.scrollY is always 0 for this view. Position the popover in
    // the scrolling container's content coordinate system instead — that
    // way it scrolls with the selection rather than staying pinned to the
    // window top.
    const container = document.querySelector(".pdf-page-view");
    if (container) {
      const cRect = container.getBoundingClientRect();
      const top = rect.top - cRect.top + container.scrollTop - 36;
      const left = rect.right - cRect.left + container.scrollLeft + 4;
      style = `top: ${top}px; left: ${left}px;`;
    } else {
      // Fallback: window-relative (matches legacy behaviour if the
      // container isn't found for any reason).
      const top = window.scrollY + rect.top - 36;
      const left = window.scrollX + rect.right + 4;
      style = `top: ${top}px; left: ${left}px;`;
    }
    open = true;
  }

  function close() {
    open = false;
    stage = "button";
    body = "";
    errorMsg = "";
    pendingAnchor = null;
    pendingViewport = null;
    pendingPage = null;
  }

  function handleSelection(payload) {
    const { range, pageNumber } = payload || {};
    if (!range) return;

    if (rangeSpansMultiplePages(range)) {
      errorMsg = "Multi-page selections are not supported in v1.";
      // Show a transient toast-like notice at the selection.
      const r = range.getBoundingClientRect();
      showAt(r);
      stage = "error";
      return;
    }

    const meta = pagesSnapshot.find((p) => p.pageNumber === pageNumber);
    if (!meta) return;

    const wrapper = document.querySelector(`[data-pdf-page="${pageNumber}"]`);
    if (!wrapper) return;

    const anchor = rangeToPdfAnchor(range, pageNumber, wrapper, meta.viewport);
    if (!anchor) return;

    pendingAnchor = anchor;
    pendingViewport = meta.viewport;
    pendingPage = pageNumber;

    const r = range.getBoundingClientRect();
    showAt(r);
  }

  function expandToForm() {
    stage = "form";
  }

  async function submit() {
    if (!pendingAnchor || !body.trim() || submitting) return;
    submitting = true;
    errorMsg = "";
    try {
      await createComment(pageId, { body: body.trim(), pdf_anchor: pendingAnchor });
      // Notify other listeners (CommentsTab + overlay) so they can refetch.
      window.dispatchEvent(new CustomEvent("commentsUpdated", { detail: { pageId } }));
      close();
    } catch (err) {
      console.error("[PdfCommentPopover] failed to create comment:", err);
      errorMsg = "Failed to save comment. Please try again.";
    } finally {
      submitting = false;
    }
  }

  function handleDocClick(event) {
    if (!open) return;
    const popover = document.getElementById("pdf-comment-popover");
    if (popover && !popover.contains(event.target)) {
      // Don't close while user is mid-selection on the text layer.
      const sel = document.getSelection();
      if (sel && !sel.isCollapsed) return;
      close();
    }
  }

  onMount(() => {
    const unsubscribePages = ctx.pages.subscribe((value) => {
      pagesSnapshot = value || [];
    });
    // Skip the initial null delivered on subscribe; only react to fresh
    // selections.
    let primed = false;
    const unsubscribeSelection = ctx.selection.subscribe((value) => {
      if (!primed) {
        primed = true;
        return;
      }
      if (value) handleSelection(value);
    });

    document.addEventListener("mousedown", handleDocClick);
    return () => {
      unsubscribePages();
      unsubscribeSelection();
      document.removeEventListener("mousedown", handleDocClick);
    };
  });
</script>

{#if open}
  <div id="pdf-comment-popover" class="pdf-comment-popover" style={style}>
    {#if stage === "button"}
      <button class="pdf-comment-btn" onclick={expandToForm}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
          stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
        <span>Comment</span>
      </button>
    {:else if stage === "form"}
      <div class="pdf-comment-form">
        <textarea
          rows="3"
          placeholder="Add a comment…"
          bind:value={body}
          disabled={submitting}
        ></textarea>
        {#if errorMsg}
          <div class="pdf-comment-error">{errorMsg}</div>
        {/if}
        <div class="pdf-comment-actions">
          <button class="pdf-comment-cancel" type="button" onclick={close} disabled={submitting}>
            Cancel
          </button>
          <button
            class="pdf-comment-submit"
            type="button"
            onclick={submit}
            disabled={!body.trim() || submitting}
          >
            {submitting ? "Saving…" : "Comment"}
          </button>
        </div>
      </div>
    {:else if stage === "error"}
      <div class="pdf-comment-form pdf-comment-form-error">
        <div class="pdf-comment-error">{errorMsg}</div>
        <div class="pdf-comment-actions">
          <button class="pdf-comment-submit" type="button" onclick={close}>Got it</button>
        </div>
      </div>
    {/if}
  </div>
{/if}

<style>
  .pdf-comment-popover {
    position: absolute;
    z-index: 10000;
    background: var(--bg-primary, white);
    border: 1px solid var(--border-color, #e0e0e0);
    border-radius: 6px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
    font-size: 13px;
  }

  .pdf-comment-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 10px;
    background: transparent;
    border: 0;
    color: var(--text-primary, #333);
    cursor: pointer;
    font-size: 13px;
  }

  .pdf-comment-btn:hover {
    background: var(--bg-hover, #f5f5f5);
    border-radius: 6px;
  }

  .pdf-comment-form {
    display: flex;
    flex-direction: column;
    width: 280px;
    padding: 8px;
    gap: 6px;
  }

  .pdf-comment-form textarea {
    width: 100%;
    resize: vertical;
    border: 1px solid var(--border-color, #e0e0e0);
    border-radius: 4px;
    padding: 6px 8px;
    font: inherit;
    box-sizing: border-box;
  }

  .pdf-comment-actions {
    display: flex;
    justify-content: flex-end;
    gap: 6px;
  }

  .pdf-comment-cancel,
  .pdf-comment-submit {
    border: 0;
    padding: 5px 10px;
    border-radius: 4px;
    font-size: 12px;
    cursor: pointer;
  }

  .pdf-comment-cancel {
    background: transparent;
    color: var(--text-secondary, #666);
  }

  .pdf-comment-submit {
    background: var(--accent, #2383e2);
    color: white;
  }

  .pdf-comment-submit:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .pdf-comment-error {
    color: #c0392b;
    font-size: 12px;
  }
</style>
