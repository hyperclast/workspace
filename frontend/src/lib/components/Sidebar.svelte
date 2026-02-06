<script>
  import { onMount } from "svelte";
  import {
    getState,
    setActiveTab,
    collapseSidebar,
    expandSidebar,
    closeSidebar,
    openSidebar,
  } from "../stores/sidebar.svelte.js";
  import { getFeatureFlags, SIDEBAR_OVERLAY_BREAKPOINT } from "../../config.js";
  import AskTab from "./sidebar/AskTab.svelte";
  import LinksTab from "./sidebar/LinksTab.svelte";
  import DevTab from "./sidebar/DevTab.svelte";

  const state = getState();
  const featureFlags = getFeatureFlags();

  // Derived state for reactivity
  let isOpen = $derived(state.isOpen);
  let isCollapsed = $derived(state.isCollapsed);
  let activeTab = $derived(state.activeTab);
  let tabs = $derived(state.tabs);

  // Check if in overlay mode (sidebars overlay content instead of pushing it)
  const isMobile = () => window.innerWidth <= SIDEBAR_OVERLAY_BREAKPOINT;

  function handleClose() {
    if (isMobile()) {
      closeSidebar();
    } else {
      collapseSidebar();
    }
  }

  function handleExpand() {
    if (isMobile()) {
      openSidebar();
    } else {
      expandSidebar();
    }
  }

  onMount(() => {
    // Manually attach click handlers since Svelte's onclick doesn't work with mount().
    // Use getElementById instead of bind:this since $state refs cause errors with mount().
    const expandBtn = document.getElementById("chat-expand-btn");
    const closeBtn = document.getElementById("chat-close-btn");
    const overlay = document.getElementById("chat-overlay");
    const tabsContainer = document.querySelector(".sidebar-tabs");

    expandBtn?.addEventListener("click", handleExpand);
    closeBtn?.addEventListener("click", handleClose);
    overlay?.addEventListener("click", () => closeSidebar());

    // Tab clicks via delegation on the tabs container
    const handleTabContainerClick = (e) => {
      const tab = e.target.closest(".sidebar-tab");
      if (tab?.dataset.tab) {
        setActiveTab(tab.dataset.tab);
      }
    };
    tabsContainer?.addEventListener("click", handleTabContainerClick);

    // Handle window resize
    const handleResize = () => {
      // Close mobile sidebar when switching to desktop
      if (!isMobile() && isOpen) {
        closeSidebar();
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      expandBtn?.removeEventListener("click", handleExpand);
      closeBtn?.removeEventListener("click", handleClose);
      overlay?.removeEventListener("click", () => closeSidebar());
      tabsContainer?.removeEventListener("click", handleTabContainerClick);
      window.removeEventListener("resize", handleResize);
    };
  });
</script>

<!-- Mobile overlay -->
<div
  id="chat-overlay"
  class="chat-overlay"
  class:visible={isOpen}
  role="button"
  tabindex="-1"
  aria-label="Close sidebar"
></div>

<!-- Sidebar -->
<aside
  id="chat-sidebar"
  class="chat-sidebar"
  class:collapsed={isCollapsed}
  class:open={isOpen}
>
  <!-- Sidebar header -->
  <div class="chat-sidebar-header">
    <div class="sidebar-tabs">
      {#each tabs as tab (tab.id)}
        <button
          class="sidebar-tab"
          class:active={activeTab === tab.id}
          data-tab={tab.id}
        >
          {tab.label}
        </button>
      {/each}
    </div>
    <button id="chat-close-btn" class="chat-close-btn" title="Collapse sidebar">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="9 18 15 12 9 6"></polyline>
      </svg>
    </button>
  </div>

  <!-- Ask Tab -->
  <div
    class="sidebar-tab-content"
    class:hidden={activeTab !== "ask"}
    data-tab-content="ask"
  >
    <AskTab />
  </div>

  <!-- Links Tab -->
  <div
    class="sidebar-tab-content"
    class:hidden={activeTab !== "links"}
    data-tab-content="links"
  >
    <LinksTab />
  </div>

  <!-- Dev Tab (conditionally rendered) -->
  {#if featureFlags.devSidebar}
    <div
      class="sidebar-tab-content"
      class:hidden={activeTab !== "dev"}
      data-tab-content="dev"
    >
      <DevTab />
    </div>
  {/if}

  <!-- Private tabs will be dynamically added -->
  {#each tabs.filter(t => t.id !== "ask" && t.id !== "links" && t.id !== "dev") as tab (tab.id)}
    <div
      class="sidebar-tab-content"
      class:hidden={activeTab !== tab.id}
      data-tab-content={tab.id}
    >
      <!-- Private tab content will be rendered via slot or portal -->
      <div id="sidebar-tab-{tab.id}"></div>
    </div>
  {/each}
</aside>

<!-- Expand button (outside sidebar) — visibility controlled by CSS sibling selectors -->
<button
  id="chat-expand-btn"
  class="chat-expand-btn"
  title="Open sidebar"
>
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <polyline points="15 18 9 12 15 6"></polyline>
  </svg>
</button>
