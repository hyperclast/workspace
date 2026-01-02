<script>
  let { open = $bindable(false), onSave } = $props();

  const STEPS = [
    { id: 1, label: "Name" },
    { id: 2, label: "API URL" },
    { id: 3, label: "API Key" },
  ];

  let currentStep = $state(1);
  let providerName = $state("");
  let apiBaseUrl = $state("");
  let apiKey = $state("");
  let error = $state("");
  let saving = $state(false);

  function reset() {
    currentStep = 1;
    providerName = "";
    apiBaseUrl = "";
    apiKey = "";
    error = "";
    saving = false;
  }

  function close() {
    open = false;
    reset();
  }

  function handleBackdropClick(e) {
    if (e.target === e.currentTarget) {
      close();
    }
  }

  function handleKeydown(e) {
    if (e.key === "Escape") {
      close();
    }
  }

  function goBack() {
    error = "";
    if (currentStep > 1) {
      currentStep--;
    }
  }

  function goNext() {
    error = "";
    if (currentStep === 1) {
      if (!providerName.trim()) {
        error = "Provider name is required";
        return;
      }
      currentStep = 2;
    } else if (currentStep === 2) {
      if (!apiBaseUrl.trim()) {
        error = "API Base URL is required";
        return;
      }
      try {
        new URL(apiBaseUrl);
      } catch {
        error = "Please enter a valid URL";
        return;
      }
      currentStep = 3;
    }
  }

  async function handleSubmit() {
    error = "";
    saving = true;

    const result = await onSave({
      provider: "custom",
      display_name: providerName.trim(),
      api_base_url: apiBaseUrl.trim(),
      api_key: apiKey.trim(),
    });

    saving = false;

    if (result.success) {
      close();
    } else {
      error = result.error || "Failed to save provider";
    }
  }

  function handleInputKeydown(e) {
    if (e.key === "Enter") {
      e.preventDefault();
      if (currentStep < 3) {
        goNext();
      } else {
        handleSubmit();
      }
    }
  }
</script>

<svelte:window onkeydown={handleKeydown} />

{#if open}
  <!-- svelte-ignore a11y_no_static_element_interactions a11y_click_events_have_key_events -->
  <div class="wizard-backdrop" onclick={handleBackdropClick}>
    <div class="wizard-modal" role="dialog" aria-modal="true" tabindex="-1">
      <div class="wizard-header">
        <h2>Add Custom AI Provider</h2>
        <button class="close-btn" onclick={close} aria-label="Close">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>

      <div class="progress-bar">
        {#each STEPS as step}
          <div class="progress-step" class:active={currentStep >= step.id} class:current={currentStep === step.id}>
            <div class="step-number">{step.id}</div>
            <span class="step-label">{step.label}</span>
          </div>
          {#if step.id < STEPS.length}
            <div class="progress-connector" class:active={currentStep > step.id}></div>
          {/if}
        {/each}
      </div>

      <div class="wizard-body">
        {#if currentStep === 1}
          <div class="step-content">
            <label for="provider-name">Provider Name</label>
            <!-- svelte-ignore a11y_autofocus -->
            <input
              id="provider-name"
              type="text"
              bind:value={providerName}
              onkeydown={handleInputKeydown}
              placeholder="Local Ollama / DeepSeek / etc"
              autofocus
            />
            <p class="field-hint">Choose a memorable name to identify this provider.</p>
          </div>
        {:else if currentStep === 2}
          <div class="step-content">
            <label for="api-base-url">API Base URL</label>
            <!-- svelte-ignore a11y_autofocus -->
            <input
              id="api-base-url"
              type="url"
              bind:value={apiBaseUrl}
              onkeydown={handleInputKeydown}
              placeholder="https://api.example.com/v1"
              autofocus
            />
            <p class="field-hint">The base URL of your OpenAI-compatible API endpoint.</p>
          </div>
        {:else if currentStep === 3}
          <div class="step-content">
            <label for="api-key">API Key <span class="optional">(optional)</span></label>
            <!-- svelte-ignore a11y_autofocus -->
            <input
              id="api-key"
              type="password"
              bind:value={apiKey}
              onkeydown={handleInputKeydown}
              placeholder="sk-..."
              autocomplete="off"
              data-1p-ignore
              data-lpignore="true"
              autofocus
            />
            <p class="field-hint">Leave empty for local endpoints that don't require authentication.</p>
          </div>
        {/if}

        {#if error}
          <div class="error-message">{error}</div>
        {/if}
      </div>

      <div class="wizard-footer">
        <div class="footer-left">
          {#if currentStep > 1}
            <button class="btn-secondary" onclick={goBack}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="15 18 9 12 15 6"></polyline>
              </svg>
              Back
            </button>
          {:else}
            <button class="btn-secondary" onclick={close}>Cancel</button>
          {/if}
        </div>
        <div class="footer-right">
          {#if currentStep < 3}
            <button class="btn-primary" onclick={goNext}>
              Continue
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="9 18 15 12 9 6"></polyline>
              </svg>
            </button>
          {:else}
            <button class="btn-primary" onclick={handleSubmit} disabled={saving}>
              {saving ? "Saving..." : "Save Provider"}
            </button>
          {/if}
        </div>
      </div>
    </div>
  </div>
{/if}

<style>
  .wizard-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }

  .wizard-modal {
    background: var(--bg-primary);
    border-radius: 12px;
    width: 100%;
    max-width: 480px;
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.2);
  }

  .wizard-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1.25rem 1.5rem;
    border-bottom: 1px solid var(--border-light);
  }

  .wizard-header h2 {
    margin: 0;
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--text-primary);
  }

  .close-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    border: none;
    background: transparent;
    color: var(--text-secondary);
    cursor: pointer;
    border-radius: 6px;
    transition: all 0.15s;
  }

  .close-btn:hover {
    background: rgba(0, 0, 0, 0.05);
    color: var(--text-primary);
  }

  .progress-bar {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 1.5rem 1.5rem 1rem;
    gap: 0;
  }

  .progress-step {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.5rem;
  }

  .step-number {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.8rem;
    font-weight: 600;
    background: var(--bg-secondary);
    color: var(--text-secondary);
    border: 2px solid var(--border-light);
    transition: all 0.2s;
  }

  .progress-step.active .step-number {
    background: #667eea;
    color: white;
    border-color: #667eea;
  }

  .progress-step.current .step-number {
    box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.2);
  }

  .step-label {
    font-size: 0.75rem;
    color: var(--text-secondary);
    font-weight: 500;
  }

  .progress-step.active .step-label {
    color: var(--text-primary);
  }

  .progress-connector {
    width: 48px;
    height: 2px;
    background: var(--border-light);
    margin: 0 0.5rem;
    margin-bottom: 1.5rem;
    transition: background 0.2s;
  }

  .progress-connector.active {
    background: #667eea;
  }

  .wizard-body {
    padding: 1.5rem;
  }

  .step-content label {
    display: block;
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--text-primary);
    margin-bottom: 0.5rem;
  }

  .step-content label .optional {
    font-weight: 400;
    color: var(--text-secondary);
  }

  .step-content input {
    width: 100%;
    padding: 0.75rem 1rem;
    border: 1px solid var(--border-light);
    border-radius: 8px;
    font-size: 0.95rem;
    color: var(--text-primary);
    background: var(--bg-primary);
  }

  .step-content input:focus {
    outline: none;
    border-color: #667eea;
    box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
  }

  .field-hint {
    margin: 0.5rem 0 0;
    font-size: 0.8rem;
    color: var(--text-secondary);
  }

  .error-message {
    margin-top: 1rem;
    padding: 0.75rem 1rem;
    background: rgba(220, 38, 38, 0.1);
    border: 1px solid rgba(220, 38, 38, 0.2);
    border-radius: 8px;
    color: #dc2626;
    font-size: 0.875rem;
  }

  .wizard-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem 1.5rem 1.5rem;
  }

  .btn-secondary {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.625rem 1rem;
    border: 1px solid var(--border-light);
    border-radius: 8px;
    background: var(--bg-primary);
    color: var(--text-primary);
    font-size: 0.875rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s;
  }

  .btn-secondary:hover {
    border-color: var(--text-secondary);
  }

  .btn-primary {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.625rem 1.25rem;
    border: none;
    border-radius: 8px;
    background: #667eea;
    color: white;
    font-size: 0.875rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s;
  }

  .btn-primary:hover:not(:disabled) {
    background: #5a6fd6;
  }

  .btn-primary:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
</style>
