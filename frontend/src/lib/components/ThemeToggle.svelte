<script>
  import { onMount } from "svelte";
  import { getStoredTheme, getEffectiveTheme, setTheme } from "../../theme.js";

  let currentTheme = $state("system");
  let effectiveTheme = $state("light");
  let popoverOpen = $state(false);
  let wrapperEl = $state(null);

  const themes = [
    { id: "light", label: "Light" },
    { id: "dark", label: "Dark" },
    { id: "system", label: "System" },
  ];

  onMount(() => {
    currentTheme = getStoredTheme();
    effectiveTheme = getEffectiveTheme(currentTheme);

    const handleThemeChange = (e) => {
      effectiveTheme = e.detail.effective;
    };
    window.addEventListener("themechange", handleThemeChange);

    const handleClickOutside = (e) => {
      if (wrapperEl && !wrapperEl.contains(e.target)) {
        popoverOpen = false;
      }
    };
    document.addEventListener("click", handleClickOutside);

    return () => {
      window.removeEventListener("themechange", handleThemeChange);
      document.removeEventListener("click", handleClickOutside);
    };
  });

  function togglePopover(e) {
    e.stopPropagation();
    popoverOpen = !popoverOpen;
  }

  function selectTheme(themeId) {
    currentTheme = themeId;
    setTheme(themeId);
    effectiveTheme = getEffectiveTheme(themeId);
    popoverOpen = false;
  }
</script>

<div class="theme-toggle" bind:this={wrapperEl} data-theme-toggle>
  <button
    class="theme-toggle-btn"
    onclick={togglePopover}
    title="Change theme"
    aria-label="Change theme"
    aria-expanded={popoverOpen}
  >
    {#if effectiveTheme === "dark"}
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"></path>
      </svg>
    {:else}
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="4"></circle>
        <path d="M12 2v2"></path>
        <path d="M12 20v2"></path>
        <path d="m4.93 4.93 1.41 1.41"></path>
        <path d="m17.66 17.66 1.41 1.41"></path>
        <path d="M2 12h2"></path>
        <path d="M20 12h2"></path>
        <path d="m6.34 17.66-1.41 1.41"></path>
        <path d="m19.07 4.93-1.41 1.41"></path>
      </svg>
    {/if}
  </button>

  {#if popoverOpen}
    <div class="theme-popover">
      {#each themes as theme (theme.id)}
        <button
          class="theme-popover-item"
          class:active={currentTheme === theme.id}
          onclick={() => selectTheme(theme.id)}
        >
          <span class="theme-radio"></span>
          <span class="theme-label">{theme.label}</span>
        </button>
      {/each}
    </div>
  {/if}
</div>

<style>
  .theme-toggle {
    position: relative;
  }

  .theme-toggle-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    padding: 0;
    background: transparent;
    border: none;
    border-radius: 6px;
    color: var(--text-secondary, #787774);
    cursor: pointer;
    transition: background 0.15s, color 0.15s;
  }

  .theme-toggle-btn:hover {
    background: rgba(0, 0, 0, 0.05);
    color: var(--text-primary, #37352f);
  }

  :global(:root.dark) .theme-toggle-btn:hover,
  :global(:root[data-theme="dark"]) .theme-toggle-btn:hover {
    background: rgba(255, 255, 255, 0.1);
  }

  .theme-popover {
    position: absolute;
    top: 100%;
    right: 0;
    margin-top: 0.5rem;
    background: var(--bg-primary, white);
    border-radius: 8px;
    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.12), 0 0 0 1px var(--border-light, #e9e9e7);
    min-width: 140px;
    padding: 0.375rem;
    z-index: 1000;
  }

  :global(:root.dark) .theme-popover,
  :global(:root[data-theme="dark"]) .theme-popover {
    background: #2d2d2d;
    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.4);
  }

  .theme-popover-item {
    display: flex;
    align-items: center;
    gap: 0.625rem;
    width: 100%;
    padding: 0.5rem 0.625rem;
    background: none;
    border: none;
    border-radius: 5px;
    font-size: 0.875rem;
    color: var(--text-primary, #37352f);
    cursor: pointer;
    transition: background 0.15s;
    text-align: left;
    font-family: inherit;
  }

  .theme-popover-item:hover {
    background: rgba(0, 0, 0, 0.04);
  }

  :global(:root.dark) .theme-popover-item,
  :global(:root[data-theme="dark"]) .theme-popover-item {
    color: #ebebeb;
  }

  :global(:root.dark) .theme-popover-item:hover,
  :global(:root[data-theme="dark"]) .theme-popover-item:hover {
    background: rgba(255, 255, 255, 0.08);
  }

  .theme-popover-item.active {
    color: var(--accent-color, #529cca);
  }

  .theme-radio {
    width: 14px;
    height: 14px;
    border: 2px solid var(--border-medium, rgba(55, 53, 47, 0.2));
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  :global(:root.dark) .theme-radio,
  :global(:root[data-theme="dark"]) .theme-radio {
    border-color: rgba(255, 255, 255, 0.2);
  }

  .theme-popover-item.active .theme-radio {
    border-color: var(--accent-color, #529cca);
  }

  .theme-radio::after {
    content: '';
    width: 6px;
    height: 6px;
    background: var(--accent-color, #529cca);
    border-radius: 50%;
    display: none;
  }

  .theme-popover-item.active .theme-radio::after {
    display: block;
  }

  .theme-label {
    font-weight: 500;
  }
</style>
