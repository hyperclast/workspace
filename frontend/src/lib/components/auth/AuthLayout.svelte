<script>
  import { getBrandName } from "../../../config.js";

  let { title, subtitle, children } = $props();

  const brandName = getBrandName();
  const path = window.location.pathname;
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
