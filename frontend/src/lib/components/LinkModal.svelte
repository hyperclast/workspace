<script>
  import Modal from './Modal.svelte';
  import { csrfFetch } from '../../csrf.js';

  let {
    open = $bindable(false),
    initialTitle = '',
    initialUrl = '',
    oninsert = () => {},
    oncancel = () => {},
  } = $props();

  let urlInputEl = $state(null);
  let titleInputEl = $state(null);
  let url = $state('');
  let title = $state('');
  let loading = $state(false);
  let fetchingTitle = $state(false);
  let userEditedTitle = $state(false);
  let suggestions = $state([]);
  let showSuggestions = $state(false);
  let selectedIndex = $state(-1);
  let suggestionsEl = $state(null);

  let debounceTimeout = null;
  let titleFetchController = null;

  $effect(() => {
    if (open) {
      url = initialUrl || '';
      title = initialTitle;
      userEditedTitle = !!initialTitle;
      fetchingTitle = false;
      suggestions = [];
      showSuggestions = false;
      selectedIndex = -1;
      if (titleFetchController) {
        titleFetchController.abort();
        titleFetchController = null;
      }
    }
  });

  $effect(() => {
    if (open) {
      setTimeout(() => {
        if (initialUrl) {
          titleInputEl?.focus();
          titleInputEl?.select();
        } else {
          urlInputEl?.focus();
        }
      }, 50);
    }
  });

  async function fetchSuggestions(query) {
    if (!query || query.length < 1) {
      suggestions = [];
      return;
    }
    try {
      const response = await csrfFetch(`/api/pages/autocomplete/?q=${encodeURIComponent(query)}`);
      if (response.ok) {
        const data = await response.json();
        suggestions = data.pages || [];
        showSuggestions = suggestions.length > 0;
        selectedIndex = -1;
      }
    } catch (e) {
      console.error('Error fetching suggestions:', e);
    }
  }

  function handleUrlInput(e) {
    const value = e.target.value;
    url = value;

    if (debounceTimeout) clearTimeout(debounceTimeout);

    if (!value.startsWith('http://') && !value.startsWith('https://')) {
      debounceTimeout = setTimeout(() => fetchSuggestions(value), 150);
    } else {
      suggestions = [];
      showSuggestions = false;
    }
  }

  function handleUrlPaste(e) {
    const pasted = e.clipboardData?.getData('text')?.trim();
    if (pasted && (pasted.startsWith('http://') || pasted.startsWith('https://') || /^[a-z0-9-]+\.[a-z]{2,}/i.test(pasted))) {
      setTimeout(() => {
        if (!userEditedTitle) {
          fetchTitleFromUrl();
        }
      }, 0);
    }
  }

  function selectSuggestion(page) {
    url = `/pages/${page.external_id}/`;
    if (!title || title === initialTitle) {
      title = page.title || 'Untitled';
    }
    suggestions = [];
    showSuggestions = false;
    selectedIndex = -1;
    titleInputEl?.focus();
    titleInputEl?.select();
  }

  function handleUrlKeydown(e) {
    if (showSuggestions && suggestions.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        selectedIndex = Math.min(selectedIndex + 1, suggestions.length - 1);
        scrollSelectedIntoView();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        selectedIndex = Math.max(selectedIndex - 1, -1);
        scrollSelectedIntoView();
      } else if (e.key === 'Enter' && selectedIndex >= 0) {
        e.preventDefault();
        selectSuggestion(suggestions[selectedIndex]);
        return;
      } else if (e.key === 'Escape') {
        showSuggestions = false;
        selectedIndex = -1;
        return;
      }
    }

    if (e.key === 'Enter' && !showSuggestions) {
      e.preventDefault();
      if (url && !title) {
        fetchTitleFromUrl();
      } else {
        titleInputEl?.focus();
      }
    }

    if (e.key === 'Tab' && !e.shiftKey && url) {
      if (!title) {
        fetchTitleFromUrl();
      }
    }
  }

  function scrollSelectedIntoView() {
    if (suggestionsEl && selectedIndex >= 0) {
      const items = suggestionsEl.querySelectorAll('.suggestion-item');
      items[selectedIndex]?.scrollIntoView({ block: 'nearest' });
    }
  }

  async function fetchTitleFromUrl() {
    if (userEditedTitle && title) {
      titleInputEl?.focus();
      titleInputEl?.select();
      return;
    }

    if (url.startsWith('/pages/')) {
      const match = url.match(/\/pages\/([^/]+)/);
      if (match) {
        const pageId = match[1];
        try {
          const response = await csrfFetch(`/api/pages/${pageId}/`);
          if (response.ok) {
            const page = await response.json();
            if (!userEditedTitle) {
              title = page.title || 'Untitled';
            }
            titleInputEl?.focus();
            titleInputEl?.select();
          }
        } catch (e) {
          console.error('Error fetching page:', e);
        }
      }
    } else if (url.startsWith('http://') || url.startsWith('https://') || url.includes('.')) {
      if (titleFetchController) {
        titleFetchController.abort();
      }
      titleFetchController = new AbortController();

      fetchingTitle = true;
      titleInputEl?.focus();

      try {
        const fetchUrl = url.startsWith('http') ? url : `https://${url}`;
        const response = await csrfFetch('/api/utils/url-title/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url: fetchUrl }),
          signal: titleFetchController.signal,
        });

        if (response.ok) {
          const data = await response.json();
          if (data.title && !userEditedTitle) {
            title = data.title;
            titleInputEl?.select();
          }
        }
      } catch (e) {
        if (e.name !== 'AbortError') {
          console.error('Error fetching URL title:', e);
        }
      } finally {
        fetchingTitle = false;
        titleFetchController = null;
      }
    }
  }

  function handleTitleInput() {
    userEditedTitle = true;
  }

  function handleTitleKeydown(e) {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleInsert();
    }
  }

  function handleInsert() {
    if (!url) return;
    const finalTitle = title || url;
    oninsert({ url, title: finalTitle });
    open = false;
  }

  function handleCancel() {
    oncancel();
    open = false;
  }

  function handleUrlBlur() {
    setTimeout(() => {
      showSuggestions = false;
    }, 150);
  }
</script>

<Modal bind:open title="Insert Link" size="sm" onclose={handleCancel}>
  {#snippet children()}
    <div class="link-field">
      <label for="link-url">Link</label>
      <div class="url-input-wrapper">
        <input
          bind:this={urlInputEl}
          type="text"
          id="link-url"
          class="link-input"
          placeholder="Paste URL or search pages..."
          value={url}
          oninput={handleUrlInput}
          onpaste={handleUrlPaste}
          onkeydown={handleUrlKeydown}
          onblur={handleUrlBlur}
          onfocus={() => { if (suggestions.length > 0) showSuggestions = true; }}
        />
        {#if showSuggestions && suggestions.length > 0}
          <div class="suggestions" bind:this={suggestionsEl}>
            {#each suggestions as page, i}
              <button
                type="button"
                class="suggestion-item"
                class:selected={i === selectedIndex}
                onmousedown={() => selectSuggestion(page)}
              >
                <span class="suggestion-title">{page.title || 'Untitled'}</span>
                <span class="suggestion-badge">page</span>
              </button>
            {/each}
          </div>
        {/if}
      </div>
    </div>

    <div class="link-field">
      <label for="link-title">Title</label>
      <div class="title-input-wrapper">
        <input
          bind:this={titleInputEl}
          bind:value={title}
          type="text"
          id="link-title"
          class="link-input"
          placeholder="Link text"
          onkeydown={handleTitleKeydown}
          oninput={handleTitleInput}
        />
        {#if fetchingTitle}
          <span class="title-spinner"></span>
        {/if}
      </div>
    </div>
  {/snippet}

  {#snippet footer({ close })}
    <button
      type="button"
      class="modal-btn-secondary"
      onclick={handleCancel}
    >
      Cancel
    </button>
    <button
      type="button"
      class="modal-btn-primary"
      onclick={handleInsert}
      disabled={!url}
    >
      Insert Link
    </button>
  {/snippet}
</Modal>

<style>
  .link-field {
    margin-bottom: 1rem;
  }

  .link-field:last-child {
    margin-bottom: 0;
  }

  .link-field label {
    display: block;
    font-weight: 500;
    font-size: 0.85rem;
    color: #374151;
    margin-bottom: 0.375rem;
  }

  .url-input-wrapper {
    position: relative;
  }

  .link-input {
    width: 100%;
    padding: 0.5rem 0.75rem;
    font-size: 0.9rem;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    background: white;
    transition: border-color 0.15s, box-shadow 0.15s;
  }

  .link-input:focus {
    outline: none;
    border-color: #667eea;
    box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
  }

  .suggestions {
    position: absolute;
    top: 100%;
    left: 0;
    right: 0;
    margin-top: 4px;
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    max-height: 200px;
    overflow-y: auto;
    z-index: 100;
  }

  .suggestion-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    padding: 0.5rem 0.75rem;
    border: none;
    background: none;
    text-align: left;
    cursor: pointer;
    font-size: 0.875rem;
    color: #374151;
    transition: background 0.1s;
  }

  .suggestion-item:hover,
  .suggestion-item.selected {
    background: #f3f4f6;
  }

  .suggestion-title {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .suggestion-badge {
    font-size: 0.7rem;
    color: #6b7280;
    background: #e5e7eb;
    padding: 0.125rem 0.375rem;
    border-radius: 4px;
    margin-left: 0.5rem;
    flex-shrink: 0;
  }

  .title-input-wrapper {
    position: relative;
  }

  .title-input-wrapper .link-input {
    padding-right: 2rem;
  }

  .title-spinner {
    position: absolute;
    right: 0.625rem;
    top: 50%;
    transform: translateY(-50%);
    width: 14px;
    height: 14px;
    border: 2px solid #e5e7eb;
    border-top-color: #667eea;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: translateY(-50%) rotate(360deg); }
  }
</style>
