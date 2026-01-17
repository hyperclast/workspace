<script>
  import { onMount } from 'svelte';
  import {
    getAllShortcuts,
    getShortcut,
    setShortcut,
    formatShortcutForDisplay,
    onShortcutChange,
  } from '../../keyboardShortcuts.js';
  import { showToast } from '../../toast.js';

  let { keyboardShortcuts = {}, onUpdate } = $props();

  const isMac = typeof navigator !== 'undefined' && navigator.platform.toUpperCase().indexOf('MAC') >= 0;

  // State for editing shortcuts
  let editingShortcut = $state(null);
  let inputRef = $state(null);

  // Reactive customizable shortcuts
  let customizableShortcuts = $state(getAllShortcuts());

  onMount(() => {
    const unsubscribe = onShortcutChange(() => {
      customizableShortcuts = getAllShortcuts();
    });
    return unsubscribe;
  });

  function startEditing(shortcutId) {
    editingShortcut = shortcutId;
    setTimeout(() => {
      if (inputRef) {
        inputRef.focus();
      }
    }, 0);
  }

  function cancelEditing() {
    editingShortcut = null;
  }

  async function handleKeyCapture(event) {
    event.preventDefault();
    event.stopPropagation();

    // Escape cancels editing
    if (event.key === 'Escape') {
      cancelEditing();
      return;
    }

    // Build the key notation
    const parts = [];
    if (event.metaKey || event.ctrlKey) parts.push('Mod');
    if (event.shiftKey) parts.push('Shift');
    if (event.altKey) parts.push('Alt');

    // Get the key itself (lowercase for letter keys)
    let key = event.key;
    if (key.length === 1) {
      key = key.toLowerCase();
    } else if (key === ' ') {
      key = 'Space';
    }

    // Only accept modifier+key combos
    if (parts.length > 0 && key !== 'Control' && key !== 'Meta' && key !== 'Shift' && key !== 'Alt') {
      parts.push(key);
      const keyNotation = parts.join('-');

      await saveShortcut(editingShortcut, keyNotation);
      editingShortcut = null;
    }
  }

  async function disableShortcut(shortcutId) {
    await saveShortcut(shortcutId, 'disabled');
    editingShortcut = null;
  }

  async function resetShortcut(shortcutId) {
    await saveShortcut(shortcutId, null);
  }

  async function saveShortcut(actionId, keyNotation) {
    // Update local state immediately
    setShortcut(actionId, keyNotation);

    // Persist to backend
    if (onUpdate) {
      const newShortcuts = { ...keyboardShortcuts };
      if (keyNotation === null) {
        delete newShortcuts[actionId];
      } else {
        newShortcuts[actionId] = keyNotation;
      }

      const result = await onUpdate(newShortcuts);
      if (result.success) {
        showToast('Shortcut updated');
      } else {
        showToast(result.error || 'Failed to save shortcut', 'error');
      }
    }
  }
</script>

<section class="settings-section">
  <h3 class="settings-subsection-title">Customizable Keyboard Shortcuts</h3>

  <div class="shortcuts-list">
    {#each customizableShortcuts as shortcut}
      {#if editingShortcut === shortcut.id}
        <div class="shortcut-row shortcut-row-editing">
          <div class="shortcut-label">{shortcut.label}</div>
          <div class="shortcut-key-container">
            <div class="shortcut-capture">
              <input
                bind:this={inputRef}
                type="text"
                class="shortcut-input"
                placeholder="Press keys..."
                readonly
                onkeydown={handleKeyCapture}
                onblur={cancelEditing}
              />
              <button
                type="button"
                class="shortcut-btn"
                onmousedown={(e) => { e.preventDefault(); disableShortcut(shortcut.id); }}
              >
                Disable
              </button>
              <button
                type="button"
                class="shortcut-btn"
                onmousedown={(e) => { e.preventDefault(); cancelEditing(); }}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      {:else}
        <button
          type="button"
          class="shortcut-row shortcut-row-clickable"
          onclick={() => startEditing(shortcut.id)}
        >
          <div class="shortcut-label">{shortcut.label}</div>
          <div class="shortcut-key-container">
            <kbd class="shortcut-key" class:shortcut-key-disabled={shortcut.key === 'disabled'}>
              {formatShortcutForDisplay(shortcut.key)}
            </kbd>
            {#if shortcut.customized}
              <button
                type="button"
                class="shortcut-reset-btn"
                onclick={(e) => { e.stopPropagation(); resetShortcut(shortcut.id); }}
                title="Reset to default ({formatShortcutForDisplay(shortcut.default)})"
              >
                Reset
              </button>
            {/if}
          </div>
        </button>
      {/if}
    {/each}
  </div>

  <p class="shortcut-hint">
    Tip: Press <kbd>?</kbd> to see all keyboard shortcuts.
  </p>
</section>

<style>
  .shortcuts-list {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    margin-top: 1rem;
  }

  .shortcut-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.75rem 1rem;
    background: var(--bg-primary);
    border: 1px solid var(--border-light);
    border-radius: 8px;
    width: 100%;
    text-align: left;
  }

  .shortcut-row-clickable {
    cursor: pointer;
    transition: border-color 0.15s, background-color 0.15s;
  }

  .shortcut-row-clickable:hover {
    border-color: #667eea;
    background: var(--bg-tertiary, #fafafa);
  }

  .shortcut-row-clickable:hover .shortcut-key {
    border-color: #667eea;
    background: var(--bg-secondary);
  }

  .shortcut-label {
    font-size: 0.9rem;
    color: var(--text-primary);
  }

  .shortcut-key-container {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .shortcut-key {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 80px;
    height: 32px;
    padding: 0 0.75rem;
    font-family: inherit;
    font-size: 0.8rem;
    font-weight: 500;
    color: var(--text-primary);
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
    transition: border-color 0.15s, background-color 0.15s;
  }

  .shortcut-key-disabled {
    color: var(--text-tertiary);
    font-style: italic;
  }

  .shortcut-capture {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .shortcut-input {
    width: 120px;
    height: 32px;
    padding: 0 0.75rem;
    font-family: inherit;
    font-size: 0.8rem;
    color: var(--text-primary);
    background: var(--bg-primary);
    border: 2px solid #667eea;
    border-radius: 6px;
    outline: none;
  }

  .shortcut-input::placeholder {
    color: var(--text-tertiary);
  }

  .shortcut-btn {
    padding: 0.375rem 0.625rem;
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--text-secondary);
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    cursor: pointer;
    transition: background-color 0.15s;
  }

  .shortcut-btn:hover {
    background: var(--bg-tertiary, #e5e5e5);
  }

  .shortcut-reset-btn {
    padding: 0.25rem 0.5rem;
    font-size: 0.7rem;
    font-weight: 500;
    color: var(--text-tertiary);
    background: transparent;
    border: 1px solid var(--border-light);
    border-radius: 4px;
    cursor: pointer;
    transition: color 0.15s, border-color 0.15s;
  }

  .shortcut-reset-btn:hover {
    color: var(--text-secondary);
    border-color: var(--border-color);
  }

  .shortcut-hint {
    margin-top: 1.5rem;
    font-size: 0.85rem;
    color: var(--text-secondary);
  }

  .shortcut-hint kbd {
    display: inline-block;
    padding: 0.125rem 0.375rem;
    font-family: inherit;
    font-size: 0.8rem;
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    box-shadow: 0 1px 0 var(--border-color);
  }
</style>
