<script>
  import Modal from './Modal.svelte';
  import {
    getShortcut,
    formatShortcutForDisplay,
    onShortcutChange,
  } from '../keyboardShortcuts.js';
  import { onMount } from 'svelte';

  let { open = $bindable(false) } = $props();

  const isMac = typeof navigator !== 'undefined' && navigator.platform.toUpperCase().indexOf('MAC') >= 0;
  const modKey = isMac ? 'Cmd' : 'Ctrl';

  // Get current shortcuts (may be customized or disabled)
  let toggleCheckboxKey = $state(formatShortcutForDisplay(getShortcut('toggleCheckbox')));
  let commandPaletteKey = $state(formatShortcutForDisplay(getShortcut('openCommandPalette')));

  onMount(() => {
    const unsubscribe = onShortcutChange(() => {
      toggleCheckboxKey = formatShortcutForDisplay(getShortcut('toggleCheckbox'));
      commandPaletteKey = formatShortcutForDisplay(getShortcut('openCommandPalette'));
    });
    return unsubscribe;
  });

  // Shortcuts organized by context
  const shortcutSections = [
    {
      category: 'Tasks',
      items: [
        { id: 'toggleCheckbox', action: 'Toggle checkbox' },
      ]
    },
    {
      category: 'Navigation',
      items: [
        { id: 'openCommandPalette', action: 'Open command palette' },
        { keys: ['?'], action: 'Keyboard shortcuts' },
      ]
    },
    {
      category: 'Text Formatting',
      items: [
        { keys: ['Tab'], action: 'Indent list item' },
        { keys: ['Shift+Tab'], action: 'Unindent list item' },
        { keys: ['Enter'], action: 'Continue blockquote' },
        { keys: ['Shift+Enter'], action: 'Exit blockquote' },
      ]
    },
    {
      category: 'Markdown Tables',
      items: [
        { keys: ['Tab'], action: 'Next cell' },
        { keys: ['Shift+Tab'], action: 'Previous cell' },
        { keys: ['Enter'], action: 'Same column, next row' },
        { keys: ['\u2191', '\u2193'], action: 'Navigate rows' },
        { keys: [`${modKey}+Enter`], action: 'Insert row below' },
        { keys: [`${modKey}+Shift+Enter`], action: 'Insert row above' },
        { keys: [`${modKey}+Shift+\u2192`], action: 'Insert column right' },
        { keys: [`${modKey}+Shift+\u2190`], action: 'Insert column left' },
      ]
    },
    {
      category: 'General',
      items: [
        { keys: ['Escape'], action: 'Close modal / cancel' },
      ]
    },
  ];

  function getKeyDisplay(item) {
    // For dynamic shortcuts, use the current value
    if (item.id === 'toggleCheckbox') {
      return toggleCheckboxKey;
    }
    if (item.id === 'openCommandPalette') {
      return commandPaletteKey;
    }
    // For static shortcuts, join the keys
    return item.keys.join(' / ');
  }

  function isDisabled(item) {
    if (item.id) {
      return getShortcut(item.id) === 'disabled';
    }
    return false;
  }
</script>

<Modal bind:open title="Keyboard Shortcuts" size="wide">
  <div class="help-content">
    {#each shortcutSections as section}
      <div class="help-section">
        <h3 class="help-section-title">{section.category}</h3>
        <div class="help-shortcuts">
          {#each section.items as item}
            <div class="help-shortcut-row">
              <div class="help-keys">
                {#if item.id}
                  <kbd class="help-key" class:help-key-disabled={isDisabled(item)}>
                    {getKeyDisplay(item)}
                  </kbd>
                {:else}
                  {#each item.keys as key, i}
                    {#if i > 0}
                      <span class="help-key-separator">/</span>
                    {/if}
                    <kbd class="help-key">{key}</kbd>
                  {/each}
                {/if}
              </div>
              <div class="help-action">{item.action}</div>
            </div>
          {/each}
        </div>
      </div>
    {/each}

  </div>
  {#snippet footer()}
    <div class="help-footer">
      <a href="/settings/#editor" class="help-customize-btn">Customize</a>
    </div>
  {/snippet}
</Modal>

<style>
  .help-content {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
    padding-right: 1rem;
  }

  .help-section {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .help-section-title {
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--text-secondary);
    margin: 0;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid var(--border-color);
  }

  .help-shortcuts {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .help-shortcut-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.25rem 0;
  }

  .help-keys {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    flex-shrink: 0;
  }

  .help-key {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 1.75rem;
    height: 1.5rem;
    padding: 0 0.5rem;
    font-family: inherit;
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--text-primary);
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    box-shadow: 0 1px 0 var(--border-color);
  }

  .help-key-disabled {
    color: var(--text-tertiary);
    font-style: italic;
  }

  .help-key-separator {
    color: var(--text-tertiary);
    font-size: 0.75rem;
  }

  .help-action {
    font-size: 0.875rem;
    color: var(--text-primary);
    text-align: right;
  }

  .help-footer {
    display: flex;
    justify-content: center;
    width: 100%;
  }

  .help-customize-btn {
    display: inline-flex;
    align-items: center;
    padding: 0.375rem 0.75rem;
    font-size: 0.8rem;
    font-weight: 500;
    color: #667eea;
    background: transparent;
    border: 1px solid #667eea;
    border-radius: 4px;
    text-decoration: none;
    transition: background-color 0.15s, color 0.15s;
  }

  .help-customize-btn:hover {
    background: #667eea;
    color: white;
  }
</style>
