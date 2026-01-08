<script>
  import { onMount, onDestroy } from "svelte";
  import { registerTabHandler, registerPageChangeHandler } from "../../stores/sidebar.svelte.js";
  import { fetchPageLinks, syncPageLinks } from "../../../api.js";

  let serverOutgoingLinks = $state([]);
  let incomingLinks = $state([]);
  let localOutgoingLinks = $state([]);
  let externalLinks = $state([]);
  let currentPageId = $state(null);
  let loading = $state(false);
  let linksUpdatedHandler = null;
  let contentChangeHandler = null;
  let enterPressedHandler = null;
  let lastSyncTime = 0;
  const SYNC_COOLDOWN_MS = 2000;

  const INTERNAL_LINK_REGEX = /\[([^\]]+)\]\(\/pages\/([a-zA-Z0-9]+)\/?[^)]*\)/g;

  function getDomainFromUrl(url) {
    try {
      return new URL(url).hostname;
    } catch {
      return url;
    }
  }

  function extractInternalLinksFromContent(content) {
    const linksList = [];
    const regex = new RegExp(INTERNAL_LINK_REGEX.source, 'g');
    let match;
    while ((match = regex.exec(content)) !== null) {
      const linkText = match[1];
      const pageId = match[2];
      if (pageId !== currentPageId) {
        linksList.push({
          external_id: pageId,
          title: linkText,
          link_text: linkText,
        });
      }
    }
    const seen = new Set();
    return linksList.filter((link) => {
      const key = `${link.external_id}-${link.link_text}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }

  function extractExternalLinksFromContent(content) {
    const linksList = [];
    const urlRegex = /https?:\/\/[^\s\)>\]]+/g;
    const markdownLinkRegex = /\[([^\]]+)\]\((https?:\/\/[^\s\)]+)\)/g;

    let match;
    while ((match = markdownLinkRegex.exec(content)) !== null) {
      linksList.push({
        title: match[1],
        url: match[2],
      });
    }

    const markdownUrls = new Set(linksList.map((l) => l.url));
    while ((match = urlRegex.exec(content)) !== null) {
      if (!markdownUrls.has(match[0])) {
        linksList.push({
          title: null,
          url: match[0],
        });
      }
    }

    const seen = new Set();
    return linksList.filter((link) => {
      if (seen.has(link.url)) return false;
      seen.add(link.url);
      return true;
    });
  }

  function updateLocalLinks() {
    if (!window.editorView) {
      localOutgoingLinks = [];
      externalLinks = [];
      return;
    }
    const content = window.editorView.state.doc.toString();
    localOutgoingLinks = extractInternalLinksFromContent(content);
    externalLinks = extractExternalLinksFromContent(content);
  }

  let displayOutgoingLinks = $derived(() => {
    const serverMap = new Map();
    for (const link of serverOutgoingLinks) {
      serverMap.set(link.external_id, link);
    }
    return localOutgoingLinks.map(local => {
      const serverLink = serverMap.get(local.external_id);
      if (serverLink) {
        return {
          ...local,
          title: serverLink.title || local.title,
          serverConfirmed: true,
        };
      }
      return { ...local, serverConfirmed: false };
    });
  });

  async function updateLinks() {
    if (!currentPageId) {
      serverOutgoingLinks = [];
      incomingLinks = [];
      localOutgoingLinks = [];
      externalLinks = [];
      return;
    }

    loading = true;
    updateLocalLinks();

    try {
      const data = await fetchPageLinks(currentPageId);
      serverOutgoingLinks = data.outgoing || [];
      incomingLinks = data.incoming || [];
    } catch (e) {
      console.error("Error fetching page links:", e);
      serverOutgoingLinks = [];
      incomingLinks = [];
    }

    loading = false;
  }

  function navigateToPage(externalId) {
    if (window.openPage) {
      window.openPage(externalId);
    } else {
      // Fallback for edge cases
      window.location.href = `/pages/${externalId}/`;
    }
  }

  async function triggerBackendSync() {
    if (!currentPageId) return;

    const now = Date.now();
    if (now - lastSyncTime < SYNC_COOLDOWN_MS) return;
    lastSyncTime = now;

    try {
      const content = window.editorView?.state?.doc?.toString() || "";
      const result = await syncPageLinks(currentPageId, content);
      if (result.synced) {
        serverOutgoingLinks = result.outgoing || [];
        incomingLinks = result.incoming || [];
      }
    } catch (e) {
      console.error("Error syncing links:", e);
    }
  }

  onMount(() => {
    registerTabHandler("links", updateLinks);
    registerPageChangeHandler((pageId) => {
      currentPageId = pageId;
      updateLinks();
    });

    linksUpdatedHandler = (event) => {
      const { pageId } = event.detail;
      if (pageId === currentPageId) {
        updateLinks();
      }
    };
    window.addEventListener("linksUpdated", linksUpdatedHandler);

    contentChangeHandler = () => {
      updateLocalLinks();
    };
    window.addEventListener("editorContentChanged", contentChangeHandler);

    enterPressedHandler = () => {
      triggerBackendSync();
    };
    window.addEventListener("editorEnterPressed", enterPressedHandler);

    updateLinks();
  });

  onDestroy(() => {
    if (linksUpdatedHandler) {
      window.removeEventListener("linksUpdated", linksUpdatedHandler);
    }
    if (contentChangeHandler) {
      window.removeEventListener("editorContentChanged", contentChangeHandler);
    }
    if (enterPressedHandler) {
      window.removeEventListener("editorEnterPressed", enterPressedHandler);
    }
  });
</script>

<div class="links-content">
  {#if loading}
    <div class="links-loading">Loading...</div>
  {:else}
    <div class="links-section">
      <h3 class="links-section-title">
        <svg class="links-section-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
          <path d="M10 12l-3 3 3 3"/>
          <line x1="7" y1="15" x2="15" y2="15"/>
        </svg>
        Backlinks
      </h3>
      {#if incomingLinks.length > 0}
        <div class="links-list">
          {#each incomingLinks as link (link.external_id + link.link_text)}
            <button
              class="link-item link-item-internal"
              onclick={() => navigateToPage(link.external_id)}
            >
              <svg class="link-item-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
              </svg>
              <div class="link-item-content">
                <div class="link-item-title">{link.title || "Untitled"}</div>
                <div class="link-item-subtitle">linked as "{link.link_text}"</div>
              </div>
            </button>
          {/each}
        </div>
      {:else}
        <div class="links-none">No other pages link to this page</div>
      {/if}
    </div>

    <div class="links-section">
      <h3 class="links-section-title">
        <svg class="links-section-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
          <path d="M14 12l3 3-3 3"/>
          <line x1="9" y1="15" x2="17" y2="15"/>
        </svg>
        Links
      </h3>
      {#if displayOutgoingLinks().length > 0}
        <div class="links-list">
          {#each displayOutgoingLinks() as link (link.external_id + link.link_text)}
            <button
              class="link-item link-item-internal"
              class:link-item-pending={!link.serverConfirmed}
              onclick={() => navigateToPage(link.external_id)}
            >
              <svg class="link-item-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
              </svg>
              <div class="link-item-content">
                <div class="link-item-title">{link.title || "Untitled"}</div>
                <div class="link-item-subtitle">"{link.link_text}"</div>
              </div>
            </button>
          {/each}
        </div>
      {:else}
        <div class="links-none">This page doesn't link to any other pages</div>
      {/if}
    </div>

    <div class="links-section">
      <h3 class="links-section-title">
        <svg class="links-section-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"/>
          <line x1="2" y1="12" x2="22" y2="12"/>
          <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
        </svg>
        External
      </h3>
      {#if externalLinks.length > 0}
        <div class="links-list">
          {#each externalLinks as link (link.url)}
            <a
              href={link.url}
              target="_blank"
              rel="noopener noreferrer"
              class="link-item link-item-external"
            >
              <svg class="link-item-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"/>
                <line x1="2" y1="12" x2="22" y2="12"/>
                <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
              </svg>
              <div class="link-item-content">
                <div class="link-item-title">
                  {link.title || getDomainFromUrl(link.url)}
                </div>
                <div class="link-item-url">{link.url}</div>
              </div>
            </a>
          {/each}
        </div>
      {:else}
        <div class="links-none">No external URLs on this page</div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .links-content {
    padding: 1rem;
    height: 100%;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .links-loading {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 2rem;
    color: var(--text-secondary);
  }

  .links-section {
    background: var(--bg-surface, #fafafa);
    border: 1px solid var(--border-light, rgba(0, 0, 0, 0.06));
    border-radius: 10px;
    overflow: hidden;
  }

  .links-section-title {
    font-size: 0.6875rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--text-secondary, #666);
    margin: 0;
    padding: 0.625rem 0.875rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    background: var(--bg-elevated, #f5f5f5);
    border-bottom: 1px solid var(--border-light, rgba(0, 0, 0, 0.06));
  }

  .links-section-icon {
    width: 13px;
    height: 13px;
    flex-shrink: 0;
    opacity: 0.6;
  }

  .links-none {
    font-size: 0.8125rem;
    color: var(--text-tertiary, #aaa);
    padding: 0.875rem;
    text-align: center;
  }

  .links-list {
    display: flex;
    flex-direction: column;
  }

  .link-item {
    display: flex;
    gap: 0.625rem;
    padding: 0.625rem 0.875rem;
    text-decoration: none;
    color: inherit;
    transition: background 0.15s;
    border: none;
    background: none;
    cursor: pointer;
    text-align: left;
    width: 100%;
    border-bottom: 1px solid var(--border-light, rgba(0, 0, 0, 0.04));
  }

  .link-item:last-child {
    border-bottom: none;
  }

  .link-item:hover {
    background: var(--bg-hover, rgba(0, 0, 0, 0.02));
  }

  .link-item-internal:hover {
    background: rgba(9, 105, 218, 0.04);
  }

  .link-item-icon {
    width: 15px;
    height: 15px;
    flex-shrink: 0;
    opacity: 0.4;
    margin-top: 1px;
  }

  .link-item-internal .link-item-icon {
    color: #0969da;
    opacity: 0.6;
  }

  .link-item-pending {
    opacity: 0.7;
  }

  .link-item-pending .link-item-title::after {
    content: " •";
    color: #f59e0b;
    font-size: 0.75rem;
  }

  .link-item-content {
    flex: 1;
    min-width: 0;
  }

  .link-item-title {
    font-size: 0.8125rem;
    font-weight: 500;
    color: var(--text-primary, #333);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .link-item-internal .link-item-title {
    color: #0969da;
  }

  .link-item-subtitle {
    font-size: 0.6875rem;
    color: var(--text-tertiary, #888);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    margin-top: 0.125rem;
  }

  .link-item-url {
    font-size: 0.6875rem;
    color: var(--text-tertiary, #888);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    margin-top: 0.125rem;
  }

  /* Dark mode adjustments */
  :global(.dark) .links-section {
    background: var(--bg-surface, #1e1e1e);
    border-color: var(--border-light, rgba(255, 255, 255, 0.08));
  }

  :global(.dark) .links-section-title {
    background: var(--bg-elevated, #252525);
    border-color: var(--border-light, rgba(255, 255, 255, 0.06));
  }
</style>
