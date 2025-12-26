<script>
  import { getToasts, removeToast } from '../stores/toast.svelte.js';

  const toasts = $derived(getToasts());
</script>

<div class="toast-container">
  {#each toasts as toast (toast.id)}
    <div class="toast toast-{toast.type}">
      <span class="toast-message">{toast.message}</span>
      <button
        type="button"
        class="toast-close"
        onclick={() => removeToast(toast.id)}
        aria-label="Dismiss"
      >
        ×
      </button>
    </div>
  {/each}
</div>

<style>
  .toast-container {
    position: fixed;
    bottom: 24px;
    right: 24px;
    z-index: 10000;
    display: flex;
    flex-direction: column;
    gap: 8px;
    pointer-events: none;
  }

  .toast {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    border-radius: 8px;
    color: white;
    font-size: 0.9rem;
    font-family: inherit;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    pointer-events: auto;
    animation: slideIn 0.3s ease-out;
    max-width: 360px;
  }

  .toast-message {
    flex: 1;
    text-align: left;
  }

  .toast-close {
    background: none;
    border: none;
    color: white;
    font-size: 1.25rem;
    line-height: 1;
    cursor: pointer;
    opacity: 0.7;
    padding: 0;
    width: 20px;
    height: 20px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 4px;
    transition: opacity 0.15s, background 0.15s;
  }

  .toast-close:hover {
    opacity: 1;
    background: rgba(255, 255, 255, 0.2);
  }

  .toast-success {
    background: linear-gradient(135deg, #28a745 0%, #218838 100%);
  }

  .toast-error {
    background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);
  }

  .toast-info {
    background: linear-gradient(135deg, #17a2b8 0%, #138496 100%);
  }

  @keyframes slideIn {
    from {
      opacity: 0;
      transform: translateX(100%);
    }
    to {
      opacity: 1;
      transform: translateX(0);
    }
  }
</style>
