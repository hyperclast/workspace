<script>
  import Modal from './Modal.svelte';
  import { API_BASE_URL } from '../../config.js';
  import { csrfFetch } from '../../csrf.js';
  import { showToast } from '../toast.js';
  import { looksLikeCsv } from '../../csv/detect.js';

  const PAGE_TYPES = [
    {
      id: 'md',
      label: 'Markdown',
      description: 'Rich formatting with headers, lists, links etc',
    },
    {
      id: 'txt',
      label: 'Plain Text',
      description: 'Simple text with monospace font',
    },
    {
      id: 'csv',
      label: 'Spreadsheet',
      description: 'View csv as tabular data',
    },
    {
      id: 'log',
      label: 'HTTP Log',
      description: 'View HTTP access logs',
    },
  ];

  let {
    open = $bindable(false),
    pageId = '',
    pageTitle = '',
    currentType = 'md',
    pageContent = '',
    onchanged = () => {},
  } = $props();

  let selectedType = $state('md');
  let loading = $state(false);

  const csvAvailable = $derived(currentType === 'csv' || looksLikeCsv(pageContent));

  $effect(() => {
    if (open) {
      selectedType = currentType || 'md';
      loading = false;
    }
  });

  async function handleConfirm() {
    if (selectedType === currentType) {
      open = false;
      return;
    }

    loading = true;

    try {
      const response = await csrfFetch(`${API_BASE_URL}/api/pages/${pageId}/`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: pageTitle,
          details: { filetype: selectedType },
        }),
      });

      if (response.ok) {
        showToast(`Page type changed to ${PAGE_TYPES.find(t => t.id === selectedType)?.label}`);
        open = false;
        onchanged(selectedType);
        window.location.reload();
      } else {
        const data = await response.json().catch(() => ({}));
        showToast(data.message || 'Failed to change page type', 'error');
      }
    } catch (error) {
      console.error('Error changing page type:', error);
      showToast('Network error. Please try again.', 'error');
    } finally {
      loading = false;
    }
  }

  function handleCancel() {
    open = false;
  }

  function handleTypeSelect(typeId) {
    if (!loading && isTypeAvailable(typeId)) {
      selectedType = typeId;
    }
  }

  function isTypeAvailable(typeId) {
    if (typeId === 'csv') return csvAvailable;
    return true;
  }

  function getUnavailableReason(typeId) {
    if (typeId === 'csv' && !csvAvailable) {
      return 'Content doesn\'t appear to be in CSV format.';
    }
    return null;
  }

  function handleKeydown(e, typeId) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleTypeSelect(typeId);
    }
  }
</script>

<Modal bind:open title="Change Page Type" size="sm">
  {#snippet children()}
    <p class="modal-intro">
      Choose a format for this page. Changing the type will reload the editor.
    </p>

    <div class="type-options">
      {#each PAGE_TYPES as type (type.id)}
        {@const unavailableReason = getUnavailableReason(type.id)}
        {@const isAvailable = isTypeAvailable(type.id)}
        <button
          type="button"
          class="type-card"
          class:selected={selectedType === type.id}
          class:current={currentType === type.id}
          class:unavailable={!isAvailable}
          onclick={() => handleTypeSelect(type.id)}
          onkeydown={(e) => handleKeydown(e, type.id)}
          disabled={loading || !isAvailable}
        >
          <div class="type-header">
            <span class="type-label">{type.label}</span>
            <span class="type-ext">.{type.id}</span>
            {#if currentType === type.id}
              <span class="current-badge">Current</span>
            {/if}
          </div>
          <p class="type-description">{type.description}</p>
          {#if unavailableReason}
            <p class="type-unavailable-reason">{unavailableReason}</p>
          {/if}
        </button>
      {/each}
    </div>
  {/snippet}

  {#snippet footer()}
    <button class="modal-btn-secondary" onclick={handleCancel} disabled={loading}>
      Cancel
    </button>
    <button
      class="modal-btn-primary"
      onclick={handleConfirm}
      disabled={loading || selectedType === currentType}
    >
      {loading ? 'Changing...' : 'Change Type'}
    </button>
  {/snippet}
</Modal>

<style>
  .modal-intro {
    margin: 0 0 1rem 0;
    font-size: 0.875rem;
    color: var(--text-secondary, #666);
    line-height: 1.5;
  }

  .type-options {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .type-card {
    display: block;
    width: 100%;
    padding: 1rem;
    border: 2px solid var(--border-light, #e5e5e5);
    border-radius: 8px;
    background: var(--bg-primary, #fff);
    cursor: pointer;
    text-align: left;
    transition: border-color 0.15s, background-color 0.15s, box-shadow 0.15s;
  }

  .type-card:hover:not(:disabled) {
    border-color: var(--border-medium, #ccc);
    background: var(--bg-secondary, #fafafa);
  }

  .type-card.selected {
    border-color: #2383e2;
    background: rgba(35, 131, 226, 0.04);
    box-shadow: 0 0 0 3px rgba(35, 131, 226, 0.1);
  }

  .type-card:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .type-card.unavailable {
    opacity: 0.7;
    background: var(--bg-secondary, #f9f9f9);
  }

  .type-card.unavailable .type-label,
  .type-card.unavailable .type-description {
    color: var(--text-tertiary, #888);
  }

  .type-unavailable-reason {
    margin: 0.5rem 0 0 0;
    padding: 0.375rem 0.5rem;
    font-size: 0.75rem;
    color: var(--text-warning, #b45309);
    background: rgba(251, 191, 36, 0.1);
    border-radius: 4px;
    line-height: 1.4;
  }

  .type-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
  }

  .type-label {
    font-weight: 600;
    font-size: 0.95rem;
    color: var(--text-primary, #333);
  }

  .type-ext {
    font-size: 0.75rem;
    color: var(--text-tertiary, #999);
    font-family: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, monospace;
  }

  .current-badge {
    margin-left: auto;
    padding: 0.125rem 0.5rem;
    font-size: 0.7rem;
    font-weight: 500;
    color: var(--text-secondary, #666);
    background: var(--bg-tertiary, #f0f0f0);
    border-radius: 4px;
    text-transform: uppercase;
    letter-spacing: 0.02em;
  }

  .type-description {
    margin: 0;
    font-size: 0.8125rem;
    color: var(--text-secondary, #666);
    line-height: 1.4;
  }
</style>
