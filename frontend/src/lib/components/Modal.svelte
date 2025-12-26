<script>
  let {
    open = $bindable(false),
    title = '',
    size = 'default',
    danger = false,
    onclose = () => {},
    children,
    footer,
  } = $props();

  let dialogEl = $state(null);

  function handleBackdropClick(e) {
    if (e.target === e.currentTarget) {
      close();
    }
  }

  function handleKeydown(e) {
    if (e.key === 'Escape') {
      close();
    }
  }

  function close() {
    open = false;
    onclose();
  }

  $effect(() => {
    if (open && dialogEl) {
      const firstInput = dialogEl.querySelector('input, textarea, select, button:not(.close-modal)');
      if (firstInput) {
        firstInput.focus();
      }
    }
  });
</script>

{#if open}
  <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
  <div
    class="modal"
    role="dialog"
    aria-modal="true"
    aria-labelledby="modal-title"
    tabindex="-1"
    onclick={handleBackdropClick}
    onkeydown={handleKeydown}
  >
    <div
      class="modal-content {size === 'sm' ? 'modal-content-sm' : ''}"
      bind:this={dialogEl}
    >
      <div class="modal-header">
        <h2 id="modal-title">{title}</h2>
        <button
          type="button"
          class="close-modal"
          aria-label="Close"
          onclick={close}
        >
          &times;
        </button>
      </div>

      <div class="modal-body">
        {#if children}
          {@render children()}
        {/if}
      </div>

      {#if footer}
        <div class="modal-footer">
          {@render footer({ close })}
        </div>
      {/if}
    </div>
  </div>
{/if}
