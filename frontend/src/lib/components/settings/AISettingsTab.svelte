<script>
  import { onMount } from "svelte";
  import { API_BASE_URL } from "../../../config.js";
  import { csrfFetch } from "../../../csrf.js";
  import { showToast } from "../../toast.js";
  import { prompt, confirm } from "../../modal.js";
  import ProviderCard from "./ProviderCard.svelte";
  import UsageChart from "./UsageChart.svelte";
  import CustomProviderWizard from "./CustomProviderWizard.svelte";
  import IndexDataPrompt from "../IndexDataPrompt.svelte";

  let { orgs = [], userRole = "member" } = $props();

  let wizardOpen = $state(false);

  const BUILTIN_PROVIDERS = [
    { provider: "openai", name: "OpenAI", description: "GPT-5.2, GPT-4.1, and other OpenAI models" },
    { provider: "anthropic", name: "Anthropic", description: "Claude Opus 4.5, Sonnet, and other Anthropic models" },
    { provider: "google", name: "Google Gemini", description: "Gemini 3 Pro, 2.5 Flash, and other Google models" },
  ];

  let scope = $state("user");
  let selectedOrgId = $state(null);
  let configs = $state([]);
  let orgProviderSummary = $state([]);
  let usage = $state(null);
  let loading = $state(true);

  const memberOrgs = $derived(orgs);
  const hasMemberOrgs = $derived(memberOrgs.length > 0);
  const selectedOrg = $derived(memberOrgs.find((o) => o.external_id === selectedOrgId));
  const isAdminOfSelectedOrg = $derived(selectedOrg?.userRole === "admin");

  onMount(() => {
    loadConfigs();
  });

  $effect(() => {
    if (scope === "org" && memberOrgs.length > 0 && !selectedOrgId) {
      selectedOrgId = memberOrgs[0].external_id;
    }
  });

  $effect(() => {
    loadConfigs();
    loadUsage();
  });

  async function loadConfigs() {
    loading = true;
    configs = [];
    orgProviderSummary = [];

    try {
      if (scope === "user") {
        const response = await fetch(`${API_BASE_URL}/api/ai/providers/`, { credentials: "same-origin" });
        if (response.ok) {
          configs = await response.json();
        }
      } else if (scope === "org" && selectedOrgId) {
        const org = memberOrgs.find((o) => o.external_id === selectedOrgId);
        if (org?.userRole === "admin") {
          const response = await fetch(`${API_BASE_URL}/api/ai/orgs/${selectedOrgId}/providers/`, {
            credentials: "same-origin",
          });
          if (response.ok) {
            configs = await response.json();
          }
        } else {
          const response = await fetch(`${API_BASE_URL}/api/ai/orgs/${selectedOrgId}/providers/summary/`, {
            credentials: "same-origin",
          });
          if (response.ok) {
            orgProviderSummary = await response.json();
          }
        }
      }
    } catch (error) {
      console.error("Failed to load AI configs:", error);
    }
    loading = false;
  }

  async function loadUsage() {
    usage = null;

    if (scope === "org" && selectedOrgId) {
      const org = memberOrgs.find((o) => o.external_id === selectedOrgId);
      if (org?.userRole !== "admin") {
        return;
      }
    }

    try {
      const tzOffset = new Date().getTimezoneOffset();
      const endpoint =
        scope === "user"
          ? `${API_BASE_URL}/api/ai/usage/?tz_offset=${tzOffset}`
          : `${API_BASE_URL}/api/ai/orgs/${selectedOrgId}/usage/?tz_offset=${tzOffset}`;
      const response = await fetch(endpoint, { credentials: "same-origin" });
      if (response.ok) {
        usage = await response.json();
      }
    } catch (error) {
      console.error("Failed to load usage:", error);
    }
  }

  function getConfigForProvider(provider) {
    return configs.find((c) => c.provider === provider);
  }

  function getCustomConfigs() {
    return configs.filter((c) => c.provider === "custom");
  }

  async function saveConfig(provider, data) {
    const existingConfig = getConfigForProvider(provider);
    const endpoint =
      scope === "user"
        ? `${API_BASE_URL}/api/ai/providers/`
        : `${API_BASE_URL}/api/ai/orgs/${selectedOrgId}/providers/`;

    try {
      let response;
      if (existingConfig) {
        response = await csrfFetch(`${endpoint}${existingConfig.external_id}/`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
        });
      } else {
        response = await csrfFetch(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ provider, ...data }),
        });
      }

      const result = await response.json();
      if (response.ok || response.status === 201) {
        showToast("Configuration saved");
        await loadConfigs();
        return { success: true, config: result };
      } else {
        return { success: false, error: result.message || "Failed to save", config: result.config };
      }
    } catch (error) {
      return { success: false, error: "Network error" };
    }
  }

  async function deleteConfig(configId) {
    const endpoint =
      scope === "user"
        ? `${API_BASE_URL}/api/ai/providers/${configId}/`
        : `${API_BASE_URL}/api/ai/orgs/${selectedOrgId}/providers/${configId}/`;

    try {
      const response = await csrfFetch(endpoint, { method: "DELETE" });
      if (response.ok || response.status === 204) {
        showToast("Configuration deleted");
        await loadConfigs();
      }
    } catch (error) {
      showToast("Failed to delete configuration", "error");
    }
  }

  async function validateConfig(configId) {
    const endpoint =
      scope === "user"
        ? `${API_BASE_URL}/api/ai/providers/${configId}/validate/`
        : `${API_BASE_URL}/api/ai/orgs/${selectedOrgId}/providers/${configId}/validate/`;

    try {
      const response = await csrfFetch(endpoint, { method: "POST" });
      const result = await response.json();
      if (result.is_valid) {
        showToast("API key validated successfully");
      } else {
        showToast(`Validation failed: ${result.error}`, "error");
      }
      await loadConfigs();
      return result;
    } catch (error) {
      showToast("Validation request failed", "error");
      return { is_valid: false, error: "Network error" };
    }
  }

  function openCustomProviderWizard() {
    wizardOpen = true;
  }

  async function saveCustomProvider(data) {
    const endpoint =
      scope === "user"
        ? `${API_BASE_URL}/api/ai/providers/`
        : `${API_BASE_URL}/api/ai/orgs/${selectedOrgId}/providers/`;

    try {
      const response = await csrfFetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });

      if (response.ok || response.status === 201) {
        showToast("Custom provider added");
        await loadConfigs();
        return { success: true };
      } else {
        const result = await response.json();
        return { success: false, error: result.message || "Failed to add provider" };
      }
    } catch (error) {
      return { success: false, error: "Network error" };
    }
  }
</script>

<div class="ai-settings">
  {#if hasMemberOrgs}
    <div class="scope-tabs">
      <button class="scope-tab" class:active={scope === "user"} onclick={() => (scope = "user")}>
        Personal
      </button>
      <button class="scope-tab" class:active={scope === "org"} onclick={() => (scope = "org")}>
        Organizations
      </button>
    </div>

    {#if scope === "org"}
      <div class="org-selector">
        <label for="org-select">Organization</label>
        <select id="org-select" bind:value={selectedOrgId} onchange={loadConfigs}>
          {#each memberOrgs as org}
            <option value={org.external_id}>{org.name}</option>
          {/each}
        </select>
      </div>
    {/if}
  {/if}

  <p class="settings-tab-intro">
    {#if scope === "user"}
      Configure your personal AI provider API keys. These override organization keys when set.
    {:else if isAdminOfSelectedOrg}
      Configure AI provider API keys for your organization. Members can use these keys for AI features but cannot view or retrieve the actual key values.
    {:else}
      Organization AI providers are managed by admins. As a member, you can use any enabled provider.
    {/if}
  </p>

  {#if scope === "user"}
    <IndexDataPrompt />
  {/if}

  {#if loading}
    <div class="loading-message">Loading...</div>
  {:else if scope === "org" && !isAdminOfSelectedOrg}
    <!-- Read-only view for non-admin org members -->
    <section class="providers-section">
      <h3 class="settings-subsection-title">Available AI Providers</h3>

      {#if orgProviderSummary.length === 0}
        <p class="no-providers-message">No AI providers have been configured for this organization yet.</p>
      {:else}
        <div class="provider-summary-list">
          {#each orgProviderSummary as provider}
            <div class="provider-summary-item">
              <div class="provider-summary-info">
                <span class="provider-summary-name">
                  {provider.display_name || BUILTIN_PROVIDERS.find((p) => p.provider === provider.provider)?.name || provider.provider}
                </span>
              </div>
              <div class="provider-summary-status">
                {#if provider.is_enabled && provider.is_validated}
                  <span class="status-badge status-active">Available</span>
                {:else if provider.is_enabled && !provider.is_validated}
                  <span class="status-badge status-pending">Pending Validation</span>
                {:else}
                  <span class="status-badge status-disabled">Disabled</span>
                {/if}
              </div>
            </div>
          {/each}
        </div>
      {/if}
    </section>
  {:else}
    <!-- Full edit view for personal or admin org -->
    <section class="providers-section">
      <h3 class="settings-subsection-title">AI Providers</h3>

      {#each BUILTIN_PROVIDERS as { provider, name, description }}
        <ProviderCard
          {provider}
          {name}
          {description}
          config={getConfigForProvider(provider)}
          onSave={(data) => saveConfig(provider, data)}
          onValidate={(configId) => validateConfig(configId)}
        />
      {/each}

      <div class="custom-providers-section">
        <h4 class="custom-providers-title">Custom Providers</h4>
        <p class="custom-providers-desc">Add OpenAI-compatible endpoints like Azure, Ollama, or local LLMs.</p>

        {#each getCustomConfigs() as config}
          <ProviderCard
            provider="custom"
            name={config.display_name}
            description={config.api_base_url}
            {config}
            isCustom={true}
            onSave={(data) => saveConfig("custom", { ...data, external_id: config.external_id })}
            onValidate={(configId) => validateConfig(configId)}
            onDelete={() => deleteConfig(config.external_id)}
          />
        {/each}

        <button class="add-custom-btn" onclick={openCustomProviderWizard}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="12" y1="5" x2="12" y2="19"></line>
            <line x1="5" y1="12" x2="19" y2="12"></line>
          </svg>
          Add Custom Provider
        </button>
      </div>
    </section>

    {#if usage}
      <section class="usage-section">
        <h3 class="settings-subsection-title">
          {scope === "user" ? "Your Usage" : "Organization Usage"}
        </h3>
        <UsageChart {usage} />
      </section>
    {/if}
  {/if}
</div>

<CustomProviderWizard bind:open={wizardOpen} onSave={saveCustomProvider} />

<style>
  .ai-settings {
    max-width: 100%;
  }

  .scope-tabs {
    display: flex;
    gap: 0;
    margin-bottom: 1.5rem;
    border-bottom: 1px solid var(--border-light);
  }

  .scope-tab {
    padding: 0.75rem 1.25rem;
    border: none;
    background: transparent;
    color: var(--text-secondary);
    font-size: 0.9rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s;
    position: relative;
  }

  .scope-tab:hover {
    color: var(--text-primary);
  }

  .scope-tab.active {
    color: #667eea;
  }

  .scope-tab.active::after {
    content: "";
    position: absolute;
    bottom: -1px;
    left: 0;
    right: 0;
    height: 2px;
    background: #667eea;
  }

  .org-selector {
    margin-bottom: 1rem;
  }

  .org-selector label {
    display: block;
    font-size: 0.8rem;
    font-weight: 500;
    color: var(--text-secondary);
    margin-bottom: 0.5rem;
  }

  .org-selector select {
    padding: 0.5rem 0.75rem;
    border: 1px solid var(--border-light);
    border-radius: 6px;
    background: var(--bg-primary);
    color: var(--text-primary);
    font-size: 0.9rem;
    min-width: 200px;
  }

  .providers-section {
    background: var(--bg-primary);
    border-radius: 8px;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
    box-shadow: 0 0 0 1px var(--border-light);
  }

  .custom-providers-section {
    margin-top: 1.5rem;
    padding-top: 1.5rem;
    border-top: 1px solid var(--border-light);
  }

  .custom-providers-title {
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0 0 0.25rem 0;
  }

  .custom-providers-desc {
    font-size: 0.85rem;
    color: var(--text-secondary);
    margin: 0 0 1rem 0;
  }

  .add-custom-btn {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.75rem 1rem;
    border: 1px dashed var(--border-light);
    border-radius: 8px;
    background: transparent;
    color: var(--text-secondary);
    font-size: 0.875rem;
    cursor: pointer;
    transition: all 0.15s;
    width: 100%;
    justify-content: center;
  }

  .add-custom-btn:hover {
    border-color: #667eea;
    color: #667eea;
    background: rgba(102, 126, 234, 0.05);
  }

  .usage-section {
    background: var(--bg-primary);
    border-radius: 8px;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
    box-shadow: 0 0 0 1px var(--border-light);
  }

  .loading-message {
    text-align: center;
    padding: 2rem;
    color: var(--text-secondary);
  }

  .no-providers-message {
    color: var(--text-secondary);
    font-size: 0.9rem;
    text-align: center;
    padding: 2rem;
  }

  .provider-summary-list {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .provider-summary-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem;
    background: var(--bg-secondary);
    border-radius: 8px;
    border: 1px solid var(--border-light);
  }

  .provider-summary-info {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .provider-summary-name {
    font-weight: 500;
    color: var(--text-primary);
  }

  .provider-summary-type {
    font-size: 0.75rem;
    color: var(--text-secondary);
    background: var(--bg-tertiary);
    padding: 0.2rem 0.5rem;
    border-radius: 4px;
    text-transform: capitalize;
  }

  .status-badge {
    font-size: 0.75rem;
    font-weight: 500;
    padding: 0.3rem 0.6rem;
    border-radius: 12px;
  }

  .status-active {
    background: rgba(16, 185, 129, 0.1);
    color: #10b981;
  }

  .status-pending {
    background: rgba(245, 158, 11, 0.1);
    color: #f59e0b;
  }

  .status-disabled {
    background: rgba(107, 114, 128, 0.1);
    color: #6b7280;
  }
</style>
