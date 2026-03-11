<script>
  import Modal from './Modal.svelte';
  import { buildTree } from '../utils/buildTree.js';
  import { showToast } from '../toast.js';
  import { bulkMovePages } from '../../api.js';
  import { broadcastSidenavChanged } from '../sidenavBroadcast.js';
  import { isDemoMode, showDemoPrompt } from '../../demo/index.js';
  import { prompt } from '../modal.js';
  import { createFolder as createFolderApi } from '../../api.js';

  let {
    open = $bindable(false),
    projectId = '',
    pageId = '',
    pageTitle = '',
    currentFolderId = null,
    folders = [],
    onmoved = () => {},
  } = $props();

  let loading = $state(false);
  let selectedFolderId = $state(undefined); // undefined = nothing selected yet

  let tree = $derived(buildTree(folders, []));

  // Reset selection when modal opens
  $effect(() => {
    if (open) selectedFolderId = undefined;
  });

  function handleSelect(folderId) {
    if (folderId === currentFolderId) return;
    selectedFolderId = folderId;
  }

  async function handleMove() {
    if (selectedFolderId === undefined || selectedFolderId === currentFolderId) return;

    if (isDemoMode()) {
      open = false;
      showDemoPrompt();
      return;
    }

    loading = true;
    try {
      await bulkMovePages(projectId, [pageId], selectedFolderId);
      showToast("Page moved");
      broadcastSidenavChanged();
      onmoved();
      open = false;
    } catch (error) {
      showToast(error.message || "Failed to move page", "error");
    } finally {
      loading = false;
    }
  }

  async function handleCreateFolder() {
    open = false;

    if (isDemoMode()) {
      showDemoPrompt();
      return;
    }

    const name = await prompt({
      title: "New Folder",
      label: "Folder name",
      value: "",
      confirmText: "Create",
    });

    if (!name) return;

    try {
      await createFolderApi(projectId, name);
      showToast("Folder created");
      broadcastSidenavChanged();
    } catch (error) {
      showToast(error.message || "Failed to create folder", "error");
    }
  }

  function handleCancel() {
    open = false;
  }

  function truncateTitle(title, max = 30) {
    if (!title || title.length <= max) return title || "Untitled";
    return title.slice(0, max) + "...";
  }
</script>

<Modal bind:open title={'Move "' + truncateTitle(pageTitle) + '"'} size="sm" onclose={handleCancel}>
  {#snippet children()}
    {#if folders.length === 0}
      <p class="move-empty">No folders in this project.</p>
      <button
        type="button"
        class="move-create-folder-btn"
        onclick={handleCreateFolder}
        disabled={loading}
      >
        + Create Folder
      </button>
    {:else}
      <div class="move-folder-list" role="listbox" aria-label="Select destination folder">
        <button
          type="button"
          class="move-folder-item"
          class:current={currentFolderId === null}
          class:selected={selectedFolderId === null}
          disabled={currentFolderId === null || loading}
          onclick={() => handleSelect(null)}
          role="option"
          aria-selected={selectedFolderId === null}
        >
          <span class="move-folder-name">Project root</span>
          {#if currentFolderId === null}
            <span class="move-current-label">(current)</span>
          {/if}
        </button>
        {#each tree.rootFolders as folder (folder.external_id)}
          {@render folderRow(folder, 0)}
        {/each}
      </div>
    {/if}
  {/snippet}

  {#snippet footer({ close })}
    <button
      type="button"
      class="modal-btn-secondary"
      onclick={handleCancel}
      disabled={loading}
    >
      Cancel
    </button>
    {#if folders.length > 0}
      <button
        type="button"
        class="modal-btn-primary"
        onclick={handleMove}
        disabled={selectedFolderId === undefined || selectedFolderId === currentFolderId || loading}
      >
        {loading ? 'Moving…' : 'Move'}
      </button>
    {/if}
  {/snippet}
</Modal>

{#snippet folderRow(folder, depth)}
  <button
    type="button"
    class="move-folder-item"
    class:current={folder.external_id === currentFolderId}
    class:selected={folder.external_id === selectedFolderId}
    style="padding-left: {12 + depth * 16}px"
    disabled={folder.external_id === currentFolderId || loading}
    onclick={() => handleSelect(folder.external_id)}
    role="option"
    aria-selected={folder.external_id === selectedFolderId}
  >
    <svg class="move-folder-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
    <span class="move-folder-name">{folder.name}</span>
    {#if folder.external_id === currentFolderId}
      <span class="move-current-label">(current)</span>
    {/if}
  </button>
  {#each folder.subfolders as sub (sub.external_id)}
    {@render folderRow(sub, depth + 1)}
  {/each}
{/snippet}

<style>
  .move-folder-list {
    display: flex;
    flex-direction: column;
    gap: 2px;
    max-height: 280px;
    overflow: hidden auto;
  }

  .move-folder-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    border: none;
    background: none;
    cursor: pointer;
    font-size: 0.875rem;
    color: var(--text-primary);
    border-radius: 6px;
    text-align: left;
    width: 100%;
    transition: background 0.1s;
  }

  .move-folder-item:hover:not(:disabled) {
    background: rgba(55, 53, 47, 0.06);
  }

  .move-folder-item:disabled {
    cursor: default;
    opacity: 0.6;
  }

  .move-folder-item.current {
    background: rgba(55, 53, 47, 0.04);
  }

  .move-folder-item.selected {
    background: rgba(55, 53, 47, 0.08);
    font-weight: 500;
  }

  .move-folder-icon {
    flex-shrink: 0;
    opacity: 0.5;
  }

  .move-folder-name {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .move-current-label {
    font-size: 0.75rem;
    color: var(--text-secondary, #6b7280);
    flex-shrink: 0;
  }

  .move-empty {
    color: var(--text-secondary, #6b7280);
    font-size: 0.875rem;
    text-align: center;
    margin: 0.5rem 0 1rem;
  }

  .move-create-folder-btn {
    display: block;
    width: 100%;
    padding: 8px 12px;
    border: 1px dashed var(--border-light, #d1d5db);
    background: none;
    cursor: pointer;
    font-size: 0.875rem;
    color: var(--text-secondary, #6b7280);
    border-radius: 6px;
    text-align: center;
    transition: background 0.1s, color 0.1s;
  }

  .move-create-folder-btn:hover {
    background: rgba(55, 53, 47, 0.04);
    color: var(--text-primary);
  }

  :root.dark .move-folder-item:hover:not(:disabled),
  [data-theme="dark"] .move-folder-item:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.06);
  }

  :root.dark .move-folder-item.current,
  [data-theme="dark"] .move-folder-item.current {
    background: rgba(255, 255, 255, 0.04);
  }

  :root.dark .move-folder-item.selected,
  [data-theme="dark"] .move-folder-item.selected {
    background: rgba(255, 255, 255, 0.08);
  }

  :root.dark .move-create-folder-btn:hover,
  [data-theme="dark"] .move-create-folder-btn:hover {
    background: rgba(255, 255, 255, 0.04);
  }
</style>
