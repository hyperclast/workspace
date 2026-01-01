<script>
  import { Search, X } from "lucide-static";

  let {
    filterQuery = $bindable(''),
    totalRows = 0,
    filteredRows = 0,
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

<div class="csv-toolbar-wrapper">
  <div class="csv-toolbar">
    <div class="csv-toolbar-container">
      <div class="filter-group">
        <span class="filter-icon">{@html Search}</span>
        <input
          type="text"
          class="filter-input"
          placeholder="Filter rows..."
          bind:value={filterQuery}
          onkeydown={handleKeydown}
        />
        {#if filterQuery}
          <button class="clear-btn" onclick={clearFilter} title="Clear filter">
            {@html X}
          </button>
        {/if}
      </div>

      <div class="row-count">
        {#if filterQuery}
          Showing {filteredRows} of {totalRows} rows
        {:else}
          {totalRows} rows
        {/if}
      </div>
    </div>
  </div>
</div>

<style>
  .csv-toolbar-wrapper {
    position: relative;
    flex: 0 0 auto;
    height: 44px;
    padding: 0.5rem 0;
    border-bottom: 1px solid var(--border-light, #e5e5e5);
    box-sizing: border-box;
  }

  .csv-toolbar {
  }

  .csv-toolbar-container {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
  }

  .filter-group {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex: 1;
    max-width: 400px;
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

  .row-count {
    font-size: 0.75rem;
    color: var(--text-tertiary, #888);
    white-space: nowrap;
  }
</style>
