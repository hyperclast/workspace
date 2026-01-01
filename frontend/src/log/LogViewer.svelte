<script>
  import { parseLog, filterByGrep, filterByIP, getStatusClass } from './parse.js';
  import LogToolbar from './LogToolbar.svelte';

  let { content = '' } = $props();

  let filterQuery = $state('');
  let selectedIP = $state(null);
  let hiddenIPs = $state(new Set());
  let onlyShowIPs = $state(new Set());

  const parsed = $derived(parseLog(content));

  const grepFiltered = $derived(filterByGrep(parsed.entries, filterQuery));
  const ipFiltered = $derived(filterByIP(grepFiltered, hiddenIPs, onlyShowIPs));

  const hasFilters = $derived(
    filterQuery !== '' || hiddenIPs.size > 0 || onlyShowIPs.size > 0
  );

  function handleIPClick(ip) {
    if (!ip) return;
    selectedIP = selectedIP === ip ? null : ip;
  }

  function handleHideSelected() {
    if (!selectedIP) return;
    hiddenIPs = new Set([...hiddenIPs, selectedIP]);
    selectedIP = null;
  }

  function handleShowOnlySelected() {
    if (!selectedIP) return;
    onlyShowIPs = new Set([selectedIP]);
    hiddenIPs = new Set();
    selectedIP = null;
  }

  function handleClearFilters() {
    filterQuery = '';
    hiddenIPs = new Set();
    onlyShowIPs = new Set();
    selectedIP = null;
  }

  function highlightMatch(text, query) {
    if (!query || query.trim() === '') return text;
    const lowerText = text.toLowerCase();
    const lowerQuery = query.toLowerCase();
    const index = lowerText.indexOf(lowerQuery);
    if (index === -1) return text;

    const before = text.slice(0, index);
    const match = text.slice(index, index + query.length);
    const after = text.slice(index + query.length);
    return `${before}<mark>${match}</mark>${after}`;
  }
</script>

<LogToolbar
  bind:filterQuery
  totalEntries={parsed.entries.length}
  visibleEntries={ipFiltered.length}
  {selectedIP}
  {hasFilters}
  onhideselected={handleHideSelected}
  onshowonlyselected={handleShowOnlySelected}
  onclearfilters={handleClearFilters}
/>

<div class="log-viewer">
  {#if parsed.entries.length === 0}
    <div class="empty-state">
      <p>No log entries to display</p>
      <p class="empty-hint">Paste or upload HTTP access log content.</p>
    </div>
  {:else if ipFiltered.length === 0}
    <div class="empty-state">
      <p>No entries match your filters</p>
      <button class="clear-filters-btn" onclick={handleClearFilters}>Clear Filters</button>
    </div>
  {:else}
    <div class="log-entries">
      {#each ipFiltered as entry (entry.lineNumber)}
        <div
          class="log-entry"
          class:highlighted={selectedIP && entry.ip === selectedIP}
          class:unparsed={!entry.parsed}
        >
          <span class="line-number">{entry.lineNumber}</span>
          {#if entry.parsed}
            <button
              class="ip-cell"
              class:selected={selectedIP === entry.ip}
              onclick={() => handleIPClick(entry.ip)}
              title="Click to select this IP"
            >
              {entry.ip}
            </button>
            <span class="timestamp">[{entry.timestamp}]</span>
            <span class="method">{entry.method}</span>
            <span class="path" title={entry.path}>
              {#if filterQuery}
                {@html highlightMatch(entry.path, filterQuery)}
              {:else}
                {entry.path}
              {/if}
            </span>
            <span class="status {getStatusClass(entry.status)}">{entry.status}</span>
            <span class="bytes">{entry.bytes}</span>
          {:else}
            <span class="raw-line">
              {#if filterQuery}
                {@html highlightMatch(entry.raw, filterQuery)}
              {:else}
                {entry.raw}
              {/if}
            </span>
          {/if}
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .log-viewer {
    flex: 1;
    overflow: auto;
    padding-top: 0.5rem;
  }

  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 200px;
    color: var(--text-tertiary, #888);
  }

  .empty-state p {
    margin: 0.25rem 0;
  }

  .empty-hint {
    font-size: 0.8125rem;
  }

  .clear-filters-btn {
    margin-top: 1rem;
    padding: 0.5rem 1rem;
    border: 1px solid var(--border-medium, #ccc);
    border-radius: 4px;
    background: var(--bg-primary, #fff);
    color: var(--text-secondary, #666);
    cursor: pointer;
  }

  .clear-filters-btn:hover {
    background: var(--bg-secondary, #f5f5f5);
  }

  .log-entries {
    font-family: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, monospace;
    font-size: 0.8125rem;
    line-height: 1.6;
  }

  .log-entry {
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
    padding: 0.125rem 0;
    border-bottom: 1px solid transparent;
    flex-wrap: nowrap;
    white-space: nowrap;
  }

  .log-entry:hover {
    background: var(--bg-secondary, #fafafa);
  }

  .log-entry.highlighted {
    background: rgba(35, 131, 226, 0.1);
  }

  .log-entry.unparsed {
    opacity: 0.7;
  }

  .line-number {
    flex: 0 0 40px;
    text-align: right;
    color: var(--text-tertiary, #999);
    font-size: 0.75rem;
    user-select: none;
  }

  .ip-cell {
    flex: 0 0 120px;
    padding: 0;
    border: none;
    background: transparent;
    color: #2383e2;
    cursor: pointer;
    text-align: left;
    font-family: inherit;
    font-size: inherit;
    border-radius: 2px;
  }

  .ip-cell:hover {
    text-decoration: underline;
    background: rgba(35, 131, 226, 0.1);
  }

  .ip-cell.selected {
    background: rgba(35, 131, 226, 0.2);
    font-weight: 600;
  }

  .timestamp {
    flex: 0 0 auto;
    color: var(--text-tertiary, #888);
    font-size: 0.75rem;
  }

  .method {
    flex: 0 0 50px;
    font-weight: 600;
    color: var(--text-primary, #333);
  }

  .path {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--text-primary, #333);
  }

  .status {
    flex: 0 0 35px;
    text-align: center;
    font-weight: 600;
    border-radius: 3px;
    padding: 0 4px;
  }

  .status.status-success {
    color: #15803d;
    background: rgba(34, 197, 94, 0.1);
  }

  .status.status-redirect {
    color: #1d4ed8;
    background: rgba(59, 130, 246, 0.1);
  }

  .status.status-client-error {
    color: #c2410c;
    background: rgba(249, 115, 22, 0.1);
  }

  .status.status-server-error {
    color: #dc2626;
    background: rgba(239, 68, 68, 0.1);
  }

  .bytes {
    flex: 0 0 60px;
    text-align: right;
    color: var(--text-tertiary, #888);
    font-size: 0.75rem;
  }

  .raw-line {
    flex: 1;
    color: var(--text-secondary, #666);
    word-break: break-all;
  }

  .log-entry :global(mark) {
    background: #fff3a3;
    color: inherit;
    padding: 0 2px;
    border-radius: 2px;
  }
</style>
