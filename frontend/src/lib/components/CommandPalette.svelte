<script>
  import { closeCommandPalette } from '../stores/modal.svelte.js';
  import { csrfFetch } from '../../csrf.js';
  import { API_BASE_URL } from '../../config.js';
  import { getRecentPages } from '../recentPages.js';
  import { isDemoMode } from '../../demo/index.js';

  let {
    open = $bindable(false),
    projects = [],
    currentPageId = null,
    currentProjectId = null,
    onselect = () => {},
  } = $props();

  let query = $state('');
  let selectedIndex = $state(0);
  let inputEl = $state(null);
  let listEl = $state(null);

  // Detect Mac for keyboard shortcut display
  const isMac = typeof navigator !== 'undefined' && navigator.platform.toUpperCase().indexOf('MAC') >= 0;

  // @Mentions state
  let mentions = $state([]);
  let mentionsLoading = $state(false);
  let mentionsExpanded = $state(false);
  const MAX_MENTIONS_COLLAPSED = 2;

  // Get recent pages from localStorage
  let storedRecentPages = $state([]);
  const MAX_RECENT = 5;

  // Fetch mentions from API
  async function fetchMentions() {
    if (isDemoMode()) return;
    mentionsLoading = true;
    try {
      const res = await csrfFetch(`${API_BASE_URL}/api/mentions/`);
      if (res.ok) {
        const data = await res.json();
        mentions = data.mentions || [];
      }
    } catch (e) {
      console.error("Error fetching mentions:", e);
    }
    mentionsLoading = false;
  }

  // Track visited pages for recent section (legacy compatibility)
  export function trackPageVisit(pageId) {
    // This is now handled by addRecentPage in recentPages.js
  }

  // Action definitions
  const actions = [
    { id: 'create-page', label: 'Create new page', icon: '+', shortcut: null, type: 'action' },
    { id: 'create-project', label: 'Create new project', icon: '+', shortcut: null, type: 'action' },
    { id: 'ask', label: 'Ask', icon: 'chat', shortcut: null, type: 'action' },
    { id: 'settings', label: 'Settings', icon: 'cog', shortcut: null, type: 'action' },
    { id: 'developer-portal', label: 'Developer Portal', icon: 'code', shortcut: null, type: 'action' },
    { id: 'delete-page', label: 'Delete current page', icon: 'trash', shortcut: null, type: 'action', danger: true },
  ];

  // Flatten all pages from projects
  let allPages = $derived.by(() => {
    const pages = [];
    for (const project of projects) {
      if (project.pages) {
        for (const page of project.pages) {
          pages.push({
            ...page,
            projectName: project.name,
            projectId: project.external_id,
            type: 'page',
          });
        }
      }
    }
    return pages;
  });

  // Fuzzy search scoring function
  function fuzzyMatch(text, pattern) {
    if (!pattern) return { match: true, score: 0 };

    const textLower = text.toLowerCase();
    const patternLower = pattern.toLowerCase();

    let score = 0;
    let patternIdx = 0;
    let lastMatchIdx = -1;
    let consecutiveMatches = 0;

    for (let i = 0; i < textLower.length && patternIdx < patternLower.length; i++) {
      if (textLower[i] === patternLower[patternIdx]) {
        // Bonus for consecutive matches
        if (lastMatchIdx === i - 1) {
          consecutiveMatches++;
          score += consecutiveMatches * 2;
        } else {
          consecutiveMatches = 1;
        }

        // Bonus for word boundary matches
        if (i === 0 || textLower[i - 1] === ' ' || textLower[i - 1] === '-' || textLower[i - 1] === '_') {
          score += 10;
        }

        // Bonus for early matches
        score += Math.max(0, 10 - i);

        lastMatchIdx = i;
        patternIdx++;
      }
    }

    // All pattern characters must be found
    if (patternIdx !== patternLower.length) {
      return { match: false, score: 0 };
    }

    return { match: true, score };
  }

  // Get recent pages from localStorage, mapped to full page data
  let recentPages = $derived.by(() => {
    const stored = storedRecentPages;
    return stored
      .map(rp => {
        const page = allPages.find(p => p.external_id === rp.id);
        return page || { ...rp, external_id: rp.id, title: rp.title, projectName: rp.projectName, type: 'page' };
      })
      .filter(p => p.external_id !== currentPageId)
      .slice(0, MAX_RECENT);
  });

  // Mentions to display (collapsible)
  let displayedMentions = $derived.by(() => {
    if (!mentions.length) return [];
    const items = mentionsExpanded ? mentions : mentions.slice(0, MAX_MENTIONS_COLLAPSED);
    return items.map(m => ({
      external_id: m.page_external_id,
      title: m.page_title,
      projectName: m.project_name,
      type: 'mention',
    }));
  });

  // Filter and score items based on query
  let filteredItems = $derived.by(() => {
    const items = [];
    const q = query.trim();

    if (!q) {
      // No query: show mentions, recent pages, then all pages, then actions

      // Mentions section (collapsible)
      if (displayedMentions.length > 0) {
        const hasMore = mentions.length > MAX_MENTIONS_COLLAPSED;
        items.push({
          type: 'header',
          label: '@ Mentions',
          expandable: hasMore,
          expanded: mentionsExpanded,
          totalCount: mentions.length,
        });
        items.push(...displayedMentions.map(m => ({ ...m, section: 'mentions' })));
        if (hasMore && !mentionsExpanded) {
          items.push({ type: 'expand-toggle', section: 'mentions', label: `Show ${mentions.length - MAX_MENTIONS_COLLAPSED} more` });
        }
      }

      // Recent pages
      if (recentPages.length > 0) {
        items.push({ type: 'header', label: 'Recent' });
        items.push(...recentPages.map(p => ({ ...p, section: 'recent' })));
      }

      // Show all pages (excluding recent and mentions)
      const recentIds = new Set(recentPages.map(p => p.external_id));
      const mentionIds = new Set(displayedMentions.map(m => m.external_id));
      const otherPages = allPages.filter(p =>
        !recentIds.has(p.external_id) &&
        !mentionIds.has(p.external_id) &&
        p.external_id !== currentPageId
      );
      if (otherPages.length > 0) {
        items.push({ type: 'header', label: 'Pages' });
        items.push(...otherPages.slice(0, 10).map(p => ({ ...p, section: 'pages' })));
      }

      // Show all actions
      items.push({ type: 'header', label: 'Actions' });
      items.push(...actions);
    } else {
      // With query: fuzzy filter pages and actions
      const pageResults = allPages
        .map(page => {
          const result = fuzzyMatch(page.title || 'Untitled', q);
          return { ...page, ...result, section: 'pages' };
        })
        .filter(p => p.match)
        .sort((a, b) => b.score - a.score)
        .slice(0, 10);

      const actionResults = actions
        .map(action => {
          const result = fuzzyMatch(action.label, q);
          return { ...action, ...result };
        })
        .filter(a => a.match)
        .sort((a, b) => b.score - a.score);

      if (pageResults.length > 0) {
        items.push({ type: 'header', label: 'Pages' });
        items.push(...pageResults);
      }

      if (actionResults.length > 0) {
        items.push({ type: 'header', label: 'Actions' });
        items.push(...actionResults);
      }
    }

    return items;
  });

  // Get only selectable items (not headers, but include expand-toggle)
  let selectableItems = $derived(filteredItems.filter(item => item.type !== 'header'));

  // Reset state when modal opens/closes
  $effect(() => {
    if (open) {
      query = '';
      selectedIndex = 0;
      mentionsExpanded = false;
      // Load recent pages from localStorage
      storedRecentPages = getRecentPages();
      // Fetch mentions
      fetchMentions();
      setTimeout(() => inputEl?.focus(), 10);
    }
  });

  // Keep selected index in bounds
  $effect(() => {
    if (selectedIndex >= selectableItems.length) {
      selectedIndex = Math.max(0, selectableItems.length - 1);
    }
  });

  // Scroll selected item into view
  $effect(() => {
    if (listEl && selectableItems.length > 0) {
      const selectedEl = listEl.querySelector(`[data-index="${selectedIndex}"]`);
      selectedEl?.scrollIntoView({ block: 'nearest' });
    }
  });

  function close() {
    open = false;
    closeCommandPalette();
  }

  function handleBackdropClick(e) {
    if (e.target === e.currentTarget) {
      close();
    }
  }

  function handleKeydown(e) {
    if (e.key === 'Escape') {
      e.preventDefault();
      close();
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      selectedIndex = Math.min(selectedIndex + 1, selectableItems.length - 1);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      selectedIndex = Math.max(selectedIndex - 1, 0);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (selectableItems[selectedIndex]) {
        selectItem(selectableItems[selectedIndex]);
      }
    }
  }

  function selectItem(item) {
    if (!item || item.type === 'header') return;

    // Handle expand toggle
    if (item.type === 'expand-toggle') {
      if (item.section === 'mentions') {
        mentionsExpanded = !mentionsExpanded;
      }
      return;
    }

    close();

    if (item.type === 'page' || item.type === 'mention') {
      onselect({ type: 'navigate', pageId: item.external_id, scrollToMention: item.type === 'mention' });
    } else if (item.type === 'action') {
      onselect({ type: 'action', actionId: item.id });
    }
  }

  function handleItemClick(item, index) {
    // Update selected index to match clicked item
    const selectableIndex = selectableItems.indexOf(item);
    if (selectableIndex !== -1) {
      selectedIndex = selectableIndex;
    }
    selectItem(item);
  }

  function getIcon(item) {
    if (item.type === 'page') {
      return 'doc';
    }
    return item.icon || '';
  }

  function getShortcutDisplay(shortcut) {
    if (!shortcut) return '';
    // Replace Cmd with appropriate symbol based on platform
    const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
    return shortcut.replace('Cmd', isMac ? '⌘' : 'Ctrl');
  }

  // Get the selectable index for an item in filteredItems
  function getSelectableIndex(item) {
    return selectableItems.indexOf(item);
  }

  // Handle global keydown - only process when open
  function handleGlobalKeydown(e) {
    if (!open) return;
    handleKeydown(e);
  }
</script>

<svelte:window onkeydown={handleGlobalKeydown} />

{#if open}
  <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
  <div
    class="command-palette-overlay"
    role="dialog"
    aria-modal="true"
    aria-labelledby="command-palette-title"
    tabindex="-1"
    onclick={handleBackdropClick}
  >
    <div class="command-palette">
      <div class="command-palette-header">
        <div class="search-input-wrapper">
          <svg class="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="11" cy="11" r="8"></circle>
            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
          </svg>
          <input
            bind:this={inputEl}
            bind:value={query}
            type="text"
            class="search-input"
            placeholder="Search pages and actions..."
            id="command-palette-title"
            autocomplete="off"
            spellcheck="false"
          />
          <kbd class="escape-hint">esc</kbd>
        </div>
      </div>

      <div class="command-palette-list" bind:this={listEl}>
        {#if filteredItems.length === 0}
          <div class="no-results">No results found</div>
        {:else}
          {#each filteredItems as item, i}
            {#if item.type === 'header'}
              <div class="list-header">
                {item.label}
                {#if item.expandable && item.totalCount}
                  <span class="header-count">{item.totalCount}</span>
                {/if}
              </div>
            {:else if item.type === 'expand-toggle'}
              {@const selectableIdx = getSelectableIndex(item)}
              <button
                class="list-item expand-toggle"
                class:selected={selectableIdx === selectedIndex}
                data-index={selectableIdx}
                onclick={() => handleItemClick(item, i)}
                onmouseenter={() => { selectedIndex = selectableIdx; }}
              >
                <span class="item-icon">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="6 9 12 15 18 9"></polyline>
                  </svg>
                </span>
                <span class="item-content">
                  <span class="item-label expand-label">{item.label}</span>
                </span>
              </button>
            {:else}
              {@const selectableIdx = getSelectableIndex(item)}
              <button
                class="list-item"
                class:selected={selectableIdx === selectedIndex}
                class:danger={item.danger}
                data-index={selectableIdx}
                onclick={() => handleItemClick(item, i)}
                onmouseenter={() => { selectedIndex = selectableIdx; }}
              >
                <span class="item-icon">
                  {#if item.type === 'mention'}
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <circle cx="12" cy="12" r="4"></circle>
                      <path d="M16 8v5a3 3 0 0 0 6 0v-1a10 10 0 1 0-3.92 7.94"></path>
                    </svg>
                  {:else if item.type === 'page'}
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                      <polyline points="14 2 14 8 20 8"></polyline>
                    </svg>
                  {:else if item.icon === '+'}
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <line x1="12" y1="5" x2="12" y2="19"></line>
                      <line x1="5" y1="12" x2="19" y2="12"></line>
                    </svg>
                  {:else if item.icon === '/'}
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <circle cx="11" cy="11" r="8"></circle>
                      <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                    </svg>
                  {:else if item.icon === 'cog'}
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <circle cx="12" cy="12" r="3"></circle>
                      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
                    </svg>
                  {:else if item.icon === 'chat'}
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                    </svg>
                  {:else if item.icon === 'code'}
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <polyline points="16 18 22 12 16 6"></polyline>
                      <polyline points="8 6 2 12 8 18"></polyline>
                    </svg>
                  {:else if item.icon === 'trash'}
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <polyline points="3 6 5 6 21 6"></polyline>
                      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                    </svg>
                  {/if}
                </span>
                <span class="item-content">
                  <span class="item-label">{(item.type === 'page' || item.type === 'mention') ? (item.title || 'Untitled') : item.label}</span>
                  {#if (item.type === 'page' || item.type === 'mention') && item.projectName}
                    <span class="item-meta">{item.projectName}</span>
                  {/if}
                </span>
                {#if item.shortcut}
                  <kbd class="item-shortcut">{getShortcutDisplay(item.shortcut)}</kbd>
                {/if}
              </button>
            {/if}
          {/each}
        {/if}
      </div>

      <div class="command-palette-footer">
        <span class="footer-hint open-hint">
          <kbd>{isMac ? '⌘' : 'Ctrl'}</kbd><kbd>K</kbd> to open
        </span>
        <span class="footer-hint">
          <kbd>↑</kbd><kbd>↓</kbd> to navigate
        </span>
        <span class="footer-hint">
          <kbd>↵</kbd> to select
        </span>
        <span class="footer-hint">
          <kbd>esc</kbd> to close
        </span>
      </div>
    </div>
  </div>
{/if}

<style>
  .command-palette-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: flex-start;
    justify-content: center;
    padding-top: 15vh;
    z-index: 10001;
    animation: fadeIn 0.15s ease-out;
  }

  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }

  @keyframes scaleIn {
    from {
      opacity: 0;
      transform: scale(0.95);
    }
    to {
      opacity: 1;
      transform: scale(1);
    }
  }

  .command-palette {
    width: 100%;
    max-width: 560px;
    max-height: 70vh;
    background: var(--bg-primary, #fff);
    border-radius: 12px;
    box-shadow: 0 16px 70px rgba(0, 0, 0, 0.2), 0 0 0 1px var(--border-light, rgba(0,0,0,0.08));
    display: flex;
    flex-direction: column;
    overflow: hidden;
    animation: scaleIn 0.15s ease-out;
  }

  .command-palette-header {
    padding: 12px 16px;
    border-bottom: 1px solid var(--border-light, rgba(0,0,0,0.08));
  }

  .search-input-wrapper {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .search-icon {
    width: 18px;
    height: 18px;
    color: var(--text-tertiary, #999);
    flex-shrink: 0;
  }

  .search-input {
    flex: 1;
    border: none;
    background: transparent;
    font-size: 1rem;
    color: var(--text-primary, #37352f);
    outline: none;
    padding: 4px 0;
  }

  .search-input::placeholder {
    color: var(--text-tertiary, #999);
  }

  .escape-hint {
    font-size: 0.7rem;
    padding: 2px 6px;
    background: var(--bg-secondary, #f5f5f5);
    border: 1px solid var(--border-light, rgba(0,0,0,0.08));
    border-radius: 4px;
    color: var(--text-tertiary, #999);
    font-family: inherit;
  }

  .command-palette-list {
    flex: 1;
    overflow-y: auto;
    padding: 8px 0;
  }

  .no-results {
    padding: 32px 16px;
    text-align: center;
    color: var(--text-tertiary, #999);
    font-size: 0.9rem;
  }

  .list-header {
    padding: 8px 16px 4px;
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-tertiary, #999);
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .header-count {
    background: var(--bg-hover, rgba(55, 53, 47, 0.08));
    padding: 1px 6px;
    border-radius: 10px;
    font-size: 0.65rem;
    font-weight: 500;
  }

  .expand-toggle {
    color: var(--text-secondary, #666);
  }

  .expand-label {
    font-size: 0.8rem;
    color: var(--text-secondary, #666);
  }

  .list-item {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    padding: 8px 16px;
    border: none;
    background: transparent;
    text-align: left;
    cursor: pointer;
    transition: background 0.1s;
    font-family: inherit;
    font-size: 0.9rem;
    color: var(--text-primary, #37352f);
  }

  .list-item:hover,
  .list-item.selected {
    background: var(--bg-hover, rgba(55, 53, 47, 0.08));
  }

  .list-item.selected {
    background: rgba(35, 131, 226, 0.1);
  }

  .list-item.danger {
    color: #dc2626;
  }

  .list-item.danger .item-icon {
    color: #dc2626;
  }

  .item-icon {
    width: 18px;
    height: 18px;
    flex-shrink: 0;
    color: var(--text-tertiary, #999);
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .item-icon svg {
    width: 16px;
    height: 16px;
  }

  .item-content {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
  }

  .item-label {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .item-meta {
    font-size: 0.8rem;
    color: var(--text-tertiary, #999);
    flex-shrink: 0;
  }

  .item-shortcut {
    font-size: 0.7rem;
    padding: 2px 6px;
    background: var(--bg-secondary, #f5f5f5);
    border: 1px solid var(--border-light, rgba(0,0,0,0.08));
    border-radius: 4px;
    color: var(--text-tertiary, #999);
    font-family: inherit;
    flex-shrink: 0;
  }

  .command-palette-footer {
    padding: 8px 16px;
    border-top: 1px solid var(--border-light, rgba(0,0,0,0.08));
    display: flex;
    gap: 16px;
    justify-content: center;
    background: var(--bg-secondary, #fafafa);
  }

  .footer-hint {
    font-size: 0.75rem;
    color: var(--text-tertiary, #999);
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .footer-hint kbd {
    font-size: 0.65rem;
    padding: 1px 4px;
    background: var(--bg-primary, #fff);
    border: 1px solid var(--border-light, rgba(0,0,0,0.1));
    border-radius: 3px;
    font-family: inherit;
  }

  /* Mobile adjustments */
  @media (max-width: 600px) {
    .command-palette-overlay {
      padding-top: 10vh;
      padding-left: 16px;
      padding-right: 16px;
    }

    .command-palette {
      max-height: 80vh;
    }

    .command-palette-footer {
      display: none;
    }
  }
</style>
