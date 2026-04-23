<script>
  import Modal from './Modal.svelte';
  import { fetchProjectsWithPages, updateDailyNoteConfig, organizeDailyNotes } from '../../api.js';
  import { countUnorganizedDailyNotes } from '../dailyNote.js';
  import { showToast } from '../toast.js';

  let {
    open = $bindable(false),
    onconfigured = () => {},
  } = $props();

  let projects = $state([]);
  let selectedProjectId = $state('');
  let selectedTemplateId = $state('');
  let organizeExisting = $state(true);
  let loading = $state(false);
  let error = $state('');
  let loadingProjects = $state(false);

  // Derived: pages in the selected project, for template picker
  let selectedProject = $derived(
    projects.find((p) => p.external_id === selectedProjectId) || null
  );
  let templatePages = $derived(selectedProject?.pages || []);

  // Derived: count of YYYY-MM-DD pages in the selected project not already in YYYY/MM
  let unorganizedCount = $derived.by(() => {
    if (!selectedProject) return 0;
    return countUnorganizedDailyNotes(
      selectedProject.pages || [],
      selectedProject.folders || [],
    );
  });

  $effect(() => {
    if (open) {
      loadProjects();
    } else {
      // Reset
      selectedProjectId = '';
      selectedTemplateId = '';
      organizeExisting = true;
      error = '';
      loading = false;
    }
  });

  // Reset template when project changes
  let lastProjectId = '';
  $effect(() => {
    if (selectedProjectId !== lastProjectId) {
      lastProjectId = selectedProjectId;
      // Clear template if it's not in the new project
      if (selectedTemplateId && !templatePages.some((p) => p.external_id === selectedTemplateId)) {
        selectedTemplateId = '';
      }
    }
  });

  async function loadProjects() {
    loadingProjects = true;
    try {
      projects = await fetchProjectsWithPages();
      // Prefer a "Daily Notes" project if present
      const daily = projects.find((p) => (p.name || '').toLowerCase() === 'daily notes');
      if (daily) {
        selectedProjectId = daily.external_id;
      } else if (projects.length > 0) {
        selectedProjectId = projects[0].external_id;
      }
    } catch (e) {
      error = 'Failed to load projects';
    } finally {
      loadingProjects = false;
    }
  }

  async function handleSubmit() {
    if (!selectedProjectId) {
      error = 'Please select a project';
      return;
    }
    error = '';
    loading = true;

    try {
      const payload = { project_external_id: selectedProjectId };
      if (selectedTemplateId) {
        payload.template_external_id = selectedTemplateId;
      }
      const config = await updateDailyNoteConfig(payload);

      if (organizeExisting && unorganizedCount > 0) {
        try {
          await organizeDailyNotes(false);
        } catch (e) {
          // Non-fatal: config was saved, organizing just didn't complete
          showToast('Saved, but could not organize existing notes', 'error');
        }
      }

      open = false;
      onconfigured(config);
    } catch (e) {
      error = e.message || 'Failed to save daily-note settings';
    } finally {
      loading = false;
    }
  }

  function handleCancel() {
    open = false;
  }
</script>

<Modal bind:open title="Daily Note Settings" size="sm">
  {#if loadingProjects}
    <p class="loading">Loading projects...</p>
  {:else}
    <div class="modal-field">
      <label for="dn-project">Project</label>
      <div class="select-wrapper">
        <select id="dn-project" bind:value={selectedProjectId} disabled={loading}>
          {#each projects as project (project.external_id)}
            <option value={project.external_id}>
              {project.name}{project.org?.name ? ` (${project.org.name})` : ''}
            </option>
          {/each}
        </select>
        <svg class="select-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M6 9l6 6 6-6" />
        </svg>
      </div>
      <p class="field-hint">Where your daily notes will be stored.</p>
    </div>

    <div class="modal-field">
      <label for="dn-template">Template (optional)</label>
      <div class="select-wrapper">
        <select id="dn-template" bind:value={selectedTemplateId} disabled={loading || !selectedProjectId}>
          <option value="">None (blank note)</option>
          {#each templatePages as page (page.external_id)}
            <option value={page.external_id}>{page.title}</option>
          {/each}
        </select>
        <svg class="select-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M6 9l6 6 6-6" />
        </svg>
      </div>
      <p class="field-hint">New daily notes will be seeded from this page's content.</p>
    </div>

    {#if unorganizedCount > 0}
      <div class="modal-field">
        <label class="checkbox-label">
          <input type="checkbox" bind:checked={organizeExisting} disabled={loading} />
          <span>Organize {unorganizedCount} existing {unorganizedCount === 1 ? 'note' : 'notes'} into year/month folders</span>
        </label>
      </div>
    {/if}
  {/if}

  {#if error}
    <div class="modal-error-message">{error}</div>
  {/if}

  {#snippet footer()}
    <button class="modal-btn-secondary" onclick={handleCancel} disabled={loading}>
      Cancel
    </button>
    <button
      class="modal-btn-primary"
      onclick={handleSubmit}
      disabled={loading || loadingProjects || !selectedProjectId}
    >
      {loading ? 'Saving...' : 'Save'}
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

  .modal-field select {
    width: 100%;
    padding: 0.625rem 0.75rem;
    border: 1px solid var(--border-light);
    border-radius: 6px;
    font-size: 0.9rem;
    background: var(--bg-primary);
    color: var(--text-primary);
    appearance: none;
    padding-right: 2.5rem;
    cursor: pointer;
  }

  .select-wrapper {
    position: relative;
  }

  .select-chevron {
    position: absolute;
    right: 0.75rem;
    top: 50%;
    transform: translateY(-50%);
    width: 16px;
    height: 16px;
    color: var(--text-secondary);
    pointer-events: none;
  }

  .modal-field select:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .field-hint {
    font-size: 0.8rem;
    color: var(--text-secondary);
    margin: 0.375rem 0 0 0;
    line-height: 1.4;
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

  .modal-error-message {
    padding: 0.625rem 0.75rem;
    background: #fef2f2;
    border: 1px solid #fecaca;
    border-radius: 6px;
    color: #dc2626;
    font-size: 0.875rem;
    margin-top: 0.5rem;
  }

  .loading {
    color: var(--text-secondary);
    font-size: 0.875rem;
  }
</style>
