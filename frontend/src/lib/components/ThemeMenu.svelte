<script>
  import { onMount } from "svelte";
  import { getStoredTheme, setTheme } from "../../theme.js";

  const OPTIONS = [
    { id: "light", label: "Light" },
    { id: "dark", label: "Dark" },
    { id: "system", label: "System" },
  ];

  let currentTheme = $state("system");

  function makeHandler(theme) {
    return (e) => {
      e.stopPropagation();
      currentTheme = theme;
      setTheme(theme);
    };
  }

  onMount(() => {
    currentTheme = getStoredTheme();

    // Sync if theme changes elsewhere (e.g. system preference shift while in "system" mode)
    const handleThemeChange = () => {
      currentTheme = getStoredTheme();
    };
    window.addEventListener("themechange", handleThemeChange);

    // Manually attach click handlers since Svelte's onclick doesn't work with mount()
    const buttons = document.querySelectorAll(".theme-menu [data-theme-option]");
    const wired = [];
    buttons.forEach((btn) => {
      const theme = btn.getAttribute("data-theme-option");
      const handler = makeHandler(theme);
      btn.addEventListener("click", handler);
      wired.push({ btn, handler });
    });

    return () => {
      window.removeEventListener("themechange", handleThemeChange);
      wired.forEach(({ btn, handler }) => btn.removeEventListener("click", handler));
    };
  });
</script>

<div class="theme-menu">
  <div
    class="theme-menu-divider"
    style="height: 1px; background: var(--border-light, #e5e7eb); margin: 0.375rem 0;"
  ></div>
  <div
    class="theme-menu-label"
    style="padding: 0.25rem 0.75rem 0.125rem; font-size: 0.7rem; font-weight: 600; color: var(--text-tertiary, #9ca3af); text-transform: uppercase; letter-spacing: 0.025em;"
  >
    Theme
  </div>
  {#each OPTIONS as opt}
    <button
      class="user-dropdown-item theme-menu-option"
      data-theme-option={opt.id}
      aria-pressed={currentTheme === opt.id}
      aria-label="Use {opt.label} theme"
      style="display: flex; align-items: center; gap: 0.5rem; padding: 0.3rem 0.75rem; color: var(--text-secondary);"
    >
      {#if opt.id === "light"}
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink: 0;">
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
      {:else if opt.id === "dark"}
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink: 0;">
          <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"></path>
        </svg>
      {:else}
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink: 0;">
          <rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect>
          <line x1="8" y1="21" x2="16" y2="21"></line>
          <line x1="12" y1="17" x2="12" y2="21"></line>
        </svg>
      {/if}
      <span style="flex: 1;">{opt.label}</span>
      {#if currentTheme === opt.id}
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink: 0; color: var(--accent-color, #2383e2);">
          <polyline points="20 6 9 17 4 12"></polyline>
        </svg>
      {/if}
    </button>
  {/each}
  <div
    class="theme-menu-divider"
    style="height: 1px; background: var(--border-light, #e5e7eb); margin: 0.375rem 0;"
  ></div>
</div>
