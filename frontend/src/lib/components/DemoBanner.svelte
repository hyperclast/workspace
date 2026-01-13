<div class="demo-banner">
  <span class="demo-banner-text">Hyperclast Demo</span>
  <span class="demo-banner-dot">·</span>
  <span class="demo-banner-cta">
    <a href="/signup/">Sign up</a> to save your work
  </span>
</div>

<style>
  .demo-banner {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    height: 44px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    z-index: 10000;
    font-size: 0.875rem;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  }

  .demo-banner-text {
    font-weight: 600;
  }

  .demo-banner-dot {
    opacity: 0.6;
  }

  .demo-banner-cta {
    opacity: 0.95;
  }

  .demo-banner-cta a {
    color: white;
    text-decoration: underline;
    text-underline-offset: 2px;
  }

  .demo-banner-cta a:hover {
    opacity: 0.85;
  }

  /* Responsive */
  @media (max-width: 500px) {
    .demo-banner {
      height: auto;
      padding: 0.5rem 1rem;
      flex-wrap: wrap;
      gap: 0.25rem 0.5rem;
    }
  }
</style>
