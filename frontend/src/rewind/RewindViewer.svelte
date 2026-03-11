<script>
  import { onMount, onDestroy, tick } from "svelte";
  import { subscribe, getState, setViewMode, setDiffFormat, exitRewindMode } from "./index.js";
  import { computeDiff } from "./diff.js";
  import { flattenDiffChunks, makeDiffDecorationExtension } from "./diffDecorations.js";
  import { formatRelativeTime } from "./timeFormat.js";

  // CodeMirror imports for preview mode (lazy)
  let cmModulesLoaded = false;
  let cmModules = null;

  let state = $state(getState());
  let unsubscribe = null;
  let previewView = null;
  let previewContainer = null;
  let diffView = null;
  let rewindExitedHandler = null;

  let diffResult = $derived.by(() => {
    if (state.viewMode !== "diff" || state.selectedContent === null) return null;
    if (state.loadingDetail) return null;
    return computeDiff(state.previousContent || "", state.selectedContent || "");
  });

  onMount(() => {
    unsubscribe = subscribe((newState) => {
      state = newState;

      // When loading or leaving preview, destroy stale CM (DOM will be replaced)
      if (state.loadingDetail || state.viewMode !== "preview") {
        destroyPreview();
        previewContainer = null;
      }

      // Update preview if in preview mode and content changed
      if (state.viewMode === "preview" && state.selectedContent !== null && !state.loadingDetail) {
        tick().then(() => updatePreview(state.selectedContent));
      }

    });

    // Attach button handlers via getElementById (mount() caveat)
    const exitBtn = document.getElementById("rewind-exit-btn");
    const diffBtn = document.getElementById("rewind-diff-btn");
    const previewBtn = document.getElementById("rewind-preview-btn");
    const plainBtn = document.getElementById("rewind-plain-btn");
    const formattedBtn = document.getElementById("rewind-formatted-btn");

    const handleDiff = () => setViewMode("diff");
    const handlePreview = () => handlePreviewClick();
    const handlePlain = () => setDiffFormat("plain");
    const handleFormatted = () => setDiffFormat("formatted");

    exitBtn?.addEventListener("click", handleExit);
    diffBtn?.addEventListener("click", handleDiff);
    previewBtn?.addEventListener("click", handlePreview);
    plainBtn?.addEventListener("click", handlePlain);
    formattedBtn?.addEventListener("click", handleFormatted);

    previewContainer = document.getElementById("rewind-preview-container");

    // Listen for rewind exit to cleanup preview
    rewindExitedHandler = () => {
      destroyPreview();
      destroyDiff();
    };
    window.addEventListener("rewindExited", rewindExitedHandler);

    return () => {
      exitBtn?.removeEventListener("click", handleExit);
      diffBtn?.removeEventListener("click", handleDiff);
      previewBtn?.removeEventListener("click", handlePreview);
      plainBtn?.removeEventListener("click", handlePlain);
      formattedBtn?.removeEventListener("click", handleFormatted);
    };
  });

  onDestroy(() => {
    if (unsubscribe) unsubscribe();
    destroyPreview();
    destroyDiff();
    if (rewindExitedHandler) {
      window.removeEventListener("rewindExited", rewindExitedHandler);
    }
  });

  function handleExit() {
    exitRewindMode();
  }

  async function handlePreviewClick() {
    setViewMode("preview");
    await tick();
    if (state.selectedContent !== null) {
      await updatePreview(state.selectedContent);
    }
  }

  async function loadCmModules() {
    if (cmModulesLoaded) return cmModules;
    const [
      { EditorState },
      { EditorView },
      { markdown },
      { decorateCodeBlocks },
      { decorateEmails },
      { codeFenceField, decorateFormatting },
      { decorateLinks },
      { markdownTableExtension },
    ] = await Promise.all([
      import("@codemirror/state"),
      import("@codemirror/view"),
      import("@codemirror/lang-markdown"),
      import("../decorateCodeBlocks.js"),
      import("../decorateEmails.js"),
      import("../decorateFormatting.js"),
      import("../decorateLinks.js"),
      import("../markdownTable.js"),
    ]);
    cmModules = { EditorState, EditorView, markdown, decorateCodeBlocks, decorateEmails, codeFenceField, decorateFormatting, decorateLinks, markdownTableExtension };
    cmModulesLoaded = true;
    return cmModules;
  }

  async function updatePreview(content) {
    if (!previewContainer) {
      previewContainer = document.getElementById("rewind-preview-container");
    }
    if (!previewContainer) return;

    if (previewView) {
      // Update existing view content
      previewView.dispatch({
        changes: {
          from: 0,
          to: previewView.state.doc.length,
          insert: content || "",
        },
      });
      return;
    }

    // Create new CodeMirror read-only instance
    const cm = await loadCmModules();

    const simpleTheme = cm.EditorView.theme(
      {
        "&": {
          color: "var(--text-primary)",
          backgroundColor: "var(--bg-primary)",
        },
        ".cm-content": {
          caretColor: "var(--text-primary)",
          color: "var(--text-primary)",
        },
        ".cm-line": { color: "var(--text-primary)" },
        ".cm-cursor": { display: "none" },
        ".cm-selectionBackground": { backgroundColor: "var(--selection-bg)" },
      },
      { dark: false }
    );

    const extensions = [
      simpleTheme,
      cm.EditorView.lineWrapping,
      cm.EditorView.editable.of(false),
      cm.EditorState.readOnly.of(true),
      cm.markdown(),
      cm.markdownTableExtension,
      cm.codeFenceField,
      cm.decorateFormatting,
      cm.decorateCodeBlocks,
      cm.decorateEmails,
      cm.decorateLinks,
    ];

    previewView = new cm.EditorView({
      parent: previewContainer,
      state: cm.EditorState.create({
        doc: content || "",
        extensions,
      }),
    });
  }

  function scrollToFirstChange(node, getDiffResult) {
    let current = getDiffResult?.();
    doScroll();

    function doScroll() {
      // Double-rAF: first frame lets Svelte flush DOM, second lets browser layout
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          const anchor = node.querySelector(".rewind-diff-anchor");
          if (anchor) {
            anchor.scrollIntoView({ behavior: "smooth", block: "center" });
          }
        });
      });
    }

    return {
      update(newGetDiffResult) {
        const next = newGetDiffResult?.();
        if (next !== current) {
          current = next;
          doScroll();
        }
      },
    };
  }

  function destroyPreview() {
    if (previewView) {
      previewView.destroy();
      previewView = null;
    }
  }

  function destroyDiff() {
    if (diffView) {
      diffView.destroy();
      diffView = null;
    }
  }

  function mountDiffView(node, getDiffResult) {
    let diffResult = getDiffResult();
    buildDiffView(node, diffResult);

    return {
      update(newGetDiffResult) {
        const newDiffResult = newGetDiffResult();
        if (newDiffResult !== diffResult) {
          diffResult = newDiffResult;
          destroyDiff();
          buildDiffView(node, diffResult);
        }
      },
      destroy() {
        destroyDiff();
      },
    };
  }

  async function buildDiffView(node, diffResult) {
    if (!diffResult || diffResult.tooLarge || diffResult.chunks.length === 0) return;

    const { text, lineTypes, firstChangedLine } = flattenDiffChunks(diffResult.chunks);
    const cm = await loadCmModules();
    const diffDecoPlugin = makeDiffDecorationExtension(lineTypes);

    const simpleTheme = cm.EditorView.theme(
      {
        "&": {
          color: "var(--text-primary)",
          backgroundColor: "var(--bg-primary)",
        },
        ".cm-content": {
          caretColor: "var(--text-primary)",
          color: "var(--text-primary)",
        },
        ".cm-line": { color: "var(--text-primary)" },
        ".cm-cursor": { display: "none" },
        ".cm-selectionBackground": { backgroundColor: "var(--selection-bg)" },
      },
      { dark: false }
    );

    const extensions = [
      simpleTheme,
      cm.EditorView.lineWrapping,
      cm.EditorView.editable.of(false),
      cm.EditorState.readOnly.of(true),
      cm.markdown(),
      cm.markdownTableExtension,
      cm.codeFenceField,
      cm.decorateFormatting,
      cm.decorateCodeBlocks,
      cm.decorateEmails,
      cm.decorateLinks,
      diffDecoPlugin,
    ];

    diffView = new cm.EditorView({
      parent: node,
      state: cm.EditorState.create({
        doc: text,
        extensions,
      }),
    });

    // Smooth-scroll to first changed line. Two stages:
    // 1. Smooth scroll to lineBlockAt estimate (may be slightly off due to
    //    CM using estimated heights for unmeasured/off-screen lines).
    // 2. On scrollend, if the actual decorated element isn't visible, do a
    //    correction scroll — by then CM has rendered the target region.
    if (firstChangedLine !== null) {
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          if (!diffView) return;
          try {
            const scrollParent = node.closest(".rewind-diff");
            if (!scrollParent) return;

            const line = diffView.state.doc.line(firstChangedLine);
            const block = diffView.lineBlockAt(line.from);
            const nodeRect = node.getBoundingClientRect();
            const parentRect = scrollParent.getBoundingClientRect();
            const nodeTopInParent = nodeRect.top - parentRect.top + scrollParent.scrollTop;
            const targetY = nodeTopInParent + block.top - scrollParent.clientHeight / 3;
            scrollParent.scrollTo({ top: Math.max(0, targetY), behavior: "smooth" });

            // After scroll animation ends, verify and correct if needed
            scrollParent.addEventListener("scrollend", () => {
              if (!diffView) return;
              const el = scrollParent.querySelector(
                ".rewind-cm-line-added, .rewind-cm-line-removed"
              );
              if (!el) return;
              const eRect = el.getBoundingClientRect();
              const pRect = scrollParent.getBoundingClientRect();
              if (eRect.top >= pRect.bottom || eRect.bottom <= pRect.top) {
                el.scrollIntoView({ behavior: "smooth", block: "center" });
              }
            }, { once: true });
          } catch (e) {
            // line may be out of range
          }
        });
      });
    }
  }
</script>

<div class="rewind-viewer" id="rewind-viewer-inner">
  {#if state.isRewindMode && state.selectedEntry}
    <!-- Header -->
    <div class="rewind-viewer-header">
      <div class="rewind-viewer-header-info">
        <span class="rewind-viewer-title">v{state.selectedEntry.rewind_number}</span>
        {#if diffResult && !diffResult.tooLarge && diffResult.chunks.length > 0}
          <span class="rewind-header-sep">&middot;</span>
          <span class="rewind-stat-added">+{diffResult.stats.added}</span>
          <span class="rewind-stat-removed">-{diffResult.stats.removed}</span>
        {/if}
        <span class="rewind-header-sep">&middot;</span>
        <span class="rewind-viewer-time">{formatRelativeTime(state.selectedEntry.created)}</span>
        {#if state.selectedEntry.label}
          <span class="rewind-header-sep">&middot;</span>
          <span class="rewind-label-pill">{state.selectedEntry.label}</span>
        {/if}
        <span class="rewind-header-sep">&middot;</span>
        <span class="rewind-readonly-pill">Read-only</span>
      </div>
      <div class="rewind-viewer-actions">
        <div class="rewind-view-toggle">
          <button
            id="rewind-diff-btn"
            class="rewind-toggle-btn"
            class:active={state.viewMode === "diff"}
            onclick={() => setViewMode("diff")}
          >
            Diff
          </button>
          <button
            id="rewind-preview-btn"
            class="rewind-toggle-btn"
            class:active={state.viewMode === "preview"}
            onclick={() => handlePreviewClick()}
          >
            Preview
          </button>
        </div>
        <div class="rewind-view-toggle" class:disabled={state.viewMode !== "diff"} title={state.viewMode !== "diff" ? "Switch to Diff mode to change format" : null}>
          <button
            id="rewind-plain-btn"
            class="rewind-toggle-btn"
            class:active={state.viewMode === "diff" && state.diffFormat === "plain"}
            disabled={state.viewMode !== "diff"}
            onclick={() => setDiffFormat("plain")}
          >Plain</button>
          <button
            id="rewind-formatted-btn"
            class="rewind-toggle-btn"
            class:active={state.viewMode === "diff" && state.diffFormat === "formatted"}
            disabled={state.viewMode !== "diff"}
            onclick={() => setDiffFormat("formatted")}
          >Formatted</button>
        </div>
        <button id="rewind-exit-btn" class="rewind-exit-btn" onclick={handleExit}>
          <svg class="rewind-exit-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
          Exit Rewind
        </button>
      </div>
    </div>

    <!-- Content -->
    {#if state.loadingDetail}
      <div class="rewind-loading">Loading snapshot...</div>
    {:else if state.viewMode === "diff"}
      <div class="rewind-diff">
        {#if diffResult && diffResult.tooLarge}
          <div class="rewind-diff-too-large">
            <p>Diff too large ({diffResult.stats.added + diffResult.stats.removed} lines changed)</p>
            <button class="rewind-switch-preview-btn" onclick={() => handlePreviewClick()}>
              Switch to Preview
            </button>
          </div>
        {:else if diffResult && diffResult.chunks.length === 0}
          <div class="rewind-diff-empty">No changes from previous version.</div>
        {:else if diffResult}
          {#if state.diffFormat === "plain"}
            <div class="rewind-diff-content" use:scrollToFirstChange={() => diffResult}>
              {#each diffResult.chunks as chunk, i}
                {#if chunk.type !== "unchanged" && (i === 0 || diffResult.chunks[i - 1].type === "unchanged")}
                  <div class="rewind-diff-anchor"></div>
                {/if}
                {#each chunk.lines as line}
                  <div class="rewind-diff-line {chunk.type}">{#if chunk.type === 'added'}+{:else if chunk.type === 'removed'}-{:else}&nbsp;{/if} {line}</div>
                {/each}
              {/each}
            </div>
          {:else}
            <div class="rewind-diff-formatted">
              <div class="rewind-diff-formatted-inner">
                <div class="rewind-diff-title">{state.selectedEntry.title || "Untitled"}</div>
                <div class="rewind-diff-cm" use:mountDiffView={() => diffResult}></div>
              </div>
            </div>
          {/if}
        {/if}
      </div>
    {:else}
      <div class="rewind-preview">
        <div class="rewind-preview-inner">
          <div class="rewind-preview-title">{state.selectedEntry.title || "Untitled"}</div>
          <div id="rewind-preview-container"></div>
        </div>
      </div>
    {/if}
  {:else if state.isRewindMode}
    <div class="rewind-loading">Select an entry from the timeline.</div>
  {/if}
</div>

<style>
  .rewind-viewer {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
  }

  .rewind-viewer-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.625rem 1rem;
    border-bottom: 1px solid var(--border-light, rgba(0, 0, 0, 0.08));
    background: var(--bg-surface, #fafafa);
    flex-shrink: 0;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  .rewind-viewer-header-info {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    min-width: 0;
    flex: 1;
  }

  .rewind-viewer-title {
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--text-primary, #333);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .rewind-header-sep {
    color: var(--text-tertiary, #888);
    font-size: 0.75rem;
  }

  .rewind-viewer-time {
    font-size: 0.75rem;
    color: var(--text-tertiary, #888);
    white-space: nowrap;
  }

  .rewind-readonly-pill {
    font-size: 0.6875rem;
    font-weight: 500;
    color: #0969da;
    background: rgba(9, 105, 218, 0.08);
    padding: 0.125rem 0.5rem;
    border-radius: 9999px;
    white-space: nowrap;
  }

  .rewind-viewer-actions {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-shrink: 0;
  }

  .rewind-view-toggle {
    display: flex;
    border: 1px solid var(--border-light, rgba(0, 0, 0, 0.1));
    border-radius: 6px;
    overflow: hidden;
  }

  .rewind-toggle-btn {
    padding: 0.25rem 0.625rem;
    border: none;
    background: none;
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--text-secondary, #666);
    cursor: pointer;
    transition: background 0.15s, color 0.15s;
  }

  .rewind-toggle-btn:not(:last-child) {
    border-right: 1px solid var(--border-light, rgba(0, 0, 0, 0.1));
  }

  .rewind-toggle-btn.active {
    background: var(--bg-elevated, #f0f0f0);
    color: var(--text-primary, #333);
  }

  .rewind-toggle-btn:hover:not(.active):not(:disabled) {
    background: var(--bg-hover, rgba(0, 0, 0, 0.03));
  }

  .rewind-toggle-btn:disabled {
    opacity: 0.4;
    cursor: default;
  }

  .rewind-view-toggle.disabled {
    opacity: 0.5;
  }

  .rewind-exit-btn {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.25rem 0.75rem;
    border: 1px solid #cf222e;
    background: none;
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 500;
    color: #cf222e;
    cursor: pointer;
    transition: background 0.15s, color 0.15s;
  }

  .rewind-exit-icon {
    flex-shrink: 0;
  }

  .rewind-exit-btn:hover {
    background: rgba(207, 34, 46, 0.08);
    color: #b62324;
  }

  /* Loading */
  .rewind-loading {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 3rem;
    color: var(--text-secondary, #666);
    font-size: 0.875rem;
  }

  /* Diff view */
  .rewind-diff {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow-y: auto;
    padding: 0;
  }

  .rewind-diff-anchor {
    height: 0;
    overflow: hidden;
  }

  .rewind-stat-added {
    font-size: 0.75rem;
    font-weight: 600;
    color: #1a7f37;
    white-space: nowrap;
  }

  .rewind-stat-removed {
    font-size: 0.75rem;
    font-weight: 600;
    color: #cf222e;
    white-space: nowrap;
  }

  .rewind-diff-content {
    font-family: "SF Mono", "Monaco", "Inconsolata", "Roboto Mono", "Source Code Pro", monospace;
    font-size: 0.8125rem;
    line-height: 1.5;
  }

  .rewind-diff-line {
    padding: 0 1rem;
    white-space: pre-wrap;
    word-break: break-all;
  }

  .rewind-diff-line.added {
    background: rgba(26, 127, 55, 0.1);
    color: #1a7f37;
  }

  .rewind-diff-line.removed {
    background: rgba(207, 34, 46, 0.1);
    color: #cf222e;
  }

  .rewind-diff-line.unchanged {
    color: var(--text-primary, #333);
  }

  .rewind-diff-empty {
    padding: 2rem;
    text-align: center;
    color: var(--text-secondary, #666);
    font-size: 0.875rem;
  }

  .rewind-diff-too-large {
    padding: 2rem;
    text-align: center;
    color: var(--text-secondary, #666);
  }

  .rewind-diff-too-large p {
    margin: 0 0 0.75rem;
    font-size: 0.875rem;
  }

  .rewind-switch-preview-btn {
    padding: 0.375rem 1rem;
    border: 1px solid var(--border-light, rgba(0, 0, 0, 0.1));
    background: none;
    border-radius: 6px;
    font-size: 0.8125rem;
    color: #0969da;
    cursor: pointer;
    transition: background 0.15s;
  }

  .rewind-switch-preview-btn:hover {
    background: rgba(9, 105, 218, 0.06);
  }

  /* Formatted diff view — scrolls with parent .rewind-diff */
  .rewind-diff-formatted {
    padding: 0 var(--page-padding, 48px);
  }

  .rewind-diff-formatted-inner {
    max-width: var(--max-content-width, 800px);
    width: 100%;
    margin: 0 auto;
  }

  .rewind-diff-title {
    font-size: 2.25rem;
    font-weight: 700;
    color: var(--text-primary, #333);
    line-height: 1.2;
    letter-spacing: -0.02em;
    padding: 1rem 0 0.5rem 0;
  }

  :global(.rewind-cm-line-added) {
    background: rgba(26, 127, 55, 0.1) !important;
  }

  :global(.rewind-cm-line-removed) {
    background: rgba(207, 34, 46, 0.1) !important;
  }

  /* Preview view */
  .rewind-preview {
    flex: 1;
    overflow-y: auto;
    padding: 0 var(--page-padding, 48px);
  }

  .rewind-preview-inner {
    max-width: var(--max-content-width, 800px);
    width: 100%;
    margin: 0 auto;
  }

  .rewind-preview-title {
    font-size: 2.25rem;
    font-weight: 700;
    color: var(--text-primary, #333);
    line-height: 1.2;
    letter-spacing: -0.02em;
    padding: 1rem 0 0.5rem 0;
  }

  /* Dark mode */
  :global(.dark) .rewind-viewer-header {
    background: var(--bg-surface, #1e1e1e);
    border-color: var(--border-light, rgba(255, 255, 255, 0.08));
  }

  :global(.dark) .rewind-diff-line.added {
    background: rgba(63, 185, 80, 0.15);
    color: #3fb950;
  }

  :global(.dark) .rewind-diff-line.removed {
    background: rgba(248, 81, 73, 0.15);
    color: #f85149;
  }

  :global(.dark) .rewind-stat-added {
    color: #3fb950;
  }

  :global(.dark) .rewind-stat-removed {
    color: #f85149;
  }

  :global(.dark) .rewind-toggle-btn.active {
    background: var(--bg-elevated, #2d2d2d);
  }

  :global(.dark) .rewind-readonly-pill {
    color: #58a6ff;
    background: rgba(56, 139, 253, 0.12);
  }

  :global(.dark) .rewind-label-pill {
    background: rgba(56, 139, 253, 0.15);
    color: #58a6ff;
  }

  :global(.dark) .rewind-exit-btn {
    border-color: #f85149;
    color: #f85149;
  }

  :global(.dark) .rewind-exit-btn:hover {
    background: rgba(248, 81, 73, 0.15);
    color: #ff7b72;
  }

  :global(.dark .rewind-cm-line-added) {
    background: rgba(63, 185, 80, 0.15) !important;
  }

  :global(.dark .rewind-cm-line-removed) {
    background: rgba(248, 81, 73, 0.15) !important;
  }
</style>
