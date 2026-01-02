<script>
  import { showToast } from "../../toast.js";
  import { confirm } from "../../modal.js";

  let {
    provider,
    name,
    description,
    config = null,
    isCustom = false,
    onSave,
    onValidate,
    onDelete = null,
  } = $props();

  let apiKey = $state("");
  let apiBaseUrl = $state("");
  let modelName = $state("");
  let isEnabled = $state(false);
  let isDefault = $state(false);
  let saving = $state(false);
  let validating = $state(false);
  let expanded = $state(false);
  let keyModified = $state(false);

  const hasKey = $derived(config?.has_key ?? false);
  const isValidated = $derived(config?.is_validated ?? false);
  const keyHint = $derived(config?.key_hint || null);
  const canBeEnabled = $derived(hasKey && isValidated);

  $effect(() => {
    if (config) {
      apiBaseUrl = config.api_base_url || "";
      modelName = config.model_name || "";
      isEnabled = canBeEnabled && (config.is_enabled ?? false);
      isDefault = config.is_default ?? false;
    } else {
      isEnabled = false;
    }
  });

  async function handleSave() {
    saving = true;
    const data = {
      is_enabled: isEnabled,
      is_default: isDefault,
    };

    const savingNewKey = !!apiKey;
    if (apiKey) {
      data.api_key = apiKey;
    }

    if (isCustom) {
      if (apiBaseUrl) data.api_base_url = apiBaseUrl;
      if (modelName) data.model_name = modelName;
    }

    const result = await onSave(data);
    saving = false;

    if (result.success) {
      apiKey = "";
      keyModified = false;

      if (savingNewKey && result.config?.is_validated && !result.config?.is_enabled) {
        const shouldEnable = await confirm({
          title: "Enable Provider?",
          message: `Your ${name} API key has been validated successfully.`,
          description: "Would you like to enable this provider now so you can use it for AI features?",
          confirmText: "Enable",
          cancelText: "Keep Disabled",
        });

        if (shouldEnable) {
          isEnabled = true;
          await onSave({ is_enabled: true });
        }
      }
    } else {
      showToast(result.error, "error");
    }
  }

  async function handleValidate() {
    if (!config?.external_id) return;
    validating = true;
    await onValidate(config.external_id);
    validating = false;
  }

  function toggleExpanded() {
    expanded = !expanded;
  }

  function handleHeaderKeydown(e) {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      toggleExpanded();
    }
  }

  function handleToggleClick(e) {
    e.stopPropagation();
  }
</script>

<div class="provider-card" class:expanded class:has-config={!!config}>
  <div
    class="provider-header"
    role="button"
    tabindex="0"
    onclick={toggleExpanded}
    onkeydown={handleHeaderKeydown}
  >
    <div class="provider-info">
      <div class="provider-name-row">
        <span class="provider-name">{name}</span>
        {#if isDefault && canBeEnabled}
          <span class="default-badge">Default</span>
        {/if}
        {#if hasKey}
          {#if isValidated}
            <span class="status-badge validated">Validated</span>
          {:else}
            <span class="status-badge pending">Pending</span>
          {/if}
        {:else}
          <span class="status-badge not-configured">Not configured</span>
        {/if}
      </div>
      <span class="provider-description">{description}</span>
    </div>
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="provider-actions" onclick={handleToggleClick} onkeydown={(e) => e.stopPropagation()}>
      <label class="toggle-switch" class:disabled={!canBeEnabled} title={!canBeEnabled ? "Add a valid API key to enable" : ""}>
        <input type="checkbox" bind:checked={isEnabled} onchange={handleSave} disabled={!canBeEnabled} />
        <span class="toggle-slider"></span>
      </label>
      <button class="expand-btn" class:expanded aria-label={expanded ? "Collapse" : "Expand"} onclick={toggleExpanded}>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="6 9 12 15 18 9"></polyline>
        </svg>
      </button>
    </div>
  </div>

  {#if expanded}
    <div class="provider-body">
      <div class="field-group">
        <label for="{provider}-key">API Key</label>
        <input type="text" style="display:none" aria-hidden="true" />
        <input type="password" style="display:none" aria-hidden="true" />
        <div class="key-input-group">
          <input
            id="{provider}-key"
            type="password"
            bind:value={apiKey}
            oninput={() => keyModified = apiKey.length > 0}
            placeholder="Enter new API key..."
            autocomplete="new-password"
            data-1p-ignore
            data-lpignore="true"
            data-form-type="other"
          />
          <button class={keyModified ? "btn-primary" : "btn-secondary"} onclick={handleSave} disabled={saving}>
            {saving ? "Saving..." : "Save"}
          </button>
        </div>
        {#if keyHint}
          <span class="key-hint">Current: {keyHint}</span>
        {/if}
      </div>

      {#if isCustom}
        <div class="field-group">
          <label for="{provider}-base-url">API Base URL</label>
          <input
            id="{provider}-base-url"
            type="url"
            bind:value={apiBaseUrl}
            placeholder="https://api.example.com/v1"
          />
        </div>

        <div class="field-group">
          <label for="{provider}-model">Model Name (optional)</label>
          <input
            id="{provider}-model"
            type="text"
            bind:value={modelName}
            placeholder="gpt-5.2, llama-3, etc."
          />
        </div>
      {/if}

      <div class="card-footer">
        <div class="footer-left">
          <label class="checkbox-label">
            <input type="checkbox" bind:checked={isDefault} onchange={handleSave} />
            Set as default
          </label>
        </div>
        <div class="footer-right">
          {#if hasKey}
            <button class="btn-link" onclick={handleValidate} disabled={validating}>
              {validating ? "Validating..." : "Re-validate"}
            </button>
          {/if}
          {#if isCustom && onDelete}
            <button class="btn-danger-link" onclick={onDelete}>Delete</button>
          {/if}
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
  .provider-card {
    border: 1px solid var(--border-light);
    border-radius: 8px;
    margin-bottom: 0.75rem;
    overflow: hidden;
    transition: box-shadow 0.15s;
  }

  .provider-card:hover {
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  }

  .provider-card.has-config {
    border-color: rgba(102, 126, 234, 0.3);
  }

  .provider-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1rem;
    cursor: pointer;
    user-select: none;
  }

  .provider-header:hover {
    background: rgba(0, 0, 0, 0.02);
  }

  .provider-info {
    flex: 1;
  }

  .provider-name-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.25rem;
  }

  .provider-name {
    font-weight: 600;
    color: var(--text-primary);
  }

  .provider-description {
    font-size: 0.85rem;
    color: var(--text-secondary);
  }

  .default-badge {
    font-size: 0.7rem;
    font-weight: 500;
    padding: 0.15rem 0.5rem;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border-radius: 100px;
  }

  .status-badge {
    font-size: 0.7rem;
    font-weight: 500;
    padding: 0.15rem 0.5rem;
    border-radius: 100px;
  }

  .status-badge.validated {
    background: rgba(52, 211, 153, 0.15);
    color: #059669;
  }

  .status-badge.pending {
    background: rgba(251, 191, 36, 0.15);
    color: #b45309;
  }

  .status-badge.not-configured {
    background: rgba(107, 114, 128, 0.1);
    color: #6b7280;
  }

  .provider-actions {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .toggle-switch {
    position: relative;
    display: inline-block;
    width: 40px;
    height: 22px;
  }

  .toggle-switch input {
    opacity: 0;
    width: 0;
    height: 0;
  }

  .toggle-slider {
    position: absolute;
    cursor: pointer;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: #ccc;
    transition: 0.2s;
    border-radius: 22px;
  }

  .toggle-slider:before {
    position: absolute;
    content: "";
    height: 16px;
    width: 16px;
    left: 3px;
    bottom: 3px;
    background-color: white;
    transition: 0.2s;
    border-radius: 50%;
  }

  .toggle-switch input:checked + .toggle-slider {
    background: #667eea;
  }

  .toggle-switch input:checked + .toggle-slider:before {
    transform: translateX(18px);
  }

  .toggle-switch.disabled {
    opacity: 0.5;
    cursor: pointer;
  }

  .toggle-switch.disabled .toggle-slider {
    cursor: pointer;
  }

  .expand-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border: none;
    background: transparent;
    color: var(--text-secondary);
    cursor: pointer;
    border-radius: 4px;
    transition: all 0.15s;
  }

  .expand-btn:hover {
    background: rgba(0, 0, 0, 0.05);
  }

  .expand-btn.expanded svg {
    transform: rotate(180deg);
  }

  .provider-body {
    padding: 0 1rem 1rem 1rem;
    border-top: 1px solid var(--border-light);
    background: rgba(0, 0, 0, 0.01);
  }

  .field-group {
    margin-top: 1rem;
  }

  .field-group label {
    display: block;
    font-size: 0.8rem;
    font-weight: 500;
    color: var(--text-secondary);
    margin-bottom: 0.5rem;
  }

  .field-group input {
    width: 100%;
    padding: 0.6rem 0.75rem;
    border: 1px solid var(--border-light);
    border-radius: 6px;
    font-size: 0.9rem;
    color: var(--text-primary);
    background: var(--bg-primary);
  }

  .field-group input:focus {
    outline: none;
    border-color: #667eea;
    box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
  }

  .key-input-group {
    display: flex;
    gap: 0.5rem;
  }

  .key-input-group input {
    flex: 1;
  }

  .key-hint {
    display: block;
    font-size: 0.75rem;
    color: var(--text-secondary);
    margin-top: 0.25rem;
  }

  .btn-secondary {
    padding: 0.6rem 1rem;
    border: 1px solid var(--border-light);
    border-radius: 6px;
    background: var(--bg-primary);
    color: var(--text-primary);
    font-size: 0.875rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s;
    white-space: nowrap;
  }

  .btn-secondary:hover:not(:disabled) {
    border-color: #667eea;
    color: #667eea;
  }

  .btn-secondary:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-primary {
    padding: 0.6rem 1rem;
    border: none;
    border-radius: 6px;
    background: #667eea;
    color: white;
    font-size: 0.875rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s;
    white-space: nowrap;
  }

  .btn-primary:hover:not(:disabled) {
    background: #5a6fd6;
  }

  .btn-primary:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .card-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 1rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border-light);
  }

  .footer-right {
    display: flex;
    gap: 1rem;
  }

  .checkbox-label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.85rem;
    color: var(--text-secondary);
    cursor: pointer;
  }

  .checkbox-label input {
    width: auto;
  }

  .btn-link {
    background: none;
    border: none;
    color: #667eea;
    font-size: 0.85rem;
    cursor: pointer;
    padding: 0;
  }

  .btn-link:hover:not(:disabled) {
    text-decoration: underline;
  }

  .btn-link:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-danger-link {
    background: none;
    border: none;
    color: #dc2626;
    font-size: 0.85rem;
    cursor: pointer;
    padding: 0;
  }

  .btn-danger-link:hover {
    text-decoration: underline;
  }
</style>
