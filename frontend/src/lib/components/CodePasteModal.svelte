<script>
  import Modal from './Modal.svelte';
  import { languageOptions } from '../../codeSyntax/languageLoader.js';

  let {
    open = $bindable(false),
    suggestedLang = '',
    onconfirm = () => {},
    oncancel = () => {},
  } = $props();

  let selectedLang = $state('');
  let yesButtonRef = $state(null);

  // Reset selected language when modal opens
  $effect(() => {
    if (open) {
      selectedLang = suggestedLang || '';
    }
  });

  // Focus the Yes button when modal opens
  $effect(() => {
    if (open && yesButtonRef) {
      // Small delay to ensure DOM is ready
      setTimeout(() => yesButtonRef?.focus(), 50);
    }
  });

  function handleConfirm() {
    onconfirm(selectedLang);
    open = false;
  }

  function handleCancel() {
    oncancel();
    open = false;
  }

  function handleKeydown(e) {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleConfirm();
    }
  }
</script>

<Modal bind:open title="Format as Code Block?" size="sm" onclose={handleCancel}>
  {#snippet children()}
    <p class="modal-description">
      This looks like code. Would you like to wrap it in a code block?
    </p>

    <div class="language-selector">
      <label for="code-lang-select">Language:</label>
      <select
        id="code-lang-select"
        bind:value={selectedLang}
        class="lang-select"
      >
        {#each languageOptions as option}
          <option value={option.code}>{option.name}</option>
        {/each}
      </select>
    </div>
  {/snippet}

  {#snippet footer({ close })}
    <button
      type="button"
      class="modal-btn-secondary"
      onclick={handleCancel}
    >
      No, paste as markdown
    </button>
    <button
      type="button"
      class="modal-btn-primary"
      onclick={handleConfirm}
      onkeydown={handleKeydown}
      bind:this={yesButtonRef}
    >
      Yes
    </button>
  {/snippet}
</Modal>

<style>
  .modal-description {
    color: var(--text-secondary, #374151);
    font-size: 0.95rem;
    line-height: 1.5;
    margin: 0 0 1rem 0;
  }

  :global(.dark) .modal-description {
    color: var(--text-secondary, #9ca3af);
  }

  .language-selector {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .language-selector label {
    color: var(--text-secondary, #6b7280);
    font-size: 0.875rem;
    font-weight: 500;
  }

  :global(.dark) .language-selector label {
    color: var(--text-secondary, #9ca3af);
  }

  .lang-select {
    flex: 1;
    padding: 0.5rem 0.75rem;
    border: 1px solid var(--border-color, #d1d5db);
    border-radius: 6px;
    background: var(--bg-primary, #fff);
    color: var(--text-primary, #111827);
    font-size: 0.875rem;
    cursor: pointer;
    min-width: 150px;
  }

  :global(.dark) .lang-select {
    border-color: var(--border-color, #374151);
    background: var(--bg-primary, #1f2937);
    color: var(--text-primary, #f3f4f6);
  }

  .lang-select:focus {
    outline: none;
    border-color: var(--accent-color, #3b82f6);
    box-shadow: 0 0 0 2px var(--accent-color-alpha, rgba(59, 130, 246, 0.2));
  }
</style>
