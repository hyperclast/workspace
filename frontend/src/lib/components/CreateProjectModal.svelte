<script>
  import Modal from './Modal.svelte';
  import { fetchOrgs, createProject as createProjectApi } from '../../api.js';
  import { showToast } from '../toast.js';
  import { validateProjectName } from '../validation.js';

  function getTodayDateTimeString() {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    let hours = now.getHours();
    const minutes = String(now.getMinutes()).padStart(2, '0');
    const ampm = hours >= 12 ? 'pm' : 'am';
    hours = hours % 12 || 12;
    return `${year}-${month}-${day} ${hours}h${minutes}${ampm}`;
  }

  let {
    open = $bindable(false),
    oncreated = () => {},
  } = $props();

  let name = $state('');
  let selectedOrgId = $state('');
  let orgs = $state([]);
  let loading = $state(false);
  let error = $state('');
  let inputEl = $state(null);
  let orgMembersCanAccess = $state(true);

  // Derived validation state (instant feedback)
  let validationResult = $derived(validateProjectName(name));
  let showValidationError = $derived(name.trim().length > 0 && !validationResult.valid);

  // Load orgs when modal opens
  $effect(() => {
    if (open) {
      name = `Project ${getTodayDateTimeString()}`;
      loadOrgs();
    } else {
      // Reset state when closed
      name = '';
      selectedOrgId = '';
      error = '';
      loading = false;
      orgMembersCanAccess = true;
    }
  });

  async function loadOrgs() {
    try {
      orgs = await fetchOrgs();
      if (orgs.length > 0) {
        selectedOrgId = orgs[0].external_id;
      }
      // Focus and select input after orgs load
      setTimeout(() => {
        inputEl?.focus();
        inputEl?.select();
      }, 50);
    } catch (e) {
      error = 'Failed to load organizations';
    }
  }

  async function handleCreate() {
    const validation = validateProjectName(name);
    if (!validation.valid) {
      error = validation.error;
      return;
    }

    if (!selectedOrgId) {
      error = 'Please select an organization';
      return;
    }

    error = '';
    loading = true;

    try {
      const project = await createProjectApi(selectedOrgId, name.trim(), '', orgMembersCanAccess);
      const selectedOrg = orgs.find(o => o.external_id === selectedOrgId);

      const newProject = {
        ...project,
        org: {
          external_id: selectedOrgId,
          name: selectedOrg?.name || '',
        },
        pages: [],
      };

      open = false;
      oncreated(newProject);
      showToast('Project created successfully');
    } catch (e) {
      error = e.message || 'Failed to create project';
    } finally {
      loading = false;
    }
  }

  function handleCancel() {
    open = false;
  }

  function handleKeydown(e) {
    if (e.key === 'Enter' && !loading) {
      handleCreate();
    }
  }
</script>

<Modal bind:open title="New Project" size="sm">
  <div class="modal-field">
    <label for="project-name-input">Project name</label>
    <input
      bind:this={inputEl}
      bind:value={name}
      type="text"
      id="project-name-input"
      placeholder="My Project"
      maxlength="255"
      disabled={loading}
      onkeydown={handleKeydown}
      class:input-error={showValidationError}
    />
    {#if showValidationError}
      <div class="field-error">{validationResult.error}</div>
    {/if}
  </div>

  <div class="modal-field">
    <label for="project-org-select">Organization</label>
    <div class="select-wrapper">
      <select
        bind:value={selectedOrgId}
        id="project-org-select"
        disabled={loading || orgs.length === 0}
      >
        {#each orgs as org (org.external_id)}
          <option value={org.external_id}>{org.name}</option>
        {/each}
      </select>
      <svg class="select-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M6 9l6 6 6-6" />
      </svg>
    </div>
  </div>

  <div class="modal-field">
    <label class="checkbox-label">
      <input
        type="checkbox"
        bind:checked={orgMembersCanAccess}
        disabled={loading}
      />
      <span>All organization members can access</span>
    </label>
    <p class="field-hint">
      {#if orgMembersCanAccess}
        Anyone in the organization can view and edit this project.
      {:else}
        Only people you explicitly invite can access this project.
      {/if}
    </p>
  </div>

  {#if error}
    <div class="modal-error-message">{error}</div>
  {/if}

  {#snippet footer()}
    <button class="modal-btn-secondary" onclick={handleCancel} disabled={loading}>
      Cancel
    </button>
    <button
      class="modal-btn-primary"
      onclick={handleCreate}
      disabled={loading || !validationResult.valid || !selectedOrgId}
    >
      {loading ? 'Creating...' : 'Create Project'}
    </button>
  {/snippet}
</Modal>

<style>
  .modal-field {
    margin-bottom: 1rem;
  }

  .modal-field label {
    display: block;
    margin-bottom: 0.375rem;
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--text-primary);
  }

  .modal-field input,
  .modal-field select {
    width: 100%;
    padding: 0.625rem 0.75rem;
    border: 1px solid var(--border-light);
    border-radius: 6px;
    font-size: 0.9rem;
    background: var(--bg-primary);
    color: var(--text-primary);
    transition: border-color 0.15s, box-shadow 0.15s;
  }

  .select-wrapper {
    position: relative;
  }

  .select-wrapper select {
    appearance: none;
    padding-right: 2.5rem;
    cursor: pointer;
  }

  .select-chevron {
    position: absolute;
    right: 0.75rem;
    top: 50%;
    transform: translateY(-50%);
    width: 16px;
    height: 16px;
    color: var(--text-secondary, #666);
    pointer-events: none;
  }

  .select-wrapper select:disabled + .select-chevron {
    opacity: 0.5;
  }

  .modal-field input:focus,
  .modal-field select:focus {
    outline: none;
    border-color: #2383e2;
    box-shadow: 0 0 0 3px rgba(35, 131, 226, 0.1);
  }

  .modal-field input:disabled,
  .modal-field select:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .modal-error-message {
    padding: 0.625rem 0.75rem;
    background: #fef2f2;
    border: 1px solid #fecaca;
    border-radius: 6px;
    color: #dc2626;
    font-size: 0.875rem;
    margin-top: 0.5rem;
  }

  .input-error {
    border-color: #dc2626 !important;
  }

  .input-error:focus {
    box-shadow: 0 0 0 3px rgba(220, 38, 38, 0.1) !important;
  }

  .field-error {
    color: #dc2626;
    font-size: 0.8rem;
    margin-top: 0.25rem;
  }

  .checkbox-label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    cursor: pointer;
    font-weight: 500;
  }

  .checkbox-label input[type="checkbox"] {
    width: auto;
    margin: 0;
    cursor: pointer;
  }

  .checkbox-label span {
    font-size: 0.875rem;
    color: var(--text-primary);
  }

  .field-hint {
    font-size: 0.8rem;
    color: var(--text-secondary);
    margin-top: 0.375rem;
    line-height: 1.4;
  }
</style>
