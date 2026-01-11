<script>
  import Modal from './Modal.svelte';

  let {
    open = $bindable(false),
    title = 'Enter value',
    label = '',
    placeholder = '',
    value = $bindable(''),
    confirmText = 'Save',
    cancelText = 'Cancel',
    maxlength = 255,
    required = true,
    validate = null,
    onconfirm = () => {},
    oncancel = () => {},
  } = $props();

  let inputEl = $state(null);
  let loading = $state(false);
  let error = $state('');

  // Derived validation for instant feedback
  let validationResult = $derived(validate ? validate(value) : { valid: true });
  let showValidationError = $derived(value.trim().length > 0 && validate && !validationResult.valid);

  async function handleConfirm() {
    const trimmedValue = value.trim();

    if (required && !trimmedValue) {
      error = 'This field is required';
      return;
    }

    // Run custom validation if provided
    if (validate) {
      const result = validate(trimmedValue);
      if (!result.valid) {
        error = result.error;
        return;
      }
    }

    error = '';
    loading = true;

    try {
      const result = await onconfirm(trimmedValue);
      if (result?.error) {
        error = result.error;
      } else {
        open = false;
      }
    } catch (e) {
      error = e.message || 'An error occurred';
    } finally {
      loading = false;
    }
  }

  function handleCancel() {
    error = '';
    oncancel();
    open = false;
  }

  function handleKeydown(e) {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleConfirm();
    }
  }

  $effect(() => {
    if (open && inputEl) {
      inputEl.focus();
      inputEl.select();
    }
  });

  $effect(() => {
    if (!open) {
      error = '';
    }
  });
</script>

<Modal bind:open {title} size="sm" onclose={handleCancel}>
  {#snippet children()}
    <div class="modal-field">
      {#if label}
        <label for="prompt-input">{label}</label>
      {/if}
      <input
        bind:this={inputEl}
        bind:value
        type="text"
        id="prompt-input"
        class="modal-input"
        class:input-error={showValidationError}
        {placeholder}
        {maxlength}
        onkeydown={handleKeydown}
        disabled={loading}
      />
      {#if showValidationError}
        <div class="field-error">{validationResult.error}</div>
      {/if}
    </div>
    {#if error}
      <div class="modal-error">{error}</div>
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
      class="modal-btn-primary"
      onclick={handleConfirm}
      disabled={loading || (validate && !validationResult.valid)}
    >
      {loading ? 'Please wait...' : confirmText}
    </button>
  {/snippet}
</Modal>

<style>
  .modal-field {
    margin-bottom: 1rem;
  }

  .modal-field label {
    display: block;
    font-weight: 500;
    font-size: 0.9rem;
    color: #374151;
    margin-bottom: 0.5rem;
  }

  .modal-input {
    width: 100%;
    padding: 0.625rem 0.75rem;
    font-size: 0.95rem;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    background: white;
    color: #1a1a1a;
    transition: border-color 0.15s, box-shadow 0.15s;
  }

  .modal-input:focus {
    outline: none;
    border-color: #667eea;
    box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
  }

  .modal-input:disabled {
    background: #f3f4f6;
    cursor: not-allowed;
  }

  .modal-error {
    margin-top: 0.5rem;
    padding: 0.625rem 0.75rem;
    font-size: 0.875rem;
    color: #991b1b;
    background: #fef2f2;
    border-radius: 6px;
  }

  .input-error {
    border-color: #dc2626 !important;
  }

  .input-error:focus {
    box-shadow: 0 0 0 3px rgba(220, 38, 38, 0.1) !important;
  }

  .field-error {
    color: #dc2626;
    font-size: 0.8rem;
    margin-top: 0.25rem;
  }

  /* Dark mode */
  :global(:root.dark) .modal-field label,
  :global(:root[data-theme="dark"]) .modal-field label {
    color: #d4d4d4;
  }

  :global(:root.dark) .modal-input,
  :global(:root[data-theme="dark"]) .modal-input {
    background: #1f1f1f;
    border-color: #444;
    color: #e5e5e5;
  }

  :global(:root.dark) .modal-input:focus,
  :global(:root[data-theme="dark"]) .modal-input:focus {
    border-color: #667eea;
    box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.2);
  }

  :global(:root.dark) .modal-input:disabled,
  :global(:root[data-theme="dark"]) .modal-input:disabled {
    background: #2a2a2a;
  }

  :global(:root.dark) .modal-error,
  :global(:root[data-theme="dark"]) .modal-error {
    background: #3b1515;
    color: #fca5a5;
  }

  :global(:root.dark) .field-error,
  :global(:root[data-theme="dark"]) .field-error {
    color: #f87171;
  }
</style>
