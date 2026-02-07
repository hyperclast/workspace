<script>
  import Modal from './Modal.svelte';
  import { showToast } from '../toast.js';
  import {
    fetchPageSharing,
    addPageEditor,
    removePageEditor,
    updatePageEditorRole,
    generateAccessCode,
    removeAccessCode,
  } from '../../api.js';

  let {
    open = $bindable(false),
    pageId = '',
    pageTitle = '',
    onAccessCodeChange = () => {},
  } = $props();

  let email = $state('');
  let newRole = $state('editor');
  let loading = $state(false);
  let addLoading = $state(false);
  let error = $state('');
  let success = $state('');
  let inputEl = $state(null);
  let confirmingRemove = $state(null);
  let removing = $state(false);
  let updatingRole = $state(null);

  // Sharing settings state
  let yourAccess = $state('');
  let accessCode = $state(null);
  let canManageSharing = $state(false);
  let accessGroups = $state([]);
  let orgName = $state('');
  let projectName = $state('');
  let publicLinkLoading = $state(false);
  let confirmingDeactivate = $state(false);

  async function loadSharing() {
    if (!pageId) return;

    loading = true;
    error = '';

    try {
      const data = await fetchPageSharing(pageId);
      yourAccess = data.your_access || '';
      accessCode = data.access_code || null;
      canManageSharing = data.can_manage_sharing || false;
      accessGroups = data.access_groups || [];
      orgName = data.org_name || '';
      projectName = data.project_name || '';
    } catch (e) {
      console.error('Error loading sharing settings:', e);
      error = 'Failed to load sharing settings';
    } finally {
      loading = false;
    }
  }

  // Removed loadEditors - now handled by loadSharing

  async function handleAddEditor() {
    const trimmedEmail = email.trim();

    if (!trimmedEmail) {
      error = 'Email is required';
      success = '';
      return;
    }

    if (!trimmedEmail.includes('@')) {
      error = 'Please enter a valid email';
      success = '';
      return;
    }

    addLoading = true;
    error = '';
    success = '';

    try {
      const data = await addPageEditor(pageId, trimmedEmail, newRole);
      email = '';
      newRole = 'editor';
      success = `Invitation sent to ${data.email}`;
      await loadSharing();
    } catch (e) {
      console.error('Error adding collaborator:', e);
      error = e.message || 'Failed to add collaborator';
    } finally {
      addLoading = false;
    }
  }

  function startRemove(editorId) {
    confirmingRemove = editorId;
  }

  function cancelRemove() {
    confirmingRemove = null;
  }

  async function confirmRemove(editor) {
    removing = true;
    try {
      await removePageEditor(pageId, editor.external_id);
      confirmingRemove = null;
      await loadSharing();
    } catch (e) {
      console.error('Error removing collaborator:', e);
      error = e.message || 'Failed to remove collaborator';
      confirmingRemove = null;
    } finally {
      removing = false;
    }
  }

  async function updateRole(editor, updatedRole) {
    if (updatingRole) return;

    updatingRole = editor.external_id;
    error = '';
    success = '';

    try {
      await updatePageEditorRole(pageId, editor.external_id, updatedRole);
      success = `Updated ${editor.email} to ${updatedRole === 'editor' ? 'can edit' : 'can view'}`;
      await loadSharing();
    } catch (e) {
      console.error('Error updating role:', e);
      error = e.message || 'Failed to update role';
    } finally {
      updatingRole = null;
    }
  }

  function getShareUrl() {
    return `${window.location.origin}/share/pages/${accessCode}/`;
  }

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(getShareUrl());
      showToast('Copied to clipboard!');
    } catch (err) {
      console.error('Failed to copy:', err);
      showToast('Failed to copy', 'error');
    }
  }

  async function activatePublicLink() {
    publicLinkLoading = true;
    error = '';

    try {
      const data = await generateAccessCode(pageId);
      accessCode = data.access_code;
      onAccessCodeChange(accessCode);
      showToast('View-only link created');
    } catch (e) {
      console.error('Error creating public link:', e);
      error = 'Failed to create view-only link';
    } finally {
      publicLinkLoading = false;
    }
  }

  function startDeactivate() {
    confirmingDeactivate = true;
  }

  function cancelDeactivate() {
    confirmingDeactivate = false;
  }

  async function confirmDeactivate() {
    publicLinkLoading = true;
    error = '';

    try {
      await removeAccessCode(pageId);
      accessCode = null;
      confirmingDeactivate = false;
      onAccessCodeChange(null);
      showToast('View-only link deactivated');
    } catch (e) {
      console.error('Error deactivating public link:', e);
      error = 'Failed to deactivate view-only link';
    } finally {
      publicLinkLoading = false;
    }
  }

  function handleKeydown(e) {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleAddEditor();
    }
  }

  function handleClose() {
    email = '';
    newRole = 'editor';
    error = '';
    success = '';
    accessGroups = [];
    confirmingRemove = null;
    confirmingDeactivate = false;
  }

  function scrollToStart(node) {
    requestAnimationFrame(() => {
      node.scrollLeft = 0;
    });
  }

  $effect(() => {
    if (open && pageId) {
      loadSharing();
      setTimeout(() => inputEl?.focus(), 100);
    }
  });
</script>

<Modal bind:open title="Share Page" size="wide" onclose={handleClose}>
  {#snippet children()}
    {#if yourAccess}
      <div class="your-access-box">Your access level: <strong>{yourAccess}</strong></div>
    {/if}

    <p class="modal-description">Add collaborators to this page</p>

    {#if canManageSharing}
      <div class="share-add-section">
        <div class="share-input-group">
          <input
            bind:this={inputEl}
            bind:value={email}
            type="email"
            placeholder="collaborator@example.com"
            onkeydown={handleKeydown}
            disabled={addLoading}
          />
          <select
            class="role-select add-role-select"
            bind:value={newRole}
            disabled={addLoading}
          >
            <option value="editor">Can edit</option>
            <option value="viewer">Can view</option>
          </select>
          <button
            type="button"
            class="modal-btn-primary"
            onclick={handleAddEditor}
            disabled={addLoading}
          >
            {addLoading ? 'Adding...' : 'Add'}
          </button>
        </div>
      </div>
    {/if}

    <div class="share-editors-section">
      <h4 class="share-editors-heading">Who can access this page?</h4>

      {#if loading}
        <div class="share-empty">Loading...</div>
      {:else}
        {@const summaryGroups = accessGroups.filter(g => !g.can_edit)}
        {@const pageGroup = accessGroups.find(g => g.can_edit)}

        <!-- Summary cards for org members and project collaborators -->
        {#if summaryGroups.length > 0}
          <div class="access-summary-cards">
            {#each summaryGroups as group (group.key)}
              <div class="access-summary-card">
                <div class="access-summary-header">
                  <span class="access-summary-label">{group.label}</span>
                  {#if group.user_count > 0}
                    <span class="access-summary-count">{group.user_count}</span>
                  {/if}
                </div>
                <div class="access-summary-description">{group.description}</div>
              </div>
            {/each}
          </div>
        {/if}

        <!-- Page collaborators section with individual users -->
        {#if pageGroup}
          <div class="page-collaborators-section">
            <div class="page-collaborators-header">
              <span class="access-group-label">{pageGroup.label}</span>
              {#if pageGroup.user_count > 0}
                <span class="access-group-count">{pageGroup.user_count}</span>
              {/if}
            </div>
            <div class="page-collaborators-description">{pageGroup.description}</div>
            <div class="page-collaborators-list">
              {#if pageGroup.users.length === 0}
                <div class="share-empty-group">No one added yet</div>
              {:else}
                {#each pageGroup.users as user (user.external_id)}
                  <div class="share-editor-item">
                    <div class="share-editor-info">
                      <span class="share-editor-email">{user.email}</span>
                      {#if user.is_owner}
                        <span class="share-badge owner">Owner</span>
                      {:else if user.is_pending}
                        <span class="share-badge pending">Pending</span>
                      {/if}
                    </div>
                    <div class="share-editor-actions">
                      {#if user.is_owner}
                        <span class="role-display">Full access</span>
                      {:else}
                        <select
                          class="role-select"
                          value={user.role}
                          onchange={(e) => updateRole(user, e.target.value)}
                          disabled={updatingRole === user.external_id || !canManageSharing}
                        >
                          <option value="viewer">Can view</option>
                          <option value="editor">Can edit</option>
                        </select>
                        {#if canManageSharing}
                          {#if confirmingRemove === user.external_id}
                            <div class="inline-confirm">
                              <button
                                type="button"
                                class="inline-btn cancel"
                                onclick={cancelRemove}
                                disabled={removing}
                              >
                                Cancel
                              </button>
                              <button
                                type="button"
                                class="inline-btn confirm"
                                onclick={() => confirmRemove(user)}
                                disabled={removing}
                              >
                                {removing ? '...' : 'Remove'}
                              </button>
                            </div>
                          {:else}
                            <button
                              type="button"
                              class="share-remove-btn"
                              title="Remove"
                              onclick={() => startRemove(user.external_id)}
                            >
                              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <line x1="18" y1="6" x2="6" y2="18"></line>
                                <line x1="6" y1="6" x2="18" y2="18"></line>
                              </svg>
                            </button>
                          {/if}
                        {/if}
                      {/if}
                    </div>
                  </div>
                {/each}
              {/if}
            </div>
          </div>
        {/if}
      {/if}
    </div>

    <div class="public-link-section">
      <h4 class="share-editors-heading">Public link</h4>

      {#if accessCode}
        <div class="link-active-box">
          <div class="link-input-group">
            <input
              type="text"
              readonly
              tabindex="-1"
              value={getShareUrl()}
              onclick={(e) => e.target.select()}
              use:scrollToStart
            />
            <button
              type="button"
              class="copy-btn"
              onclick={copyLink}
              title="Copy link"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
              </svg>
              Copy
            </button>
          </div>
          <div class="link-status">
            <div class="link-status-info">
              <svg class="eye-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                <circle cx="12" cy="12" r="3"></circle>
              </svg>
              <span>Anyone with this link can view</span>
            </div>
            {#if canManageSharing}
              {#if confirmingDeactivate}
                <div class="inline-confirm">
                  <button
                    type="button"
                    class="inline-btn cancel"
                    onclick={cancelDeactivate}
                    disabled={publicLinkLoading}
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    class="inline-btn confirm"
                    onclick={confirmDeactivate}
                    disabled={publicLinkLoading}
                  >
                    {publicLinkLoading ? 'Deactivating...' : 'Deactivate'}
                  </button>
                </div>
              {:else}
                <button
                  type="button"
                  class="deactivate-btn"
                  onclick={startDeactivate}
                  disabled={publicLinkLoading}
                >
                  Deactivate
                </button>
              {/if}
            {/if}
          </div>
        </div>
      {:else}
        <div class="link-inactive-box">
          <p class="link-inactive-description">
            Create a view-only link that anyone can use to view this page without logging in.
          </p>
          {#if canManageSharing}
            <button
              type="button"
              class="activate-link-btn"
              onclick={activatePublicLink}
              disabled={publicLinkLoading}
            >
              {publicLinkLoading ? 'Creating...' : 'Create view-only link'}
            </button>
          {/if}
        </div>
      {/if}
    </div>
  {/snippet}

  {#snippet footer({ close })}
    {#if error || success}
      <span class="footer-message {error ? 'error' : 'success'}">
        {error || success}
      </span>
    {/if}
    <button type="button" class="modal-btn-secondary" onclick={close}>
      Done
    </button>
  {/snippet}
</Modal>

<style>
  .modal-description {
    color: var(--text-primary, #374151);
    font-size: 0.95rem;
    margin: 0 0 1.25rem 0;
  }

  .share-add-section {
    margin-bottom: 1.5rem;
    padding-bottom: 1.5rem;
    border-bottom: 1px solid var(--border-light, #e5e7eb);
  }

  .share-input-group {
    display: flex;
    gap: 0.5rem;
  }

  .share-input-group input {
    flex: 1;
    padding: 0.625rem 0.75rem;
    font-size: 0.95rem;
    border: 1px solid var(--border-medium, #d1d5db);
    border-radius: 6px;
    background: var(--bg-primary, white);
    color: var(--text-primary, #1f2937);
  }

  .share-input-group input:focus {
    outline: none;
    border-color: #667eea;
    box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
  }

  .share-input-group input:disabled {
    background: var(--bg-secondary, #f3f4f6);
  }

  .add-role-select {
    padding: 0.625rem 0.5rem;
    font-size: 0.875rem;
    border: 1px solid var(--border-medium, #d1d5db);
    border-radius: 6px;
    background: var(--bg-primary, white);
    color: var(--text-primary, #1f2937);
    cursor: pointer;
    min-width: 100px;
  }

  .add-role-select:focus {
    outline: none;
    border-color: #667eea;
    box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
  }

  .add-role-select:disabled {
    background: var(--bg-secondary, #f3f4f6);
    cursor: not-allowed;
  }

  .footer-message {
    font-size: 0.85rem;
    margin-right: auto;
    padding: 0.25rem 0;
  }

  .footer-message.error {
    color: #dc2626;
  }

  .footer-message.success {
    color: #059669;
  }

  .share-editors-heading {
    font-weight: 600;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-secondary, #6b7280);
    margin: 0 0 0.75rem 0;
  }

  .your-access-box {
    font-size: 0.85rem;
    color: var(--text-secondary, #6b7280);
    padding: 0.5rem 0.75rem;
    margin-bottom: 1rem;
    border: 1px solid var(--border-light, #e5e7eb);
    border-radius: 6px;
    background: var(--bg-secondary, #f9fafb);
  }

  .your-access-box strong {
    color: var(--text-primary, #1f2937);
  }

  .share-editors-section {
    margin-bottom: 1.5rem;
  }

  .share-empty {
    padding: 1.25rem;
    text-align: center;
    color: var(--text-secondary, #6b7280);
    font-size: 0.9rem;
    border: 1px solid var(--border-light, #e5e7eb);
    border-radius: 8px;
  }

  /* Summary cards for org/project access */
  .access-summary-cards {
    display: flex;
    gap: 0.75rem;
    margin-bottom: 1rem;
  }

  @media (max-width: 480px) {
    .access-summary-cards {
      flex-direction: column;
    }
  }

  .access-summary-card {
    flex: 1;
    padding: 0.75rem;
    border: 1px solid var(--border-light, #e5e7eb);
    border-radius: 8px;
    background: var(--bg-secondary, #f9fafb);
    min-width: 0; /* Prevent flex items from overflowing */
  }

  .access-summary-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.25rem;
  }

  .access-summary-label {
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--text-primary, #374151);
  }

  .access-summary-count {
    font-size: 0.7rem;
    font-weight: 500;
    color: var(--text-secondary, #6b7280);
    background: var(--border-light, #e5e7eb);
    padding: 0.1rem 0.4rem;
    border-radius: 10px;
  }

  .access-summary-description {
    font-size: 0.75rem;
    color: var(--text-secondary, #6b7280);
    line-height: 1.4;
  }

  /* Page collaborators section */
  .page-collaborators-section {
    border: 1px solid var(--border-light, #e5e7eb);
    border-radius: 8px;
    overflow: hidden;
  }

  .page-collaborators-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.75rem 1rem 0.25rem;
    background: var(--bg-secondary, #f9fafb);
  }

  .page-collaborators-description {
    font-size: 0.75rem;
    color: var(--text-secondary, #6b7280);
    padding: 0 1rem 0.75rem;
    background: var(--bg-secondary, #f9fafb);
  }

  .page-collaborators-list {
    background: var(--bg-primary, white);
    max-height: 200px;
    overflow-y: auto;
  }

  .access-group-label {
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--text-primary, #374151);
  }

  .access-group-count {
    font-size: 0.7rem;
    font-weight: 500;
    color: var(--text-secondary, #6b7280);
    background: var(--border-light, #e5e7eb);
    padding: 0.1rem 0.4rem;
    border-radius: 10px;
  }

  .share-empty-group {
    padding: 0.75rem 1rem;
    color: var(--text-muted, #9ca3af);
    font-size: 0.875rem;
    font-style: italic;
  }

  .share-editor-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.75rem 1rem;
    border-bottom: 1px solid var(--border-light, #f3f4f6);
  }

  .share-editor-item:last-child {
    border-bottom: none;
  }

  .share-editor-info {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    min-width: 0;
  }

  .share-editor-email {
    font-size: 0.9rem;
    font-weight: 500;
    color: var(--text-primary, #1f2937);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .share-editor-actions {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-shrink: 0;
  }

  .role-select {
    padding: 0.25rem 0.5rem;
    font-size: 0.8rem;
    border: 1px solid var(--border-light, #e5e7eb);
    border-radius: 4px;
    background: var(--bg-primary, white);
    color: var(--text-primary, #1f2937);
    cursor: pointer;
    appearance: auto;
  }

  .role-select:hover:not(:disabled) {
    border-color: var(--border-medium, #d1d5db);
  }

  .role-select:focus {
    outline: none;
    border-color: #667eea;
    box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.1);
  }

  .role-select:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .role-display {
    font-size: 0.8rem;
    color: var(--text-secondary, #6b7280);
    padding: 0.25rem 0.5rem;
  }

  .share-badge {
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    padding: 0.2rem 0.4rem;
    border-radius: 4px;
    flex-shrink: 0;
  }

  .share-badge.owner {
    background: #dbeafe;
    color: #1e40af;
  }

  .share-badge.pending {
    background: #fef3c7;
    color: #92400e;
  }

  .share-remove-btn {
    background: none;
    border: none;
    padding: 0.375rem;
    cursor: pointer;
    color: var(--text-muted, #9ca3af);
    border-radius: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: color 0.15s, background 0.15s;
  }

  .share-remove-btn:hover {
    color: #ef4444;
    background: rgba(239, 68, 68, 0.08);
  }

  .inline-confirm {
    display: flex;
    gap: 0.375rem;
  }

  .inline-btn {
    padding: 0.25rem 0.5rem;
    font-size: 0.75rem;
    border-radius: 4px;
    border: none;
    cursor: pointer;
    font-weight: 500;
    transition: background 0.15s;
  }

  .inline-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .inline-btn.cancel {
    background: var(--bg-secondary, #f3f4f6);
    color: var(--text-secondary, #4b5563);
  }

  .inline-btn.cancel:hover:not(:disabled) {
    background: var(--border-light, #e5e7eb);
  }

  .inline-btn.confirm {
    background: #fee2e2;
    color: #dc2626;
  }

  .inline-btn.confirm:hover:not(:disabled) {
    background: #fecaca;
  }

  /* Public Link Section */
  .public-link-section {
    border-top: 1px solid var(--border-light, #e5e7eb);
    padding-top: 1.5rem;
  }

  .link-active-box {
    border: 1px solid var(--border-light, #e5e7eb);
    border-radius: 8px;
    padding: 1rem;
  }

  .link-input-group {
    display: flex;
    align-items: stretch;
    gap: 0.5rem;
    margin-bottom: 0.75rem;
  }

  .link-input-group input {
    flex: 1;
    padding: 0 0.75rem;
    height: 38px;
    font-size: 0.875rem;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    border: 1px solid var(--border-medium, #d1d5db);
    border-radius: 6px;
    background: var(--bg-secondary, #f9fafb);
    color: var(--text-primary, #374151);
    cursor: default;
    caret-color: transparent;
  }

  .link-input-group input:focus {
    outline: none;
  }

  .copy-btn {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0 0.875rem;
    height: 38px;
    font-size: 0.875rem;
    font-weight: 500;
    color: white;
    background: #2383e2;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.15s;
    white-space: nowrap;
  }

  .copy-btn:hover {
    background: #1a6fc9;
  }

  .copy-btn:active {
    background: #1560b5;
  }

  .link-status {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.5rem 0.75rem;
    background: #fef3c7;
    border-radius: 6px;
  }

  .link-status-info {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    color: #92400e;
    font-size: 0.85rem;
  }

  .eye-icon {
    flex-shrink: 0;
  }

  .deactivate-btn {
    padding: 0.375rem 0.75rem;
    font-size: 0.8rem;
    font-weight: 500;
    color: #92400e;
    background: white;
    border: 1px solid #fbbf24;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.15s;
  }

  .deactivate-btn:hover:not(:disabled) {
    background: #fffbeb;
    border-color: #f59e0b;
  }

  .deactivate-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .link-inactive-box {
    padding: 1rem;
    border: 1px solid var(--border-light, #e5e7eb);
    border-radius: 8px;
    background: var(--bg-secondary, #f9fafb);
    text-align: center;
  }

  .link-inactive-description {
    margin: 0 0 1rem 0;
    font-size: 0.9rem;
    color: var(--text-secondary, #6b7280);
    line-height: 1.4;
  }

  .activate-link-btn {
    padding: 0.5rem 1rem;
    font-size: 0.9rem;
    font-weight: 500;
    color: white;
    background: #2383e2;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.15s;
  }

  .activate-link-btn:hover:not(:disabled) {
    background: #1a6fc9;
  }

  .activate-link-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
</style>
