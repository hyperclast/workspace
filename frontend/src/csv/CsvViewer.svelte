<script>
  import { parseCSV, sortRows, filterRows } from './parse.js';
  import CsvToolbar from './CsvToolbar.svelte';

  let { content = '' } = $props();

  let filterQuery = $state('');
  let sortColumn = $state(-1);
  let sortDirection = $state('asc');

  const parsed = $derived(parseCSV(content));

  const filteredData = $derived(filterRows(parsed.rows, filterQuery));
  const sortedData = $derived(sortRows(filteredData, sortColumn, sortDirection));

  function handleHeaderClick(index) {
    if (sortColumn === index) {
      sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
      sortColumn = index;
      sortDirection = 'asc';
    }
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

<CsvToolbar
  bind:filterQuery
  totalRows={parsed.rows.length}
  filteredRows={sortedData.length}
/>

<div class="csv-viewer">
  {#if parsed.headers.length === 0}
    <div class="empty-state">
      <p>No data to display</p>
      <p class="empty-hint">Paste or type CSV content, then switch to Spreadsheet view.</p>
    </div>
  {:else}
    <div class="table-wrapper">
      <table class="csv-table">
        <thead>
          <tr>
            {#each parsed.headers as header, i}
              <th
                onclick={() => handleHeaderClick(i)}
                class:sorted={sortColumn === i}
              >
                <span class="header-content">
                  {header}
                  {#if sortColumn === i}
                    <span class="sort-indicator">
                      {sortDirection === 'asc' ? '↑' : '↓'}
                    </span>
                  {/if}
                </span>
              </th>
            {/each}
          </tr>
        </thead>
        <tbody>
          {#each sortedData as row, rowIndex (rowIndex)}
            <tr>
              {#each row as cell, cellIndex}
                <td>
                  {#if filterQuery}
                    {@html highlightMatch(cell, filterQuery)}
                  {:else}
                    {cell}
                  {/if}
                </td>
              {/each}
            </tr>
          {:else}
            <tr>
              <td colspan={parsed.headers.length} class="no-results">
                No rows match your filter
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

<style>
  .csv-viewer {
    flex: 1;
    overflow: auto;
    padding-top: 1rem;
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

  .table-wrapper {
    overflow-x: auto;
  }

  .csv-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.875rem;
    font-family: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, monospace;
  }

  .csv-table th,
  .csv-table td {
    padding: 0.5rem 0.75rem;
    text-align: left;
    border-bottom: 1px solid var(--border-light, #e5e5e5);
    white-space: nowrap;
  }

  .csv-table th {
    position: sticky;
    top: 0;
    background: var(--bg-primary, #fff);
    font-weight: 600;
    color: var(--text-secondary, #666);
    cursor: pointer;
    user-select: none;
    border-bottom: 2px solid var(--border-medium, #ddd);
  }

  .csv-table th:hover {
    background: var(--bg-secondary, #f9f9f9);
  }

  .csv-table th.sorted {
    color: var(--text-primary, #333);
    background: var(--bg-secondary, #f5f5f5);
  }

  .header-content {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
  }

  .sort-indicator {
    font-size: 0.75rem;
    opacity: 0.7;
  }

  .csv-table tbody tr:nth-child(even) {
    background: var(--bg-secondary, #fafafa);
  }

  .csv-table tbody tr:hover {
    background: rgba(35, 131, 226, 0.05);
  }

  .csv-table td {
    color: var(--text-primary, #333);
  }

  .csv-table td :global(mark) {
    background: #fff3a3;
    color: inherit;
    padding: 0 2px;
    border-radius: 2px;
  }

  .no-results {
    text-align: center;
    color: var(--text-tertiary, #888);
    font-style: italic;
  }
</style>
