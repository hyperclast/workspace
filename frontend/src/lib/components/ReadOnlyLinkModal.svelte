<script>
  import Modal from './Modal.svelte';
  import { showToast } from '../toast.js';
  import { removeAccessCode } from '../../api.js';

  let {
    open = $bindable(false),
    pageExternalId = '',
    pageTitle = '',
    accessCode = '',
    onremove = () => {},
  } = $props();

  let confirmingRemove = $state(false);
  let removing = $state(false);
  let error = $state('');

  function getShareUrl() {
    return `${window.location.origin}/share/pages/${accessCode}/`;
  }

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(getShareUrl());
      showToast('Copied to clipboard!');
    } catch (err) {
      console.error('Failed to copy:', err);
      showToast('Failed to copy', 'error');
    }
  }

  function startRemove() {
    confirmingRemove = true;
  }

  function cancelRemove() {
    confirmingRemove = false;
  }

  async function confirmRemove() {
    removing = true;
    error = '';

    try {
      await removeAccessCode(pageExternalId);
      confirmingRemove = false;
      open = false;
      onremove();
      showToast('View-only link deactivated');
    } catch (e) {
      console.error('Error removing access:', e);
      error = 'Failed to remove access. Please try again.';
    } finally {
      removing = false;
    }
  }

  function handleClose() {
    confirmingRemove = false;
    error = '';
  }

  function scrollToStart(node) {
    // Use requestAnimationFrame to ensure the value is rendered first
    requestAnimationFrame(() => {
      node.scrollLeft = 0;
    });
  }
</script>

<Modal bind:open title="View-Only Link" onclose={handleClose}>
  {#snippet children()}
    <p class="modal-description">
      Anyone with this link can view <strong>{pageTitle}</strong>.
    </p>

    <div class="link-section">
      <div class="link-input-group">
        <input
          type="text"
          readonly
          tabindex="-1"
          value={getShareUrl()}
          onclick={(e) => e.target.select()}
          use:scrollToStart
        />
        <button
          type="button"
          class="copy-btn"
          onclick={copyLink}
          title="Copy link"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
          </svg>
          Copy
        </button>
      </div>
    </div>

    <div class="remove-section">
      <div class="remove-info">
        <svg class="eye-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
          <circle cx="12" cy="12" r="3"></circle>
        </svg>
        <span>View-only link is active</span>
      </div>
      {#if confirmingRemove}
        <div class="inline-confirm">
          <button
            type="button"
            class="inline-btn cancel"
            onclick={cancelRemove}
            disabled={removing}
          >
            Cancel
          </button>
          <button
            type="button"
            class="inline-btn confirm"
            onclick={confirmRemove}
            disabled={removing}
          >
            {removing ? 'Deactivating...' : 'Deactivate'}
          </button>
        </div>
      {:else}
        <button
          type="button"
          class="remove-link-btn"
          onclick={startRemove}
        >
          Deactivate
        </button>
      {/if}
    </div>
  {/snippet}

  {#snippet footer({ close })}
    {#if error}
      <span class="footer-message error">{error}</span>
    {/if}
    <button type="button" class="modal-btn-secondary" onclick={close}>
      Done
    </button>
  {/snippet}
</Modal>

<style>
  .modal-description {
    color: #374151;
    font-size: 0.95rem;
    margin: 0 0 1.25rem 0;
  }

  .link-section {
    margin-bottom: 1.5rem;
  }

  .link-input-group {
    display: flex;
    align-items: stretch;
    gap: 0.5rem;
  }

  .link-input-group input {
    flex: 1;
    padding: 0 0.75rem;
    height: 38px;
    font-size: 0.875rem;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    background: #f9fafb;
    color: #374151;
    cursor: default;
    caret-color: transparent;
  }

  .link-input-group input:focus {
    outline: none;
  }

  .copy-btn {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0 0.875rem;
    height: 38px;
    font-size: 0.875rem;
    font-weight: 500;
    color: white;
    background: #2383e2;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.15s;
    white-space: nowrap;
  }

  .copy-btn:hover {
    background: #1a6fc9;
  }

  .copy-btn:active {
    background: #1560b5;
  }

  .remove-section {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.875rem 1rem;
    background: #fef3c7;
    border-radius: 8px;
    border: 1px solid #fcd34d;
  }

  .remove-info {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    color: #92400e;
    font-size: 0.875rem;
  }

  .eye-icon {
    flex-shrink: 0;
  }

  .remove-link-btn {
    padding: 0.375rem 0.75rem;
    font-size: 0.8rem;
    font-weight: 500;
    color: #92400e;
    background: white;
    border: 1px solid #fbbf24;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.15s;
  }

  .remove-link-btn:hover {
    background: #fffbeb;
    border-color: #f59e0b;
  }

  .inline-confirm {
    display: flex;
    gap: 0.375rem;
  }

  .inline-btn {
    padding: 0.375rem 0.625rem;
    font-size: 0.8rem;
    border-radius: 4px;
    border: none;
    cursor: pointer;
    font-weight: 500;
    transition: background 0.15s;
  }

  .inline-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .inline-btn.cancel {
    background: white;
    color: #4b5563;
    border: 1px solid #d1d5db;
  }

  .inline-btn.cancel:hover:not(:disabled) {
    background: #f9fafb;
  }

  .inline-btn.confirm {
    background: #dc2626;
    color: white;
  }

  .inline-btn.confirm:hover:not(:disabled) {
    background: #b91c1c;
  }

  .footer-message {
    font-size: 0.85rem;
    margin-right: auto;
    padding: 0.25rem 0;
  }

  .footer-message.error {
    color: #dc2626;
  }
</style>
