<script>
  import Modal from './Modal.svelte';
  import { API_BASE_URL } from '../../config.js';
  import { csrfFetch } from '../../csrf.js';

  let {
    open = $bindable(false),
    projectId = '',
    projectName = '',
    orgName = '',
  } = $props();

  let email = $state('');
  let editors = $state([]);
  let loading = $state(false);
  let addLoading = $state(false);
  let error = $state('');
  let success = $state('');
  let inputEl = $state(null);
  let confirmingRemove = $state(null);
  let removing = $state(false);
  let updatingRole = $state(null);

  // Sharing settings state
  let orgMembersCanAccess = $state(true);
  let canChangeAccess = $state(false);
  let sharingLoading = $state(false);
  let orgMemberCount = $state(0);
  let yourAccess = $state('');

  async function loadEditors() {
    if (!projectId) return;

    loading = true;
    error = '';

    try {
      const response = await csrfFetch(`${API_BASE_URL}/api/projects/${projectId}/editors/`);
      if (!response.ok) {
        throw new Error('Failed to load editors');
      }
      editors = await response.json();
    } catch (e) {
      console.error('Error loading editors:', e);
      editors = [];
      error = 'Failed to load collaborators';
    } finally {
      loading = false;
    }
  }

  async function loadSharingSettings() {
    if (!projectId) return;

    try {
      const response = await csrfFetch(`${API_BASE_URL}/api/projects/${projectId}/sharing/`);
      if (response.ok) {
        const data = await response.json();
        orgMembersCanAccess = data.org_members_can_access;
        canChangeAccess = data.can_change_access;
        orgMemberCount = data.org_member_count || 0;
        yourAccess = data.your_access || '';
      }
    } catch (e) {
      console.error('Error loading sharing settings:', e);
    }
  }

  async function updateOrgAccess(newValue) {
    if (!canChangeAccess || sharingLoading) return;

    sharingLoading = true;
    error = '';
    success = '';

    try {
      const response = await csrfFetch(`${API_BASE_URL}/api/projects/${projectId}/sharing/`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ org_members_can_access: newValue }),
      });

      if (response.ok) {
        const data = await response.json();
        orgMembersCanAccess = data.org_members_can_access;
        orgMemberCount = data.org_member_count || 0;
        yourAccess = data.your_access || '';
        success = newValue
          ? 'All org members can now access this project'
          : 'Project access restricted to invited collaborators only';
      } else {
        const data = await response.json().catch(() => ({}));
        error = data.message || 'Failed to update access settings';
        // Revert the checkbox if the update failed
        orgMembersCanAccess = !newValue;
      }
    } catch (e) {
      console.error('Error updating sharing settings:', e);
      error = 'Network error. Please try again.';
      orgMembersCanAccess = !newValue;
    } finally {
      sharingLoading = false;
    }
  }

  async function addEditor() {
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
      const response = await csrfFetch(`${API_BASE_URL}/api/projects/${projectId}/editors/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: trimmedEmail }),
      });

      if (response.ok) {
        const data = await response.json();
        email = '';
        success = `Invitation sent to ${data.email}`;
        await loadEditors();
      } else if (response.status === 429) {
        error = 'Too many requests. Please wait a moment.';
      } else {
        const data = await response.json().catch(() => ({}));
        error = data.message || 'Failed to add collaborator';
      }
    } catch (e) {
      console.error('Error adding collaborator:', e);
      error = 'Network error. Please try again.';
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
      const response = await csrfFetch(
        `${API_BASE_URL}/api/projects/${projectId}/editors/${editor.external_id}/`,
        { method: 'DELETE' }
      );

      if (response.ok || response.status === 204) {
        confirmingRemove = null;
        await loadEditors();
      } else {
        const data = await response.json().catch(() => ({}));
        error = data.message || 'Failed to remove collaborator';
        confirmingRemove = null;
      }
    } catch (e) {
      console.error('Error removing collaborator:', e);
      error = 'Network error. Please try again.';
      confirmingRemove = null;
    } finally {
      removing = false;
    }
  }

  async function updateRole(editor, newRole) {
    if (updatingRole) return;

    updatingRole = editor.external_id;
    error = '';
    success = '';

    try {
      const response = await csrfFetch(
        `${API_BASE_URL}/api/projects/${projectId}/editors/${editor.external_id}/`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ role: newRole }),
        }
      );

      if (response.ok) {
        // Update the local editor state
        const idx = editors.findIndex((e) => e.external_id === editor.external_id);
        if (idx !== -1) {
          editors[idx] = { ...editors[idx], role: newRole };
        }
        success = `Updated ${editor.email} to ${newRole === 'editor' ? 'can edit' : 'can view'}`;
      } else {
        const data = await response.json().catch(() => ({}));
        error = data.message || 'Failed to update role';
      }
    } catch (e) {
      console.error('Error updating role:', e);
      error = 'Network error. Please try again.';
    } finally {
      updatingRole = null;
    }
  }

  function handleKeydown(e) {
    if (e.key === 'Enter') {
      e.preventDefault();
      addEditor();
    }
  }

  function handleClose() {
    email = '';
    error = '';
    success = '';
    editors = [];
    confirmingRemove = null;
    orgMembersCanAccess = true;
    canChangeAccess = false;
    sharingLoading = false;
  }

  $effect(() => {
    if (open && projectId) {
      loadEditors();
      loadSharingSettings();
      setTimeout(() => inputEl?.focus(), 100);
    }
  });
</script>

<Modal bind:open title="Share Project" onclose={handleClose}>
  {#snippet children()}
    {#if yourAccess}
      <div class="your-access-box">Your access level: <strong>{yourAccess}</strong></div>
    {/if}

    <p class="modal-description">
      Invite collaborators to <strong>{projectName}</strong>
    </p>

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
        <button
          type="button"
          class="modal-btn-primary"
          onclick={addEditor}
          disabled={addLoading}
        >
          {addLoading ? 'Adding...' : 'Add'}
        </button>
      </div>

    </div>

    <div class="share-editors-section">
      <h4 class="share-editors-heading">Who can access this project?</h4>

      <div class="share-access-toggle">
        <label class="toggle-label">
          <input
            type="checkbox"
            checked={orgMembersCanAccess}
            onchange={(e) => updateOrgAccess(e.target.checked)}
            disabled={!canChangeAccess || sharingLoading}
          />
          <span class="toggle-text">{#if orgName}{#if orgMemberCount}All {orgMemberCount} {orgName} members{:else}All {orgName} members{/if}{:else}All org members{/if}</span>
        </label>
        {#if !canChangeAccess}
          <span class="toggle-note">Only the project owner can change this setting</span>
        {/if}
        <p class="share-access-hint">
          {#if orgMembersCanAccess}
            Anyone in the org can view and edit this project. The following people have access too.
          {:else}
            Only people listed below can access this project.
          {/if}
        </p>
      </div>
      <div class="share-editors-list">
        {#if loading}
          <div class="share-empty">Loading...</div>
        {:else if editors.length === 0}
          <div class="share-empty">No collaborators yet</div>
        {:else}
          {#each editors as editor (editor.external_id)}
            <div class="share-editor-item">
              <div class="share-editor-info">
                <span class="share-editor-email">{editor.email}</span>
                {#if editor.is_creator}
                  <span class="share-badge owner">Owner</span>
                {:else if editor.is_pending}
                  <span class="share-badge pending">Pending</span>
                {/if}
              </div>
              <div class="share-editor-actions">
                {#if editor.is_creator}
                  <span class="role-display">Full access</span>
                {:else}
                  <select
                    class="role-select"
                    value={editor.role}
                    onchange={(e) => updateRole(editor, e.target.value)}
                    disabled={updatingRole === editor.external_id}
                  >
                    <option value="viewer">Can view</option>
                    <option value="editor">Can edit</option>
                  </select>
                  {#if confirmingRemove === editor.external_id}
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
                        onclick={() => confirmRemove(editor)}
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
                      onclick={() => startRemove(editor.external_id)}
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                      </svg>
                    </button>
                  {/if}
                {/if}
              </div>
            </div>
          {/each}
        {/if}
      </div>
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
    color: #374151;
    font-size: 0.95rem;
    margin: 0 0 1.25rem 0;
  }

  .share-add-section {
    margin-bottom: 1.5rem;
    padding-bottom: 1.5rem;
    border-bottom: 1px solid #e5e7eb;
  }

  .share-input-group {
    display: flex;
    gap: 0.5rem;
  }

  .share-input-group input {
    flex: 1;
    padding: 0.625rem 0.75rem;
    font-size: 0.95rem;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    background: white;
  }

  .share-input-group input:focus {
    outline: none;
    border-color: #667eea;
    box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
  }

  .share-input-group input:disabled {
    background: #f3f4f6;
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

  .share-editors-list {
    max-height: 240px;
    overflow-y: auto;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
  }

  .share-empty {
    padding: 1.25rem;
    text-align: center;
    color: #6b7280;
    font-size: 0.9rem;
  }

  .share-editor-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.75rem 1rem;
    border-bottom: 1px solid #f3f4f6;
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
    color: #9ca3af;
    border-radius: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: color 0.15s, background 0.15s;
  }

  .share-remove-btn:hover {
    color: #ef4444;
    background: #fef2f2;
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
    background: #f3f4f6;
    color: #4b5563;
  }

  .inline-btn.cancel:hover:not(:disabled) {
    background: #e5e7eb;
  }

  .inline-btn.confirm {
    background: #fee2e2;
    color: #dc2626;
  }

  .inline-btn.confirm:hover:not(:disabled) {
    background: #fecaca;
  }

  .share-access-toggle {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    margin-bottom: 1rem;
  }

  .toggle-label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    cursor: pointer;
  }

  .toggle-label input[type="checkbox"] {
    width: 16px;
    height: 16px;
    margin: 0;
    cursor: pointer;
  }

  .toggle-label input[type="checkbox"]:disabled {
    cursor: not-allowed;
  }

  .toggle-text {
    font-size: 0.9rem;
    font-weight: 500;
    color: var(--text-primary, #1f2937);
  }

  .toggle-note {
    font-size: 0.75rem;
    color: var(--text-secondary, #6b7280);
    margin-left: 1.625rem;
  }

  .share-access-hint {
    font-size: 0.8rem;
    color: var(--text-secondary, #6b7280);
    margin: 0.5rem 0 0 0;
    line-height: 1.4;
  }
</style>
