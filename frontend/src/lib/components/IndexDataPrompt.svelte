<script>
  import { onMount } from "svelte";
  import { fetchIndexingStatus, triggerIndexing } from "../../api.js";

  let { compact = false } = $props();

  let status = $state(null);
  let isIndexing = $state(false);
  let error = $state(null);
  let pollInterval = null;

  onMount(() => {
    loadStatus();
    return () => {
      if (pollInterval) clearInterval(pollInterval);
    };
  });

  async function loadStatus() {
    try {
      status = await fetchIndexingStatus();
      error = null;

      if (isIndexing && status.pending_pages === 0) {
        isIndexing = false;
        if (pollInterval) {
          clearInterval(pollInterval);
          pollInterval = null;
        }
      }
    } catch (e) {
      console.error("Failed to load indexing status:", e);
      error = "Failed to load status";
    }
  }

  async function handleIndex() {
    if (isIndexing) return;

    isIndexing = true;
    error = null;

    try {
      await triggerIndexing();
      pollInterval = setInterval(loadStatus, 3000);
    } catch (e) {
      error = e.message || "Failed to start indexing";
      isIndexing = false;
    }
  }

  const showPrompt = $derived(
    status && status.has_valid_provider && status.pending_pages > 0
  );
</script>

{#if showPrompt}
  <div class="index-prompt" class:compact>
    <div class="index-content">
      {#if isIndexing}
        <div class="index-progress">
          <div class="spinner"></div>
          <span class="index-text">
            Indexing {status.pending_pages} page{status.pending_pages !== 1 ? "s" : ""}...
          </span>
        </div>
      {:else}
        <div class="index-info">
          <svg class="index-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
            <polyline points="14 2 14 8 20 8"></polyline>
            <line x1="16" y1="13" x2="8" y2="13"></line>
            <line x1="16" y1="17" x2="8" y2="17"></line>
            <polyline points="10 9 9 9 8 9"></polyline>
          </svg>
          <span class="index-text">
            {status.pending_pages} page{status.pending_pages !== 1 ? "s" : ""} not indexed for AI search
          </span>
        </div>
        <button class="index-btn" onclick={handleIndex}>
          Index Now
        </button>
      {/if}
    </div>
    {#if error}
      <div class="index-error">{error}</div>
    {/if}
  </div>
{/if}

<style>
  .index-prompt {
    background: linear-gradient(135deg, rgba(102, 126, 234, 0.08) 0%, rgba(118, 75, 162, 0.08) 100%);
    border: 1px solid rgba(102, 126, 234, 0.2);
    border-radius: 8px;
    padding: 0.875rem 1rem;
    margin-bottom: 1rem;
  }

  .index-prompt.compact {
    padding: 0.625rem 0.75rem;
    margin-bottom: 0.75rem;
  }

  .index-content {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
  }

  .compact .index-content {
    flex-direction: column;
    align-items: stretch;
    gap: 0.5rem;
  }

  .index-info {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .index-icon {
    color: #667eea;
    flex-shrink: 0;
  }

  .compact .index-icon {
    width: 16px;
    height: 16px;
  }

  .index-text {
    font-size: 0.875rem;
    color: var(--text-primary);
  }

  .compact .index-text {
    font-size: 0.8rem;
  }

  .index-btn {
    padding: 0.5rem 1rem;
    background: #667eea;
    color: white;
    border: none;
    border-radius: 6px;
    font-size: 0.85rem;
    font-weight: 500;
    cursor: pointer;
    transition: background 0.15s;
    white-space: nowrap;
  }

  .index-btn:hover {
    background: #5a6fd6;
  }

  .compact .index-btn {
    padding: 0.375rem 0.75rem;
    font-size: 0.8rem;
  }

  .index-progress {
    display: flex;
    align-items: center;
    gap: 0.625rem;
  }

  .spinner {
    width: 18px;
    height: 18px;
    border: 2px solid rgba(102, 126, 234, 0.3);
    border-top-color: #667eea;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  .compact .spinner {
    width: 14px;
    height: 14px;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  .index-error {
    margin-top: 0.5rem;
    font-size: 0.8rem;
    color: #dc3545;
  }
</style>
