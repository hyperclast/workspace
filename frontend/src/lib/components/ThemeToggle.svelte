<script>
  import { onMount } from "svelte";
  import { getStoredTheme, getEffectiveTheme, setTheme } from "../../theme.js";

  let currentTheme = $state("system");
  let effectiveTheme = $state("light");
  let popoverOpen = $state(false);
  let buttonRef = $state(null);

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
      if (!e.target.closest(".theme-toggle")) {
        popoverOpen = false;
      }
    };
    document.addEventListener("click", handleClickOutside);

    // Manually attach click handler since Svelte's onclick doesn't work with mount()
    if (buttonRef) {
      buttonRef.addEventListener("click", handleButtonClick);
    }

    return () => {
      window.removeEventListener("themechange", handleThemeChange);
      document.removeEventListener("click", handleClickOutside);
      if (buttonRef) {
        buttonRef.removeEventListener("click", handleButtonClick);
      }
    };
  });

  function handleButtonClick(e) {
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

<div class="theme-toggle" data-theme-toggle style="position: relative;">
  <button
    bind:this={buttonRef}
    class="theme-toggle-btn"
    title="Change theme"
    aria-label="Change theme"
    aria-expanded={popoverOpen}
    style="display: flex; align-items: center; justify-content: center; width: 32px; height: 32px; padding: 0; background: transparent; border: none; border-radius: 6px; color: var(--text-secondary); cursor: pointer;"
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
    <div class="theme-popover" style="display: block !important; visibility: visible !important; opacity: 1 !important; position: absolute; top: 100%; right: 0; background: var(--bg-primary, white); border-radius: 8px; box-shadow: 0 4px 24px rgba(0,0,0,0.12), 0 0 0 1px var(--border-light); min-width: 150px; padding: 8px; z-index: 9999;">
      {#each themes as theme (theme.id)}
        <button
          class="theme-popover-item"
          class:active={currentTheme === theme.id}
          onclick={() => selectTheme(theme.id)}
          style="display: flex; width: 100%; padding: 8px; background: none; border: none; cursor: pointer; align-items: center; gap: 10px; border-radius: 5px; font-size: 0.875rem; color: {currentTheme === theme.id ? 'var(--accent-color)' : 'var(--text-primary)'};"
        >
          <span style="width: 14px; height: 14px; border: 2px solid {currentTheme === theme.id ? 'var(--accent-color)' : 'var(--border-medium)'}; border-radius: 50%; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
            {#if currentTheme === theme.id}
              <span style="width: 6px; height: 6px; background: var(--accent-color); border-radius: 50%;"></span>
            {/if}
          </span>
          <span style="font-weight: 500;">{theme.label}</span>
        </button>
      {/each}
    </div>
  {/if}
</div>
