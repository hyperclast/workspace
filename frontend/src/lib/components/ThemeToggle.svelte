<script>
  import { onMount } from "svelte";
  import { getStoredTheme, getEffectiveTheme, setTheme } from "../../theme.js";

  // Cycle order: light → dark → system → light
  const CYCLE = ["light", "dark", "system"];
  const LABELS = { light: "Light", dark: "Dark", system: "System" };

  let currentTheme = $state("system");
  let effectiveTheme = $state("light");
  let buttonRef = null;

  function nextTheme(theme) {
    const i = CYCLE.indexOf(theme);
    return CYCLE[(i + 1) % CYCLE.length] || "light";
  }

  function handleButtonClick(e) {
    e.stopPropagation();
    const next = nextTheme(currentTheme);
    currentTheme = next;
    setTheme(next);
    effectiveTheme = getEffectiveTheme(next);
  }

  onMount(() => {
    currentTheme = getStoredTheme();
    effectiveTheme = getEffectiveTheme(currentTheme);

    const handleThemeChange = (e) => {
      effectiveTheme = e.detail.effective;
    };
    window.addEventListener("themechange", handleThemeChange);

    // Manually attach click handler since Svelte's onclick doesn't work with mount()
    buttonRef = document.querySelector(".theme-toggle .theme-toggle-btn");
    if (buttonRef) {
      buttonRef.addEventListener("click", handleButtonClick);
    }

    return () => {
      window.removeEventListener("themechange", handleThemeChange);
      if (buttonRef) {
        buttonRef.removeEventListener("click", handleButtonClick);
      }
    };
  });
</script>

<div class="theme-toggle" data-theme-toggle style="position: relative;">
  <button
    class="theme-toggle-btn"
    title="Switch to {LABELS[nextTheme(currentTheme)]}"
    aria-label="Switch to {LABELS[nextTheme(currentTheme)]} theme"
    style="display: flex; align-items: center; justify-content: center; width: 32px; height: 32px; padding: 0; background: transparent; border: none; border-radius: 6px; color: var(--text-secondary); cursor: pointer;"
  >
    {#if currentTheme === "system"}
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect>
        <line x1="8" y1="21" x2="16" y2="21"></line>
        <line x1="12" y1="17" x2="12" y2="21"></line>
      </svg>
    {:else if currentTheme === "dark"}
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
</div>
