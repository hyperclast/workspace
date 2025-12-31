<script>
  import Modal from './Modal.svelte';

  let {
    open = $bindable(false),
    projectId = '',
    pages = [],
    oncreated = () => {},
  } = $props();

  let title = $state('');
  let copyFrom = $state('');
  let loading = $state(false);
  let error = $state('');
  let inputEl = $state(null);

  let todayValue = $derived(formatToday());
  let nowValue = $derived(formatNow());
  let humanDateValue = $derived(formatHumanDate());

  function formatToday() {
    return new Date().toISOString().split('T')[0];
  }

  function formatNow() {
    const d = new Date();
    const date = d.toISOString().split('T')[0];
    const hours = d.getHours();
    const mins = String(d.getMinutes()).padStart(2, '0');
    const ampm = hours >= 12 ? 'pm' : 'am';
    const h = hours % 12 || 12;
    return `${date} ${h}h${mins}${ampm}`;
  }

  function formatHumanDate() {
    const d = new Date();
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return `${months[d.getMonth()]} ${d.getDate()}, ${d.getFullYear()}`;
  }

  function getStoredTitleFormat() {
    return localStorage.getItem('newPageTitleFormat') || 'now';
  }

  function setStoredTitleFormat(format) {
    localStorage.setItem('newPageTitleFormat', format);
  }

  function getStoredCopyFrom(projectId) {
    try {
      const prefs = JSON.parse(localStorage.getItem('copyFromPrefs') || '{}');
      return prefs[projectId] || '';
    } catch {
      return '';
    }
  }

  function setStoredCopyFrom(projectId, pageId) {
    try {
      const prefs = JSON.parse(localStorage.getItem('copyFromPrefs') || '{}');
      prefs[projectId] = pageId;
      localStorage.setItem('copyFromPrefs', JSON.stringify(prefs));
    } catch {
      // ignore
    }
  }

  $effect(() => {
    if (open) {
      const format = getStoredTitleFormat();
      if (format === 'today') {
        title = formatToday();
      } else if (format === 'human') {
        title = formatHumanDate();
      } else {
        title = formatNow();
      }
      copyFrom = getStoredCopyFrom(projectId);
      error = '';
      loading = false;
      setTimeout(() => {
        inputEl?.focus();
        inputEl?.select();
      }, 50);
    }
  });

  function handleTodayClick(e) {
    e.preventDefault();
    title = formatToday();
    setStoredTitleFormat('today');
    inputEl?.focus();
    inputEl?.select();
  }

  function handleNowClick(e) {
    e.preventDefault();
    title = formatNow();
    setStoredTitleFormat('now');
    inputEl?.focus();
    inputEl?.select();
  }

  function handleHumanDateClick(e) {
    e.preventDefault();
    title = formatHumanDate();
    setStoredTitleFormat('human');
    inputEl?.focus();
    inputEl?.select();
  }

  async function handleCreate() {
    const finalTitle = title.trim() || 'Untitled';
    const finalCopyFrom = copyFrom || null;

    error = '';
    loading = true;

    setStoredCopyFrom(projectId, copyFrom);

    try {
      open = false;
      oncreated({ title: finalTitle, copyFrom: finalCopyFrom });
    } catch (e) {
      error = e.message || 'Failed to create page';
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

<Modal bind:open title="New Page" size="sm">
  <div class="modal-field">
    <label for="page-title-input">Title</label>
    <input
      bind:this={inputEl}
      bind:value={title}
      type="text"
      id="page-title-input"
      placeholder="Untitled"
      maxlength="100"
      disabled={loading}
      onkeydown={handleKeydown}
    />
    <div class="title-presets">
      <span class="presets-label">Set:</span>
      <button type="button" class="preset-link" onclick={handleTodayClick}>{todayValue}</button>
      <span class="presets-sep">/</span>
      <button type="button" class="preset-link" onclick={handleNowClick}>{nowValue}</button>
      <span class="presets-sep">/</span>
      <button type="button" class="preset-link" onclick={handleHumanDateClick}>{humanDateValue}</button>
    </div>
  </div>

  {#if pages.length > 0}
    <div class="modal-field copy-from-field">
      <label for="page-copy-from-select">Copy contents from page</label>
      <div class="select-wrapper">
        <select
          bind:value={copyFrom}
          id="page-copy-from-select"
          disabled={loading}
        >
          <option value="">Blank</option>
          {#each pages as page (page.external_id)}
            <option value={page.external_id}>{page.title || 'Untitled'}</option>
          {/each}
        </select>
        <svg class="select-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M6 9l6 6 6-6" />
        </svg>
      </div>
    </div>
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
      onclick={handleCreate}
      disabled={loading}
    >
      {loading ? 'Creating...' : 'Create Page'}
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

  .title-presets {
    margin-top: 0.25rem;
    font-size: 0.75rem;
    color: var(--text-tertiary, #888);
  }

  .presets-label {
    margin-right: 0.25rem;
  }

  .preset-link {
    background: none;
    border: none;
    padding: 0;
    font: inherit;
    cursor: pointer;
    color: var(--text-secondary, #666);
    text-decoration: none;
    transition: color 0.15s;
  }

  .preset-link:hover {
    color: var(--text-primary, #333);
    text-decoration: underline;
  }

  .presets-sep {
    margin: 0 0.375rem;
    color: var(--text-tertiary, #aaa);
  }

  .copy-from-field {
    margin-top: 1.25rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border-light, #eee);
  }

  .copy-from-field label {
    font-weight: 400;
    color: var(--text-secondary, #666);
    font-size: 0.8rem;
  }

  .copy-from-field select {
    font-size: 0.85rem;
    padding: 0.5rem 0.625rem;
    color: var(--text-secondary, #666);
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
    color: var(--text-tertiary, #999);
    pointer-events: none;
  }

  .select-wrapper select:disabled + .select-chevron {
    opacity: 0.5;
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
</style>
