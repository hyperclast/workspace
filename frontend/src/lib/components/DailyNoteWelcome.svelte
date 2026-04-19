<script>
  import Modal from './Modal.svelte';

  let {
    open = $bindable(false),
    projectName = 'Daily Notes',
    projectExists = false,
    unorganizedCount = 0,
    onproceed = () => {},
    oncustomize = () => {},
  } = $props();

  function handleProceed() {
    open = false;
    onproceed();
  }

  function handleCustomize() {
    open = false;
    oncustomize();
  }
</script>

<Modal bind:open title="Daily Note" size="sm">
  <p class="intro">
    {#if projectExists}
      We'll use your existing <strong>{projectName}</strong> project.
    {:else}
      We'll create a <strong>{projectName}</strong> project for your daily notes.
    {/if}
  </p>

  {#if unorganizedCount > 0}
    <p class="organize-note">
      We'll also organize <strong>{unorganizedCount}</strong> existing {unorganizedCount === 1 ? 'note' : 'notes'} into year/month folders.
    </p>
  {/if}

  {#snippet footer()}
    <button class="modal-btn-secondary link-btn" onclick={handleCustomize}>
      Customize...
    </button>
    <button class="modal-btn-primary" onclick={handleProceed}>
      Got it
    </button>
  {/snippet}
</Modal>

<style>
  .intro {
    margin: 0 0 0.75rem 0;
    font-size: 0.95rem;
    color: var(--text-primary);
    line-height: 1.5;
  }

  .organize-note {
    margin: 0;
    padding: 0.625rem 0.75rem;
    background: var(--bg-subtle, #f6f8fa);
    border-radius: 6px;
    font-size: 0.875rem;
    color: var(--text-secondary);
  }

  .link-btn {
    background: transparent;
    border: none;
    color: var(--text-secondary);
    padding: 0.5rem 0.75rem;
    cursor: pointer;
    font-size: 0.875rem;
  }

  .link-btn:hover {
    color: var(--text-primary);
    text-decoration: underline;
  }
</style>
