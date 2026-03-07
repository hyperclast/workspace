<script>
  import { onMount, onDestroy } from "svelte";
  import { subscribe, getState, selectEntry, loadMore } from "./index.js";
  import { formatRelativeTime, groupByDay } from "./timeFormat.js";

  let state = $state(getState());
  let unsubscribe = null;
  let loadMoreBtn = null;

  let groups = $derived(groupByDay(state.entries));
  let hasMore = $derived(state.entries.length < state.totalCount);

  onMount(() => {
    unsubscribe = subscribe((newState) => {
      state = newState;
    });

    // Attach load more click handler manually (mount() caveat)
    loadMoreBtn = document.getElementById("rewind-load-more-btn");
    if (loadMoreBtn) {
      loadMoreBtn.addEventListener("click", handleLoadMore);
    }
  });

  onDestroy(() => {
    if (unsubscribe) unsubscribe();
    if (loadMoreBtn) {
      loadMoreBtn.removeEventListener("click", handleLoadMore);
    }
  });

  function handleLoadMore() {
    loadMore();
  }

  function handleEntryClick(entry) {
    selectEntry(entry);
  }
</script>

<div class="rewind-timeline">
  {#if state.loading && state.entries.length === 0}
    <div class="rewind-skeleton">
      <div class="rewind-skeleton-bar"></div>
      <div class="rewind-skeleton-bar short"></div>
      <div class="rewind-skeleton-bar"></div>
    </div>
  {:else if !state.currentPageId}
    <div class="rewind-empty">Open a page to view its history.</div>
  {:else if state.entries.length === 0}
    <div class="rewind-empty">No rewind history yet.</div>
  {:else}
    {#each groups as group (group.label)}
      <div class="rewind-group">
        <div class="rewind-group-header">{group.label}</div>
        {#each group.entries as entry (entry.external_id)}
          <button
            class="rewind-entry"
            class:selected={state.selectedEntry?.external_id === entry.external_id}
            onclick={() => handleEntryClick(entry)}
          >
            <div class="rewind-entry-main">
              <span class="rewind-entry-number">v{entry.rewind_number}</span>
              {#if entry.lines_added || entry.lines_deleted}
                <span class="rewind-diff-stat">
                  <span class="diff-add">+{entry.lines_added}</span>
                  <span class="diff-del">-{entry.lines_deleted}</span>
                </span>
              {/if}
              <span class="rewind-entry-time">{formatRelativeTime(entry.created)}</span>
            </div>
            <div class="rewind-entry-meta">
              {#if entry.label}
                <span class="rewind-label-pill">{entry.label}</span>
              {/if}
              {#if entry.is_compacted}
                <span class="rewind-compacted-badge" title="Compacted from {entry.compacted_from_count} snapshots">compacted</span>
              {/if}
            </div>
          </button>
        {/each}
      </div>
    {/each}

    {#if hasMore}
      <button id="rewind-load-more-btn" class="rewind-load-more" onclick={handleLoadMore}>
        {state.loading ? "Loading..." : "Load more"}
      </button>
    {/if}
  {/if}
</div>

<style>
  .rewind-timeline {
    padding: 0.5rem;
    height: 100%;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 0;
  }

  .rewind-empty {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 2rem 1rem;
    color: var(--text-secondary, #666);
    font-size: 0.8125rem;
    text-align: center;
  }

  /* Skeleton loading */
  .rewind-skeleton {
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .rewind-skeleton-bar {
    height: 2.5rem;
    background: var(--bg-elevated, #f5f5f5);
    border-radius: 6px;
    animation: rewind-pulse 1.5s ease-in-out infinite;
  }

  .rewind-skeleton-bar.short {
    width: 70%;
  }

  @keyframes rewind-pulse {
    0%, 100% { opacity: 0.4; }
    50% { opacity: 0.8; }
  }

  /* Day groups */
  .rewind-group {
    margin-bottom: 0.25rem;
  }

  .rewind-group-header {
    font-size: 0.6875rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--text-secondary, #666);
    padding: 0.5rem 0.75rem 0.25rem;
  }

  /* Entry rows */
  .rewind-entry {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    width: 100%;
    padding: 0.5rem 0.75rem;
    border: none;
    background: none;
    cursor: pointer;
    text-align: left;
    border-radius: 6px;
    transition: background 0.15s;
    border-left: 2px solid transparent;
  }

  .rewind-entry:hover {
    background: var(--bg-hover, rgba(0, 0, 0, 0.03));
  }

  .rewind-entry.selected {
    background: rgba(9, 105, 218, 0.1);
    border-left-color: #0969da;
  }

  .rewind-entry.selected .rewind-entry-number {
    color: #0969da;
    font-weight: 600;
  }

  .rewind-entry-main {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
  }

  .rewind-entry-number {
    font-size: 0.8125rem;
    font-weight: 500;
    color: var(--text-primary, #333);
    white-space: nowrap;
    flex-shrink: 0;
  }

  .rewind-entry-time {
    font-size: 0.6875rem;
    color: var(--text-tertiary, #888);
    white-space: nowrap;
    flex-shrink: 0;
  }

  .rewind-entry-meta {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    min-height: 0;
  }

  .rewind-entry-meta:empty {
    display: none;
  }

  .rewind-label-pill {
    font-size: 0.625rem;
    font-weight: 500;
    padding: 0.0625rem 0.375rem;
    border-radius: 3px;
    background: rgba(9, 105, 218, 0.08);
    color: #0969da;
    white-space: nowrap;
    max-width: 120px;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .rewind-diff-stat {
    font-family: monospace;
    font-size: 0.625rem;
    display: flex;
    gap: 0.25rem;
  }

  .diff-add {
    color: #1a7f37;
  }

  .diff-del {
    color: #cf222e;
  }

  :global(.dark) .diff-add {
    color: #3fb950;
  }

  :global(.dark) .diff-del {
    color: #f85149;
  }

  .rewind-compacted-badge {
    font-size: 0.625rem;
    color: var(--text-tertiary, #888);
    font-style: italic;
  }

  /* Load more */
  .rewind-load-more {
    display: block;
    width: 100%;
    padding: 0.625rem;
    margin-top: 0.25rem;
    border: 1px dashed var(--border-light, rgba(0, 0, 0, 0.1));
    background: none;
    border-radius: 6px;
    color: var(--text-secondary, #666);
    font-size: 0.8125rem;
    cursor: pointer;
    transition: background 0.15s, color 0.15s;
  }

  .rewind-load-more:hover {
    background: var(--bg-hover, rgba(0, 0, 0, 0.03));
    color: var(--text-primary, #333);
  }

  /* Dark mode */
  :global(.dark) .rewind-entry.selected {
    background: rgba(56, 139, 253, 0.15);
    border-left-color: #58a6ff;
  }

  :global(.dark) .rewind-entry.selected .rewind-entry-number {
    color: #58a6ff;
  }

  :global(.dark) .rewind-label-pill {
    background: rgba(56, 139, 253, 0.15);
    color: #58a6ff;
  }

  :global(.dark) .rewind-skeleton-bar {
    background: var(--bg-elevated, #252525);
  }
</style>
