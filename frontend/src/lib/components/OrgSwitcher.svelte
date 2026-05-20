<script>
  import { onMount } from "svelte";
  import {
    getCurrentOrgId,
    getCurrentOrgName,
    getAvailableOrgs,
    setAvailableOrgs,
    setCurrentOrgId,
  } from "../orgContext.js";
  import { refreshAvailableOrgs } from "../orgSwitch.js";
  import CreateOrgModal from "./CreateOrgModal.svelte";

  let currentOrgId = $state(getCurrentOrgId());
  let orgs = $state(getAvailableOrgs());
  let fallbackName = $state(getCurrentOrgName());
  let open = $state(false);
  let createModalOpen = $state(false);

  let currentOrg = $derived(orgs.find((o) => o.external_id === currentOrgId) || null);
  // For external collaborators (project-/page-editor sharing) the
  // current org lives outside the membership list shown in the
  // dropdown, so `currentOrg` is null. Fall back to the SPA-injected
  // org name from `orgContext` before showing the generic placeholder.
  let displayName = $derived(currentOrg?.name || fallbackName || "Organization");

  function refresh() {
    currentOrgId = getCurrentOrgId();
    orgs = getAvailableOrgs();
    fallbackName = getCurrentOrgName();
  }

  function close() {
    open = false;
  }

  async function handleCreated(newOrg) {
    // Refresh the org list from the server so any server-side defaults
    // are included, then switch into the newly-created organization.
    // `refreshAvailableOrgs` is shared with the initial-hydration path
    // (lib/orgSwitch.js) so both code paths fetch+set+dispatch the
    // same way.
    try {
      await refreshAvailableOrgs();
    } catch {
      // Network blip — append the new org locally so the UI still
      // shows it. The next hydrate cycle reconciles.
      setAvailableOrgs([...orgs, newOrg]);
    }
    setCurrentOrgId(newOrg.external_id);
    refresh();
  }

  // OrgSwitcher is mount()-ed by main.js. Per CLAUDE.md ("Svelte 5
  // Components with mount()") delegated onclick={} handlers on templated
  // buttons are unreliable in this setup. We use one delegated listener on
  // the root that dispatches based on data-org-action.
  function handleRootClick(e) {
    const target = e.target.closest("[data-org-action]");
    if (!target) return;
    const action = target.dataset.orgAction;
    if (action === "toggle") {
      open = !open;
    } else if (action === "select") {
      const orgId = target.dataset.orgId;
      if (orgId) {
        setCurrentOrgId(orgId);
        refresh();
      }
      close();
    } else if (action === "create") {
      close();
      createModalOpen = true;
    }
  }

  function handleDocClick(e) {
    if (!open) return;
    const root = e.target.closest?.(".org-switcher");
    if (!root) close();
  }

  function handleKeydown(e) {
    if (e.key === "Escape" && open) {
      close();
    }
  }

  // Bound via `bind:this` on the root <div> below — using
  // `document.querySelector(".org-switcher")` would silently latch onto
  // whichever instance happens to be first in the DOM, which is fine
  // today (single switcher) but would break in unexpected ways the
  // moment a second switcher is ever mounted. Plain `let` rather than
  // `$state` to dodge the Svelte 5 `mount()` + `$state` ref issue
  // documented in CLAUDE.md.
  let rootEl;

  onMount(() => {
    // Single delegated click listener on the switcher root. Survives
    // {#if open} popover re-renders without rebinding per child.
    if (rootEl) rootEl.addEventListener("click", handleRootClick);

    // External store mutations (e.g., main.js hydrating orgs after the
    // initial fetchOrgs()) tell us to refresh our local copy. We listen
    // to both event channels because they cover different shifts:
    //  - `orgs-changed` fires when the membership list changes
    //  - `current-org-changed` fires when the selected org changes
    // The second is what catches the loadPage()-driven cross-org page
    // upgrade — without it the trigger label would lag the autocomplete
    // and Ask surfaces by exactly one navigation.
    const handleStoreChange = () => refresh();
    window.addEventListener("hyperclast:orgs-changed", handleStoreChange);
    window.addEventListener("hyperclast:current-org-changed", handleStoreChange);
    document.addEventListener("click", handleDocClick);
    document.addEventListener("keydown", handleKeydown);
    return () => {
      if (rootEl) rootEl.removeEventListener("click", handleRootClick);
      window.removeEventListener("hyperclast:orgs-changed", handleStoreChange);
      window.removeEventListener("hyperclast:current-org-changed", handleStoreChange);
      document.removeEventListener("click", handleDocClick);
      document.removeEventListener("keydown", handleKeydown);
    };
  });
</script>

<div class="org-switcher" bind:this={rootEl}>
  <button
    class="org-switcher-trigger"
    type="button"
    aria-haspopup="menu"
    aria-expanded={open}
    title="Switch organization"
    data-org-action="toggle"
  >
    <span class="org-name">{displayName}</span>
    <svg
      class="org-chevron"
      class:rotated={open}
      width="10"
      height="10"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="3"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true"
    >
      <polyline points="6 9 12 15 18 9"></polyline>
    </svg>
  </button>

  {#if open}
    <div class="org-switcher-popover" role="menu">
      {#if orgs.length === 0}
        <div class="org-switcher-empty">No organizations yet</div>
      {:else}
        {#each orgs as org (org.external_id)}
          <button
            class="org-switcher-item"
            class:active={org.external_id === currentOrgId}
            role="menuitemradio"
            aria-checked={org.external_id === currentOrgId}
            data-org-action="select"
            data-org-id={org.external_id}
          >
            <span class="org-switcher-check" aria-hidden="true">
              {#if org.external_id === currentOrgId}
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
              {/if}
            </span>
            <span class="org-switcher-name">{org.name}</span>
          </button>
        {/each}
      {/if}
      <div class="org-switcher-divider"></div>
      <button
        class="org-switcher-item org-switcher-create"
        type="button"
        data-org-action="create"
      >
        <span class="org-switcher-check" aria-hidden="true">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <line x1="12" y1="5" x2="12" y2="19"></line>
            <line x1="5" y1="12" x2="19" y2="12"></line>
          </svg>
        </span>
        <span class="org-switcher-name">New organization</span>
      </button>
    </div>
  {/if}
</div>

<CreateOrgModal bind:open={createModalOpen} oncreated={handleCreated} />

<style>
  .org-switcher {
    position: relative;
    display: inline-flex;
    align-items: center;
    min-width: 0;
    flex: 1 1 auto;
  }

  .org-switcher-trigger {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 6px 2px 4px;
    margin: 0;
    border: none;
    background: transparent;
    cursor: pointer;
    border-radius: 5px;
    color: var(--text-tertiary);
    font: inherit;
    font-size: 10.5px;
    font-weight: 600;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    line-height: 1;
    max-width: 100%;
    min-width: 0;
    transition: background 0.15s, color 0.15s;
  }

  .org-switcher-trigger:hover {
    background: var(--bg-hover-subtle);
    color: var(--text-secondary);
  }

  .org-switcher-trigger:focus-visible {
    outline: 2px solid var(--accent-color);
    outline-offset: 1px;
  }

  .org-name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 160px;
  }

  .org-chevron {
    flex-shrink: 0;
    transition: transform 0.15s ease;
    opacity: 0.8;
  }

  .org-chevron.rotated {
    transform: rotate(180deg);
  }

  .org-switcher-popover {
    position: absolute;
    top: calc(100% + 4px);
    left: 0;
    min-width: 220px;
    max-width: 260px;
    background: var(--bg-elevated);
    border: 1px solid var(--border-light);
    border-radius: 8px;
    box-shadow: var(--shadow-md);
    padding: 4px;
    z-index: 100;
    display: flex;
    flex-direction: column;
  }

  .org-switcher-empty {
    padding: 8px 10px;
    color: var(--text-tertiary);
    font-size: 0.8rem;
  }

  .org-switcher-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 10px;
    border: none;
    background: transparent;
    cursor: pointer;
    border-radius: 5px;
    color: var(--text-primary);
    font: inherit;
    font-size: 0.875rem;
    text-align: left;
    width: 100%;
    transition: background 0.12s;
  }

  .org-switcher-item:hover {
    background: var(--bg-hover-subtle);
  }

  .org-switcher-item:focus-visible {
    outline: 2px solid var(--accent-color);
    outline-offset: -2px;
  }

  .org-switcher-check {
    width: 14px;
    height: 14px;
    color: var(--accent-color);
    flex-shrink: 0;
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }

  .org-switcher-create .org-switcher-check {
    color: var(--text-secondary);
  }

  .org-switcher-name {
    flex: 1 1 auto;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .org-switcher-divider {
    height: 1px;
    background: var(--border-light);
    margin: 4px 0;
  }
</style>
