<script>
  import Modal from './Modal.svelte';
  import { startNotionImport, getImportStatus } from '../../api.js';
  import { showToast } from '../toast.js';
  import { closeImport } from '../stores/modal.svelte.js';

  let {
    open = $bindable(false),
    projectId = '',
    projectName = '',
    onimported = () => {},
  } = $props();

  let file = $state(null);
  let loading = $state(false);
  let error = $state('');
  let dragOver = $state(false);
  let importJob = $state(null);
  let fileInputEl = $state(null);

  // Status display
  let statusMessage = $derived.by(() => {
    if (!importJob) return '';
    switch (importJob.status) {
      case 'pending':
        return 'Import queued...';
      case 'processing':
        const progress = importJob.total_pages > 0
          ? `${importJob.pages_imported_count || 0}/${importJob.total_pages}`
          : '';
        return `Processing${progress ? ` (${progress} pages)` : '...'}`;
      case 'completed':
        return `Completed: ${importJob.pages_imported_count || 0} pages imported`;
      case 'failed':
        return `Failed: ${importJob.error_message || 'Unknown error'}`;
      default:
        return '';
    }
  });

  let isProcessing = $derived(importJob && ['pending', 'processing'].includes(importJob.status));
  let isCompleted = $derived(importJob && importJob.status === 'completed');
  let isFailed = $derived(importJob && importJob.status === 'failed');
  // Don't show retry for errors where retrying won't help (e.g., empty or invalid content)
  let canRetry = $derived(isFailed && !importJob?.error_message?.includes('No importable content'));

  // Reset state when modal closes
  $effect(() => {
    if (!open) {
      file = null;
      error = '';
      loading = false;
      dragOver = false;
      importJob = null;
    }
  });

  function handleDragOver(e) {
    e.preventDefault();
    dragOver = true;
  }

  function handleDragLeave(e) {
    e.preventDefault();
    dragOver = false;
  }

  function handleDrop(e) {
    e.preventDefault();
    dragOver = false;
    const droppedFile = e.dataTransfer?.files?.[0];
    if (droppedFile) {
      validateAndSetFile(droppedFile);
    }
  }

  function handleFileSelect(e) {
    const selectedFile = e.target?.files?.[0];
    if (selectedFile) {
      validateAndSetFile(selectedFile);
    }
  }

  function validateAndSetFile(selectedFile) {
    error = '';

    // Check file type
    const validTypes = ['application/zip', 'application/x-zip-compressed'];
    if (!validTypes.includes(selectedFile.type) && !selectedFile.name.endsWith('.zip')) {
      error = 'Please select a zip file';
      return;
    }

    // Check file size (100MB max)
    const maxSize = 100 * 1024 * 1024;
    if (selectedFile.size > maxSize) {
      error = 'File size exceeds 100MB limit';
      return;
    }

    file = selectedFile;
  }

  function handleBrowseClick() {
    fileInputEl?.click();
  }

  function clearFile() {
    file = null;
    error = '';
    if (fileInputEl) {
      fileInputEl.value = '';
    }
  }

  async function pollImportStatus(externalId) {
    const maxAttempts = 120; // 2 minutes with 1s intervals
    let attempts = 0;

    while (attempts < maxAttempts) {
      try {
        const status = await getImportStatus(externalId);
        importJob = status;

        if (status.status === 'completed') {
          showToast(`Import completed: ${status.pages_imported_count} pages imported`);
          onimported(status);
          return;
        }

        if (status.status === 'failed') {
          error = status.error_message || 'Import failed';
          return;
        }

        // Wait 1 second before next poll
        await new Promise(resolve => setTimeout(resolve, 1000));
        attempts++;
      } catch (e) {
        console.error('Error polling import status:', e);
        error = 'Lost connection to import status';
        return;
      }
    }

    error = 'Import timed out. Please check the project for imported pages.';
  }

  async function handleImport() {
    if (!file || !projectId) return;

    error = '';
    loading = true;

    try {
      const response = await startNotionImport(projectId, file);
      // API returns { job: {...}, message: "..." }
      const job = response.job;
      importJob = job;
      loading = false;

      // Start polling for status
      await pollImportStatus(job.external_id);
    } catch (e) {
      error = e.message || 'Failed to start import';
      loading = false;
    }
  }

  function handleCancel() {
    if (isProcessing) {
      // Can't cancel during processing, just close
      showToast('Import is still processing in the background');
    }
    open = false;
    closeImport();
  }

  function handleClose() {
    if (isCompleted) {
      onimported(importJob);
    }
    open = false;
    closeImport();
  }

  function formatFileSize(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }
</script>

<Modal bind:open title="Import from Notion" size="sm" onclose={handleCancel}>
  <div class="import-modal-content">
    <p class="import-description">
      Upload a Notion export zip file to import your pages into "{projectName}".
    </p>

    {#if !importJob}
      <!-- File selection -->
      <input
        bind:this={fileInputEl}
        type="file"
        accept=".zip,application/zip,application/x-zip-compressed"
        onchange={handleFileSelect}
        class="hidden-file-input"
      />

      <!-- svelte-ignore a11y_no_static_element_interactions a11y_click_events_have_key_events -->
      <div
        class="drop-zone"
        class:drag-over={dragOver}
        class:has-file={file}
        ondragover={handleDragOver}
        ondragleave={handleDragLeave}
        ondrop={handleDrop}
        onclick={!file ? handleBrowseClick : undefined}
      >
        {#if file}
          <div class="file-info">
            <div class="file-icon">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 8v13H3V3h13l5 5z"/>
                <path d="M14 3v5h5"/>
              </svg>
            </div>
            <div class="file-details">
              <div class="file-name">{file.name}</div>
              <div class="file-size">{formatFileSize(file.size)}</div>
            </div>
            <button
              type="button"
              class="clear-file-btn"
              onclick={clearFile}
              disabled={loading}
              title="Remove file"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"/>
                <line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>
        {:else}
          <div class="drop-zone-content">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="17 8 12 3 7 8"/>
              <line x1="12" y1="3" x2="12" y2="15"/>
            </svg>
            <span class="drop-zone-text">
              Drop your Notion export here or <button type="button" class="browse-link">browse</button>
            </span>
            <span class="drop-zone-hint">Zip files up to 100MB</span>
          </div>
        {/if}
      </div>

      <div class="import-help">
        <details>
          <summary>How to export from Notion</summary>
          <ol>
            <li>Notion &rsaquo; General &rsaquo; Export</li>
            <li>Click "Export" in "Workspace Content"</li>
            <li>Choose "Markdown &amp; CSV" format</li>
            <li>Download and upload the zip file here</li>
          </ol>
        </details>
      </div>
    {:else}
      <!-- Import progress -->
      <div class="import-progress">
        <div class="progress-icon" class:spinning={isProcessing}>
          {#if isCompleted}
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
              <polyline points="22 4 12 14.01 9 11.01"/>
            </svg>
          {:else if isFailed}
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"/>
              <line x1="15" y1="9" x2="9" y2="15"/>
              <line x1="9" y1="9" x2="15" y2="15"/>
            </svg>
          {:else}
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 2v4"/>
              <path d="M12 18v4"/>
              <path d="M4.93 4.93l2.83 2.83"/>
              <path d="M16.24 16.24l2.83 2.83"/>
              <path d="M2 12h4"/>
              <path d="M18 12h4"/>
              <path d="M4.93 19.07l2.83-2.83"/>
              <path d="M16.24 7.76l2.83-2.83"/>
            </svg>
          {/if}
        </div>
        <div class="progress-status" class:error={isFailed} class:success={isCompleted}>
          {statusMessage}
        </div>
        {#if isProcessing && importJob.total_pages > 0}
          <div class="progress-bar-container">
            <div
              class="progress-bar"
              style="width: {((importJob.pages_imported_count || 0) / importJob.total_pages) * 100}%"
            ></div>
          </div>
        {/if}
      </div>
    {/if}

    {#if error}
      <div class="import-error">{error}</div>
    {/if}
  </div>

  {#snippet footer()}
    {#if isCompleted}
      <button class="modal-btn-primary" onclick={handleClose}>
        Done
      </button>
    {:else if isFailed}
      <button class="modal-btn-secondary" onclick={handleCancel}>
        Close
      </button>
      {#if canRetry}
        <button class="modal-btn-primary" onclick={() => { importJob = null; error = ''; }}>
          Try Again
        </button>
      {/if}
    {:else if isProcessing}
      <button class="modal-btn-secondary" onclick={handleCancel}>
        Close
      </button>
    {:else}
      <button class="modal-btn-secondary" onclick={handleCancel} disabled={loading}>
        Cancel
      </button>
      <button
        class="modal-btn-primary"
        onclick={handleImport}
        disabled={loading || !file}
      >
        {loading ? 'Starting...' : 'Import'}
      </button>
    {/if}
  {/snippet}
</Modal>

<style>
  .import-modal-content {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .import-description {
    font-size: 0.875rem;
    color: var(--text-secondary, #666);
    margin: 0;
  }

  .hidden-file-input {
    display: none;
  }

  .drop-zone {
    border: 2px dashed var(--border-light, #e0e0e0);
    border-radius: 8px;
    padding: 1.5rem;
    text-align: center;
    cursor: pointer;
    transition: border-color 0.15s, background-color 0.15s;
  }

  .drop-zone:hover,
  .drop-zone.drag-over {
    border-color: #2383e2;
    background-color: rgba(35, 131, 226, 0.05);
  }

  .drop-zone.has-file {
    cursor: default;
    border-style: solid;
    background-color: var(--bg-secondary, #f5f5f5);
  }

  .drop-zone-content {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.5rem;
    color: var(--text-secondary, #666);
  }

  .drop-zone-content svg {
    opacity: 0.5;
  }

  .drop-zone-text {
    font-size: 0.875rem;
  }

  .browse-link {
    background: none;
    border: none;
    color: #2383e2;
    cursor: pointer;
    padding: 0;
    font-size: inherit;
    text-decoration: underline;
  }

  .browse-link:hover {
    color: #1a6dc2;
  }

  .drop-zone-hint {
    font-size: 0.75rem;
    color: var(--text-tertiary, #999);
  }

  .file-info {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    text-align: left;
  }

  .file-icon {
    flex-shrink: 0;
    color: var(--text-secondary, #666);
  }

  .file-details {
    flex: 1;
    min-width: 0;
  }

  .file-name {
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .file-size {
    font-size: 0.75rem;
    color: var(--text-secondary, #666);
  }

  .clear-file-btn {
    flex-shrink: 0;
    background: none;
    border: none;
    color: var(--text-secondary, #666);
    cursor: pointer;
    padding: 0.25rem;
    border-radius: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .clear-file-btn:hover {
    background-color: rgba(0, 0, 0, 0.05);
    color: var(--text-primary);
  }

  .clear-file-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .import-help {
    font-size: 0.8rem;
  }

  .import-help details {
    color: var(--text-secondary, #666);
  }

  .import-help summary {
    cursor: pointer;
    color: #2383e2;
  }

  .import-help summary:hover {
    text-decoration: underline;
  }

  .import-help ol {
    margin: 0.5rem 0 0;
    padding-left: 1.25rem;
    line-height: 1.6;
  }

  .import-progress {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1rem;
    padding: 1.5rem;
    background-color: var(--bg-secondary, #f5f5f5);
    border-radius: 8px;
  }

  .progress-icon {
    color: var(--text-secondary, #666);
  }

  .progress-icon.spinning svg {
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    from {
      transform: rotate(0deg);
    }
    to {
      transform: rotate(360deg);
    }
  }

  .progress-status {
    font-size: 0.875rem;
    color: var(--text-primary);
    text-align: center;
  }

  .progress-status.error {
    color: #dc2626;
  }

  .progress-status.success {
    color: #16a34a;
  }

  .progress-bar-container {
    width: 100%;
    height: 4px;
    background-color: var(--border-light, #e0e0e0);
    border-radius: 2px;
    overflow: hidden;
  }

  .progress-bar {
    height: 100%;
    background-color: #2383e2;
    transition: width 0.3s ease;
  }

  .import-error {
    padding: 0.625rem 0.75rem;
    background: #fef2f2;
    border: 1px solid #fecaca;
    border-radius: 6px;
    color: #dc2626;
    font-size: 0.875rem;
  }
</style>
