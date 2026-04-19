<script>
  import { onMount } from 'svelte';
  import { getDailyNoteConfig } from '../../../api.js';
  import { showToast } from '../../toast.js';
  import { openDailyNoteWizard } from '../../dailyNote.js';

  let loading = $state(true);
  let config = $state({ project: null, template: null });

  onMount(async () => {
    await reload();
  });

  async function reload() {
    loading = true;
    try {
      config = await getDailyNoteConfig();
    } catch (e) {
      showToast('Failed to load daily-note settings', 'error');
    } finally {
      loading = false;
    }
  }

  function handleChange() {
    openDailyNoteWizard({
      onconfigured: async () => {
        await reload();
        showToast('Daily note settings updated');
      },
    });
  }
</script>

<section class="settings-section">
  <h3 class="settings-subsection-title">Daily Notes</h3>
  <p class="settings-tab-intro">
    One-click access to today's note, auto-filed into year/month folders.
  </p>

  {#if loading}
    <div class="loading">Loading...</div>
  {:else}
    <button type="button" class="dn-card" onclick={handleChange}>
      <div class="dn-rows">
        <div class="dn-row">
          <div class="dn-label">Project</div>
          <div class="dn-value" class:dn-value-empty={!config.project}>
            {config.project ? config.project.name : 'Not configured'}
          </div>
        </div>

        {#if config.project}
          <div class="dn-row">
            <div class="dn-label">Template</div>
            <div class="dn-value" class:dn-value-empty={!config.template}>
              {config.template ? config.template.title : 'None (blank note)'}
            </div>
          </div>
        {/if}
      </div>

      <svg class="dn-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M9 6l6 6-6 6" />
      </svg>
    </button>
  {/if}
</section>

<style>
  .loading {
    color: var(--text-secondary);
    font-size: 0.875rem;
    padding: 0.5rem 0;
  }

  .dn-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    width: 100%;
    margin-top: 1rem;
    padding: 0.875rem 1rem;
    background: var(--bg-primary);
    border: 1px solid var(--border-light);
    border-radius: 8px;
    text-align: left;
    cursor: pointer;
    transition: border-color 0.15s, background-color 0.15s;
  }

  .dn-card:hover {
    border-color: var(--border-color);
    background: var(--bg-tertiary, #fafafa);
  }

  .dn-rows {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    min-width: 0;
    flex: 1;
  }

  .dn-row {
    display: grid;
    grid-template-columns: 5.5rem 1fr;
    align-items: baseline;
    gap: 0.75rem;
    min-width: 0;
  }

  .dn-label {
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }

  .dn-value {
    font-size: 0.95rem;
    color: var(--text-primary);
    min-width: 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .dn-value-empty {
    color: var(--text-tertiary);
    font-style: italic;
  }

  .dn-chevron {
    flex-shrink: 0;
    width: 18px;
    height: 18px;
    color: var(--text-tertiary);
  }

  .dn-card:hover .dn-chevron {
    color: var(--text-secondary);
  }
</style>
