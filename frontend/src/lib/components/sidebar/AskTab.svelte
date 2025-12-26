<script>
  import { onMount, onDestroy } from "svelte";
  import { askQuestion, AskError, autocompletePages } from "../../../ask.js";
  import { getState, setCurrentPageId } from "../../stores/sidebar.svelte.js";

  const sidebarState = getState();

  // Local state
  let messages = $state([]);
  let inputValue = $state("");
  let isLoading = $state(false);
  let mentionedPageIds = $state([]);

  // Autocomplete state
  let autocompleteVisible = $state(false);
  let autocompleteSuggestions = $state([]);
  let autocompleteSelectedIndex = $state(-1);
  let mentionStart = $state(-1);

  // Element refs
  let inputEl = $state(null);
  let messagesEl = $state(null);
  let autocompleteEl = $state(null);

  // Debounce timeout
  let debounceTimeout = null;

  // Error messages
  const errorMessages = {
    empty_question: "Please enter a question.",
    no_matching_pages: "No relevant pages found. Try asking about something in your pages.",
    api_error: "Unable to process your question. Please try again.",
    unexpected: "Something went wrong. Please try again.",
  };

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

    // Add user message
    messages = [...messages, { type: "user", content: message }];
    inputValue = "";
    isLoading = true;

    // Scroll to bottom
    setTimeout(() => {
      if (messagesEl) messagesEl.scrollTop = messagesEl.scrollHeight;
    }, 0);

    try {
      // Combine current page ID with mentioned IDs
      const pageIds = [];
      if (sidebarState.currentPageId) {
        pageIds.push(sidebarState.currentPageId);
      }
      mentionedPageIds.forEach((id) => {
        if (!pageIds.includes(id)) {
          pageIds.push(id);
        }
      });

      const response = await askQuestion(message, pageIds);
      messages = [
        ...messages,
        {
          type: "assistant",
          content: response.answer,
          pages: response.pages,
        },
      ];

      // Clear mentioned page IDs
      mentionedPageIds = [];
    } catch (error) {
      const errorCode = error instanceof AskError ? error.code : "network";
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
        if (messagesEl) messagesEl.scrollTop = messagesEl.scrollHeight;
      }, 0);
    }
  }

  function handleKeydown(e) {
    // Handle autocomplete navigation
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

    // Send message on Enter (without shift)
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  function handleInput() {
    // Auto-resize textarea (fallback for browsers without field-sizing support)
    if (inputEl && !CSS.supports("field-sizing", "content")) {
      inputEl.style.height = "auto";
      inputEl.style.height = Math.min(inputEl.scrollHeight, 200) + "px";
    }

    // Check for @mention
    checkForMention();
  }

  function checkForMention() {
    if (!inputEl) return;

    const value = inputEl.value;
    const cursorPos = inputEl.selectionStart;

    // Find @ symbol before cursor
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

    // Track the page ID
    mentionedPageIds = [...mentionedPageIds, page.external_id];

    hideAutocomplete();

    // Move cursor after mention
    setTimeout(() => {
      if (inputEl) {
        const newPos = beforeMention.length + mentionText.length;
        inputEl.selectionStart = newPos;
        inputEl.selectionEnd = newPos;
        inputEl.focus();
      }
    }, 0);
  }

  // Handle click outside autocomplete
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

  onMount(() => {
    document.addEventListener("click", handleClickOutside);
  });

  onDestroy(() => {
    document.removeEventListener("click", handleClickOutside);
    clearTimeout(debounceTimeout);
  });
</script>

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
  <div class="chat-input-wrapper">
    <!-- Autocomplete dropdown -->
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

<style>
  /* Only autocomplete styles - rest uses global CSS */
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
</style>
