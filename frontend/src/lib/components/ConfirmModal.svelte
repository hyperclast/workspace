<script>
  import Modal from './Modal.svelte';

  let {
    open = $bindable(false),
    title = 'Confirm',
    message = '',
    description = '',
    confirmText = 'Confirm',
    cancelText = 'Cancel',
    danger = false,
    onconfirm = () => {},
    oncancel = () => {},
  } = $props();

  let loading = $state(false);

  async function handleConfirm() {
    loading = true;
    try {
      await onconfirm();
      open = false;
    } finally {
      loading = false;
    }
  }

  function handleCancel() {
    oncancel();
    open = false;
  }
</script>

<Modal bind:open {title} size="sm" onclose={handleCancel}>
  {#snippet children()}
    {#if message}
      <p class="modal-description">{message}</p>
    {/if}
    {#if description}
      <p class="modal-warning {danger ? 'danger' : ''}">{description}</p>
    {/if}
  {/snippet}

  {#snippet footer({ close })}
    <button
      type="button"
      class="modal-btn-secondary"
      onclick={handleCancel}
      disabled={loading}
    >
      {cancelText}
    </button>
    <button
      type="button"
      class="modal-btn-primary {danger ? 'danger' : ''}"
      onclick={handleConfirm}
      disabled={loading}
    >
      {loading ? 'Please wait...' : confirmText}
    </button>
  {/snippet}
</Modal>

<style>
  .modal-description {
    color: #374151;
    font-size: 0.95rem;
    line-height: 1.5;
    margin: 0 0 1rem 0;
  }

  .modal-warning {
    color: #6b7280;
    font-size: 0.875rem;
    line-height: 1.5;
    margin: 0;
    padding: 0.75rem;
    background: #f3f4f6;
    border-radius: 6px;
  }

  .modal-warning.danger {
    background: #fef2f2;
    color: #991b1b;
  }
</style>
