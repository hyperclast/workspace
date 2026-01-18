<script>
  import { onMount } from "svelte";
  import { csrfFetch } from "../../csrf.js";
  import { API_BASE_URL } from "../../config.js";

  // Props
  let { onnavigate = null } = $props();

  // State
  let mentions = $state([]);
  let loading = $state(true);
  let error = $state(null);

  async function fetchMentions() {
    loading = true;
    error = null;

    try {
      const response = await csrfFetch(`${API_BASE_URL}/api/mentions/`);
      if (!response.ok) {
        throw new Error("Failed to fetch mentions");
      }
      const data = await response.json();
      mentions = data.mentions || [];
    } catch (e) {
      console.error("Error fetching mentions:", e);
      error = e.message;
    } finally {
      loading = false;
    }
  }

  function handleClick(pageExternalId) {
    if (onnavigate) {
      onnavigate(pageExternalId);
    }
  }

  function formatDate(isoString) {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now - date;
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffDays === 0) {
      return "Today";
    } else if (diffDays === 1) {
      return "Yesterday";
    } else if (diffDays < 7) {
      return `${diffDays} days ago`;
    } else {
      return date.toLocaleDateString();
    }
  }

  onMount(() => {
    fetchMentions();
  });

  // Expose refresh method
  export function refresh() {
    fetchMentions();
  }
</script>

<div class="mentions-list">
  {#if loading}
    <div class="mentions-loading">Loading mentions...</div>
  {:else if error}
    <div class="mentions-error">{error}</div>
  {:else if mentions.length === 0}
    <div class="mentions-empty">
      <div class="mentions-empty-icon">@</div>
      <div class="mentions-empty-text">No mentions yet</div>
      <div class="mentions-empty-hint">When someone @mentions you in a page, it will appear here.</div>
    </div>
  {:else}
    {#each mentions as mention (mention.page_external_id)}
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <div
        class="mention-item"
        onclick={() => handleClick(mention.page_external_id)}
      >
        <div class="mention-item-title">{mention.page_title}</div>
        <div class="mention-item-meta">
          <span class="mention-item-project">{mention.project_name}</span>
          <span class="mention-item-date">{formatDate(mention.modified)}</span>
        </div>
      </div>
    {/each}
  {/if}
</div>

<style>
  .mentions-list {
    padding: 0.5rem;
  }

  .mentions-loading,
  .mentions-error {
    padding: 1rem;
    text-align: center;
    color: var(--text-secondary, rgba(55, 53, 47, 0.65));
    font-size: 0.875rem;
  }

  .mentions-error {
    color: #e53e3e;
  }

  .mentions-empty {
    padding: 2rem 1rem;
    text-align: center;
  }

  .mentions-empty-icon {
    font-size: 2rem;
    color: var(--text-tertiary, rgba(55, 53, 47, 0.35));
    margin-bottom: 0.5rem;
  }

  .mentions-empty-text {
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--text-secondary, rgba(55, 53, 47, 0.65));
    margin-bottom: 0.25rem;
  }

  .mentions-empty-hint {
    font-size: 0.75rem;
    color: var(--text-tertiary, rgba(55, 53, 47, 0.5));
  }

  .mention-item {
    padding: 0.75rem;
    border-radius: 4px;
    cursor: pointer;
    transition: background 0.15s;
    margin-bottom: 2px;
  }

  .mention-item:hover {
    background: var(--bg-hover, rgba(55, 53, 47, 0.08));
  }

  .mention-item-title {
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--text-primary, #37352f);
    margin-bottom: 0.25rem;
  }

  .mention-item-meta {
    display: flex;
    justify-content: space-between;
    font-size: 0.75rem;
    color: var(--text-tertiary, rgba(55, 53, 47, 0.5));
  }

  .mention-item-project {
    color: var(--text-secondary, rgba(55, 53, 47, 0.65));
  }

  :global(:root.dark) .mention-item-title,
  :global([data-theme="dark"]) .mention-item-title {
    color: var(--text-primary, #fff);
  }

  :global(:root.dark) .mention-item:hover,
  :global([data-theme="dark"]) .mention-item:hover {
    background: var(--bg-hover, rgba(255, 255, 255, 0.08));
  }
</style>
