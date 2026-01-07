<script>
  import { getBrandName } from "../../../config.js";
  import { getStoredTheme, getEffectiveTheme, setTheme } from "../../../theme.js";

  let { title, subtitle, children } = $props();

  const brandName = getBrandName();
  const path = window.location.pathname;

  let popoverOpen = $state(false);
  let storedTheme = $state(getStoredTheme());

  function togglePopover(e) {
    e.stopPropagation();
    popoverOpen = !popoverOpen;
  }

  function selectTheme(theme) {
    setTheme(theme);
    storedTheme = theme;
    popoverOpen = false;
  }

  function handleClickOutside(e) {
    if (!e.target.closest('.theme-toggle-wrapper')) {
      popoverOpen = false;
    }
  }

  $effect(() => {
    document.addEventListener('click', handleClickOutside);
    return () => document.removeEventListener('click', handleClickOutside);
  });
</script>

<nav class="site-nav">
  <div class="site-nav-container">
    <a href="/" class="site-logo">
      <svg class="logo-icon" viewBox="0 0 90 90" width="28" height="28">
        <path d="M 10,80 L 10,70 L 20,70 L 20,80 L 30,80 L 40,80 L 40,70 L 30,70 L 30,60 L 40,60 L 40,50 L 30,50 L 20,50 L 20,60 L 10,60 L 10,50 L 10,40 L 20,40 L 20,30 L 10,30 L 10,20 L 10,10 L 20,10 L 20,20 L 30,20 L 30,10 L 40,10 L 40,20 L 40,30 L 30,30 L 30,40 L 40,40 L 50,40 L 60,40 L 60,30 L 50,30 L 50,20 L 50,10 L 60,10 L 60,20 L 70,20 L 70,10 L 80,10 L 80,20 L 80,30 L 70,30 L 70,40 L 80,40 L 80,50 L 80,60 L 70,60 L 70,50 L 60,50 L 50,50 L 50,60 L 60,60 L 60,70 L 50,70 L 50,80 L 60,80 L 70,80 L 70,70 L 80,70 L 80,80" fill="none" stroke="currentColor" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
      {brandName}
    </a>
    <div class="site-nav-actions">
      <div class="theme-toggle-wrapper">
        <button class="theme-toggle-btn" onclick={togglePopover} title="Change theme" aria-label="Change theme">
          <svg class="theme-icon-sun" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
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
          <svg class="theme-icon-moon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"></path>
          </svg>
        </button>
        <div class="theme-popover" class:open={popoverOpen}>
          <button class="theme-radio" class:selected={storedTheme === 'light'} onclick={() => selectTheme('light')}>
            <span class="theme-radio-dot"></span>Light
          </button>
          <button class="theme-radio" class:selected={storedTheme === 'dark'} onclick={() => selectTheme('dark')}>
            <span class="theme-radio-dot"></span>Dark
          </button>
          <button class="theme-radio" class:selected={storedTheme === 'system'} onclick={() => selectTheme('system')}>
            <span class="theme-radio-dot"></span>System
          </button>
        </div>
      </div>
      <a href="/dev/" class="site-nav-link hide-mobile">Developers</a>
      <a href="/login" class="site-nav-link" class:site-nav-link-active={path === '/login'}>Log in</a>
      <a href="/signup" class="site-nav-btn" class:site-nav-btn-active={path === '/signup'}>Get Started</a>
    </div>
  </div>
</nav>

<div class="auth-container">
  <div class="auth-box">
    <h1>{title}</h1>
    {#if subtitle}
      <p class="auth-subtitle">{subtitle}</p>
    {/if}
    {@render children()}
  </div>
</div>

<style>
  :global(body:has(.auth-container)) {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    min-height: 100vh;
  }
  :global(:root.dark body:has(.auth-container)),
  :global(:root[data-theme="dark"] body:has(.auth-container)) {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  }
  :global(body:has(.auth-container) .site-nav) {
    background: transparent !important;
  }
  :global(body:has(.auth-container) .site-nav-link) {
    color: rgba(255, 255, 255, 0.9);
  }
  :global(body:has(.auth-container) .site-nav-link:hover) {
    color: white;
  }
  :global(body:has(.auth-container) .site-nav-btn) {
    background: white !important;
    color: #667eea !important;
  }
  :global(:root.dark body:has(.auth-container) .site-nav-btn),
  :global(:root[data-theme="dark"] body:has(.auth-container) .site-nav-btn) {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
    color: white !important;
  }
  :global(:root.dark body:has(.auth-container) .site-nav-btn:hover),
  :global(:root[data-theme="dark"] body:has(.auth-container) .site-nav-btn:hover) {
    box-shadow: 0 4px 20px rgba(102, 126, 234, 0.4);
  }
</style>
