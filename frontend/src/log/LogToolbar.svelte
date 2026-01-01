<script>
  import { Search, X, EyeOff, Eye, FilterX } from "lucide-static";

  let {
    filterQuery = $bindable(''),
    totalEntries = 0,
    visibleEntries = 0,
    selectedIP = null,
    hasFilters = false,
    onhideselected = () => {},
    onshowonlyselected = () => {},
    onclearfilters = () => {},
  } = $props();

  function clearFilter() {
    filterQuery = '';
  }

  function handleKeydown(e) {
    if (e.key === 'Escape') {
      clearFilter();
    }
  }
</script>

<div class="log-toolbar-wrapper">
  <div class="log-toolbar">
    <div class="log-toolbar-container">
      <div class="filter-group">
        <span class="filter-icon">{@html Search}</span>
        <input
          type="text"
          class="filter-input"
          placeholder="Filter logs (grep)..."
          bind:value={filterQuery}
          onkeydown={handleKeydown}
        />
        {#if filterQuery}
          <button class="clear-btn" onclick={clearFilter} title="Clear filter">
            {@html X}
          </button>
        {/if}
      </div>

      <div class="action-buttons">
        <button
          class="action-btn"
          onclick={onhideselected}
          disabled={!selectedIP}
          title={selectedIP ? `Hide all entries from ${selectedIP}` : 'Select an IP first'}
        >
          <span class="btn-icon">{@html EyeOff}</span>
          <span class="btn-label">Hide IP</span>
        </button>

        <button
          class="action-btn"
          onclick={onshowonlyselected}
          disabled={!selectedIP}
          title={selectedIP ? `Show only entries from ${selectedIP}` : 'Select an IP first'}
        >
          <span class="btn-icon">{@html Eye}</span>
          <span class="btn-label">Only IP</span>
        </button>

        <button
          class="action-btn"
          onclick={onclearfilters}
          disabled={!hasFilters}
          title="Clear all filters"
        >
          <span class="btn-icon">{@html FilterX}</span>
          <span class="btn-label">Clear</span>
        </button>
      </div>

      <div class="entry-count">
        {#if visibleEntries !== totalEntries}
          {visibleEntries} of {totalEntries} entries
        {:else}
          {totalEntries} entries
        {/if}
      </div>
    </div>
  </div>
</div>

<style>
  .log-toolbar-wrapper {
    position: relative;
    flex: 0 0 auto;
    height: 44px;
    padding: 0.5rem 0;
    border-bottom: 1px solid var(--border-light, #e5e5e5);
    box-sizing: border-box;
  }

  .log-toolbar {
  }

  .log-toolbar-container {
    display: flex;
    align-items: center;
    gap: 1rem;
  }

  .filter-group {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex: 1;
    max-width: 300px;
    background: var(--bg-secondary, #f5f5f5);
    border-radius: 6px;
    padding: 0 0.75rem;
    height: 28px;
  }

  .filter-icon {
    color: var(--text-tertiary, #999);
    display: flex;
    align-items: center;
  }

  .filter-icon :global(svg) {
    width: 14px;
    height: 14px;
  }

  .filter-input {
    flex: 1;
    border: none;
    background: transparent;
    font-size: 0.8125rem;
    color: var(--text-primary, #333);
    outline: none;
  }

  .filter-input::placeholder {
    color: var(--text-tertiary, #999);
  }

  .clear-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 2px;
    border: none;
    background: transparent;
    color: var(--text-tertiary, #999);
    cursor: pointer;
    border-radius: 4px;
  }

  .clear-btn:hover {
    background: rgba(0, 0, 0, 0.1);
    color: var(--text-secondary, #666);
  }

  .clear-btn :global(svg) {
    width: 14px;
    height: 14px;
  }

  .action-buttons {
    display: flex;
    gap: 0.5rem;
  }

  .action-btn {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.25rem 0.5rem;
    border: 1px solid var(--border-light, #e0e0e0);
    border-radius: 4px;
    background: var(--bg-primary, #fff);
    color: var(--text-secondary, #666);
    font-size: 0.75rem;
    cursor: pointer;
    transition: all 0.15s;
  }

  .action-btn:hover:not(:disabled) {
    background: var(--bg-secondary, #f5f5f5);
    border-color: var(--border-medium, #ccc);
  }

  .action-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-icon {
    display: flex;
    align-items: center;
  }

  .btn-icon :global(svg) {
    width: 14px;
    height: 14px;
  }

  .btn-label {
    white-space: nowrap;
  }

  .entry-count {
    margin-left: auto;
    font-size: 0.75rem;
    color: var(--text-tertiary, #888);
    white-space: nowrap;
  }
</style>
