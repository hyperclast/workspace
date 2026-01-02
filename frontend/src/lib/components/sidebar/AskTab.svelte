<script>
  import { onMount, onDestroy } from "svelte";
  import { askQuestion, AskError, autocompletePages, fetchAvailableProviders, fetchProviderModels } from "../../../ask.js";
  import { getState, setCurrentPageId } from "../../stores/sidebar.svelte.js";
  import IndexDataPrompt from "../IndexDataPrompt.svelte";

  const sidebarState = getState();

  let messages = $state([]);
  let inputValue = $state("");
  let isLoading = $state(false);
  let mentionedPageIds = $state([]);

  let autocompleteVisible = $state(false);
  let autocompleteSuggestions = $state([]);
  let autocompleteSelectedIndex = $state(-1);
  let mentionStart = $state(-1);

  let availableProviders = $state([]);
  let selectedProviderId = $state(null);
  let showMissingKeyPrompt = $state(false);

  let availableModels = $state([]);
  let selectedModelId = $state(null);
  let loadingModels = $state(false);

  let inputEl = $state(null);
  let messagesEl = $state(null);
  let autocompleteEl = $state(null);

  let debounceTimeout = null;

  const errorMessages = {
    empty_question: "Please enter a question.",
    no_matching_pages: "No relevant pages found. Try asking about something in your pages.",
    api_error: "Unable to process your question. Please try again.",
    unexpected: "Something went wrong. Please try again.",
    ai_key_not_configured: "No AI provider configured.",
  };

  const selectedProvider = $derived(
    availableProviders.find((p) => p.external_id === selectedProviderId)
  );

  onMount(async () => {
    await loadProviders();

    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        loadProviders();
      }
    };
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  });

  async function loadProviders() {
    try {
      availableProviders = await fetchAvailableProviders();
      const defaultProvider = availableProviders.find((p) => p.is_default);
      if (defaultProvider) {
        selectedProviderId = defaultProvider.external_id;
      } else if (availableProviders.length > 0) {
        selectedProviderId = availableProviders[0].external_id;
      }

      const savedProviderId = localStorage.getItem("ask_provider_id");
      if (savedProviderId && availableProviders.some((p) => p.external_id === savedProviderId)) {
        selectedProviderId = savedProviderId;
      }

      showMissingKeyPrompt = availableProviders.length === 0;

      if (selectedProviderId) {
        await loadModelsForProvider(selectedProviderId);
      }
    } catch (error) {
      console.error("Failed to load providers:", error);
      showMissingKeyPrompt = true;
    }
  }

  async function loadModelsForProvider(providerId) {
    const provider = availableProviders.find((p) => p.external_id === providerId);
    if (!provider) return;

    loadingModels = true;
    try {
      const result = await fetchProviderModels(provider.provider);
      availableModels = result.models || [];

      const savedModelKey = `ask_model_${provider.provider}`;
      const savedModel = localStorage.getItem(savedModelKey);

      if (savedModel && availableModels.some((m) => m.id === savedModel)) {
        selectedModelId = savedModel;
      } else if (result.default_model) {
        selectedModelId = result.default_model;
      } else if (availableModels.length > 0) {
        selectedModelId = availableModels[0].id;
      }
    } catch (error) {
      console.error("Failed to load models:", error);
      availableModels = [];
    } finally {
      loadingModels = false;
    }
  }

  async function handleProviderChange(e) {
    selectedProviderId = e.target.value;
    localStorage.setItem("ask_provider_id", selectedProviderId);
    await loadModelsForProvider(selectedProviderId);
  }

  function handleModelChange(e) {
    selectedModelId = e.target.value;
    const provider = availableProviders.find((p) => p.external_id === selectedProviderId);
    if (provider) {
      localStorage.setItem(`ask_model_${provider.provider}`, selectedModelId);
    }
  }

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  function renderMentionsWithEscape(text) {
    const parts = [];
    let lastIndex = 0;
    const mentionRegex = /@\[([^\]]+)\]/g;
    let match;

    while ((match = mentionRegex.exec(text)) !== null) {
      if (match.index > lastIndex) {
        parts.push(escapeHtml(text.substring(lastIndex, match.index)));
      }
      const title = escapeHtml(match[1]);
      parts.push(`<span class="mention">@${title}</span>`);
      lastIndex = match.index + match[0].length;
    }

    if (lastIndex < text.length) {
      parts.push(escapeHtml(text.substring(lastIndex)));
    }

    return parts.join("");
  }

  function getTimeAgo(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const seconds = Math.floor((now - date) / 1000);

    if (seconds < 60) return "just now";
    if (seconds < 3600) return `${Math.floor(seconds / 60)} minutes ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)} hours ago`;
    if (seconds < 604800) return `${Math.floor(seconds / 86400)} days ago`;
    return date.toLocaleDateString();
  }

  async function sendMessage() {
    const message = inputValue.trim();
    if (!message || isLoading) return;

    if (availableProviders.length === 0) {
      showMissingKeyPrompt = true;
      return;
    }

    messages = [...messages, { type: "user", content: message }];
    inputValue = "";
    isLoading = true;

    setTimeout(() => {
      if (messagesEl) messagesEl.scrollTop = messagesEl.scrollHeight;
    }, 0);

    try {
      const pageIds = [];
      if (sidebarState.currentPageId) {
        pageIds.push(sidebarState.currentPageId);
      }
      mentionedPageIds.forEach((id) => {
        if (!pageIds.includes(id)) {
          pageIds.push(id);
        }
      });

      const response = await askQuestion(message, pageIds, {
        configId: selectedProviderId,
        model: selectedModelId,
      });
      messages = [
        ...messages,
        {
          type: "assistant",
          content: response.answer,
          pages: response.pages,
        },
      ];

      mentionedPageIds = [];
    } catch (error) {
      const errorCode = error instanceof AskError ? error.code : "network";

      if (errorCode === "ai_key_not_configured") {
        showMissingKeyPrompt = true;
      }

      messages = [
        ...messages,
        {
          type: "error",
          content: errorMessages[errorCode] || "An error occurred. Please try again.",
        },
      ];
    } finally {
      isLoading = false;
      setTimeout(() => {
        if (inputEl) inputEl.focus();
      }, 0);
      setTimeout(() => {
        if (messagesEl) messagesEl.scrollTop = messagesEl.scrollHeight;
      }, 0);
    }
  }

  function handleKeydown(e) {
    if (autocompleteVisible) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        autocompleteSelectedIndex = Math.min(
          autocompleteSelectedIndex + 1,
          autocompleteSuggestions.length - 1
        );
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        autocompleteSelectedIndex = Math.max(autocompleteSelectedIndex - 1, 0);
        return;
      }
      if (e.key === "Enter" && autocompleteSelectedIndex >= 0) {
        e.preventDefault();
        e.stopPropagation();
        selectSuggestion(autocompleteSelectedIndex);
        return;
      }
      if (e.key === "Escape") {
        e.preventDefault();
        hideAutocomplete();
        return;
      }
      if (e.key === "Tab" && autocompleteSelectedIndex >= 0) {
        e.preventDefault();
        selectSuggestion(autocompleteSelectedIndex);
        return;
      }
    }

    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  function handleInput() {
    if (inputEl && !CSS.supports("field-sizing", "content")) {
      inputEl.style.height = "auto";
      inputEl.style.height = Math.min(inputEl.scrollHeight, 200) + "px";
    }

    checkForMention();
  }

  function checkForMention() {
    if (!inputEl) return;

    const value = inputEl.value;
    const cursorPos = inputEl.selectionStart;

    let atIndex = -1;
    for (let i = cursorPos - 1; i >= 0; i--) {
      if (value[i] === "@") {
        atIndex = i;
        break;
      }
      if (/\s/.test(value[i])) {
        break;
      }
    }

    if (atIndex >= 0) {
      const query = value.substring(atIndex + 1, cursorPos);
      if (query.length > 0 && !query.includes("]")) {
        mentionStart = atIndex;
        showAutocomplete(query);
        return;
      }
    }

    hideAutocomplete();
  }

  async function showAutocomplete(query) {
    autocompleteVisible = true;
    autocompleteSelectedIndex = -1;

    clearTimeout(debounceTimeout);
    debounceTimeout = setTimeout(async () => {
      try {
        const response = await autocompletePages(query);
        autocompleteSuggestions = response.pages || [];
        autocompleteSelectedIndex = autocompleteSuggestions.length > 0 ? 0 : -1;
      } catch (error) {
        console.error("Autocomplete error:", error);
        hideAutocomplete();
      }
    }, 200);
  }

  function hideAutocomplete() {
    autocompleteVisible = false;
    autocompleteSuggestions = [];
    autocompleteSelectedIndex = -1;
    mentionStart = -1;
  }

  function selectSuggestion(index) {
    if (index < 0 || index >= autocompleteSuggestions.length) return;

    const page = autocompleteSuggestions[index];
    const beforeMention = inputValue.substring(0, mentionStart);
    const afterMention = inputValue.substring(inputEl?.selectionStart || 0);
    const mentionText = `@[${page.title}]`;

    inputValue = beforeMention + mentionText + afterMention;

    mentionedPageIds = [...mentionedPageIds, page.external_id];

    hideAutocomplete();

    setTimeout(() => {
      if (inputEl) {
        const newPos = beforeMention.length + mentionText.length;
        inputEl.selectionStart = newPos;
        inputEl.selectionEnd = newPos;
        inputEl.focus();
      }
    }, 0);
  }

  function handleClickOutside(e) {
    if (
      autocompleteVisible &&
      autocompleteEl &&
      !autocompleteEl.contains(e.target) &&
      e.target !== inputEl
    ) {
      hideAutocomplete();
    }
  }

  function dismissMissingKeyPrompt() {
    showMissingKeyPrompt = false;
  }

  onMount(() => {
    document.addEventListener("click", handleClickOutside);
  });

  onDestroy(() => {
    document.removeEventListener("click", handleClickOutside);
    clearTimeout(debounceTimeout);
  });
</script>

{#if showMissingKeyPrompt}
  <div class="missing-key-prompt">
    <div class="missing-key-icon">
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"></path>
      </svg>
    </div>
    <h3 class="missing-key-title">AI Provider Required</h3>
    <p class="missing-key-text">
      To use Ask, configure an AI provider with your API key in Settings.
    </p>
    <a href="/settings#ai" class="missing-key-btn">
      Configure AI Provider
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polyline points="9 18 15 12 9 6"></polyline>
      </svg>
    </a>
    {#if messages.length > 0}
      <button class="missing-key-dismiss" onclick={dismissMissingKeyPrompt}>Dismiss</button>
    {/if}
  </div>
{:else}
  <div class="ask-container">
    <IndexDataPrompt compact={true} />
  </div>
  <div id="chat-messages" class="chat-messages" bind:this={messagesEl}>
    {#if messages.length === 0}
      <div class="chat-empty">
        <div class="chat-empty-icon">💬</div>
        <div class="chat-empty-title">Chat about your pages</div>
        <div class="chat-empty-text">
          Ask questions, get summaries, or brainstorm ideas.
        </div>
      </div>
    {:else}
      {#each messages as message, i (i)}
        <div class="chat-message chat-message-{message.type}">
          <div class="chat-message-content">
            {#if message.type === "loading"}
              <div class="loading-dots">
                <span></span>
                <span></span>
                <span></span>
              </div>
            {:else if message.type === "error"}
              <div class="error-icon">⚠️</div>
              <div class="error-text">{message.content}</div>
            {:else if message.type === "user"}
              <div class="message-text">{@html renderMentionsWithEscape(message.content)}</div>
            {:else}
              <div class="message-text">{escapeHtml(message.content)}</div>
              {#if message.pages?.length > 0}
                <div class="message-citations">
                  <div class="citations-label">Sources:</div>
                  <div class="citations-list">
                    {#each message.pages as page (page.id)}
                      <button
                        class="citation-item"
                        onclick={() => console.log("Navigate to:", page.id)}
                      >
                        <span class="citation-title">{page.title}</span>
                      </button>
                    {/each}
                  </div>
                </div>
              {/if}
            {/if}
          </div>
        </div>
      {/each}

      {#if isLoading}
        <div class="chat-message chat-message-loading">
          <div class="chat-message-content">
            <div class="loading-dots">
              <span></span>
              <span></span>
              <span></span>
            </div>
          </div>
        </div>
      {/if}
    {/if}
  </div>

  <div class="chat-input-area">
    <div class="selectors-row">
      {#if availableProviders.length > 1}
        <div class="selector-group">
          <select class="provider-select" value={selectedProviderId} onchange={handleProviderChange}>
            {#each availableProviders as provider (provider.external_id)}
              <option value={provider.external_id}>
                {provider.display_name}
                {#if provider.scope === "org"}(org){/if}
              </option>
            {/each}
          </select>
        </div>
      {/if}

      {#if availableModels.length > 0}
        <div class="selector-group model-selector">
          <select class="model-select" value={selectedModelId} onchange={handleModelChange} disabled={loadingModels}>
            {#each availableModels as model (model.id)}
              <option value={model.id}>
                {model.name}
              </option>
            {/each}
          </select>
        </div>
      {/if}
    </div>

    <div class="chat-input-wrapper">
      {#if autocompleteVisible}
        <div class="autocomplete-dropdown" bind:this={autocompleteEl}>
          {#if autocompleteSuggestions.length === 0}
            <div class="autocomplete-loading">Searching...</div>
          {:else}
            {#each autocompleteSuggestions as page, index (page.external_id)}
              <div
                class="autocomplete-item"
                class:selected={index === autocompleteSelectedIndex}
                onclick={() => selectSuggestion(index)}
                onkeydown={(e) => e.key === 'Enter' && selectSuggestion(index)}
                role="option"
                tabindex="0"
                aria-selected={index === autocompleteSelectedIndex}
              >
                <div class="autocomplete-item-title">
                  {page.title || "Untitled"}
                </div>
                <div class="autocomplete-item-meta">
                  updated {getTimeAgo(page.updated || page.created)}
                </div>
              </div>
            {/each}
          {/if}
        </div>
      {/if}

      <textarea
        id="chat-input"
        bind:this={inputEl}
        bind:value={inputValue}
        class="chat-input"
        placeholder="Ask something about your pages..."
        rows="1"
        disabled={isLoading}
        oninput={handleInput}
        onkeydown={handleKeydown}
      ></textarea>
      <button
        id="chat-send-btn"
        class="chat-send-btn"
        class:active={inputValue.trim() && !isLoading}
        disabled={isLoading || !inputValue.trim()}
        title="Send message"
        onclick={sendMessage}
      >
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="22" y1="2" x2="11" y2="13"></line>
          <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
        </svg>
      </button>
    </div>
  </div>
{/if}

<style>
  .ask-container {
    padding: 0.75rem 0.75rem 0;
  }

  .autocomplete-dropdown {
    position: absolute;
    bottom: 100%;
    left: 0;
    right: 0;
    margin-bottom: 0.5rem;
    max-height: 200px;
    overflow-y: auto;
    background: var(--bg-primary);
    border: 1px solid var(--border-light);
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    z-index: 100;
  }

  .autocomplete-item {
    padding: 0.625rem 0.75rem;
    cursor: pointer;
    transition: background 0.1s;
  }

  .autocomplete-item:hover,
  .autocomplete-item.selected {
    background: var(--bg-hover);
  }

  .autocomplete-item-title {
    font-size: 0.9rem;
    font-weight: 500;
    color: var(--text-primary);
  }

  .autocomplete-item-meta {
    font-size: 0.75rem;
    color: var(--text-secondary);
    margin-top: 0.125rem;
  }

  .autocomplete-loading {
    padding: 0.75rem;
    text-align: center;
    color: var(--text-secondary);
    font-size: 0.875rem;
  }

  .selectors-row {
    display: flex;
    gap: 0.5rem;
    padding: 0 0.75rem 0.5rem 0.75rem;
  }

  .selector-group {
    flex: 1;
    min-width: 0;
  }

  .selector-group select {
    width: 100%;
    padding: 0.4rem 0.5rem;
    border: 1px solid var(--border-light);
    border-radius: 6px;
    background: var(--bg-primary);
    color: var(--text-primary);
    font-size: 0.8rem;
    cursor: pointer;
    appearance: none;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%236b7280' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 0.5rem center;
    padding-right: 1.5rem;
  }

  .selector-group select:focus {
    outline: none;
    border-color: #667eea;
  }

  .selector-group select:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .model-selector {
    flex: 1.2;
  }

  .missing-key-prompt {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 2rem 1.5rem;
    text-align: center;
    height: 100%;
  }

  .missing-key-icon {
    width: 64px;
    height: 64px;
    border-radius: 50%;
    background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 1rem;
    color: #667eea;
  }

  .missing-key-title {
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0 0 0.5rem 0;
  }

  .missing-key-text {
    font-size: 0.9rem;
    color: var(--text-secondary);
    margin: 0 0 1.5rem 0;
    line-height: 1.5;
  }

  .missing-key-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.75rem 1.25rem;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border-radius: 8px;
    font-size: 0.9rem;
    font-weight: 500;
    text-decoration: none;
    transition: transform 0.15s, box-shadow 0.15s;
  }

  .missing-key-btn:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
  }

  .missing-key-dismiss {
    margin-top: 1rem;
    padding: 0.5rem 1rem;
    background: none;
    border: none;
    color: var(--text-secondary);
    font-size: 0.85rem;
    cursor: pointer;
  }

  .missing-key-dismiss:hover {
    color: var(--text-primary);
  }
</style>
