<script>
  import { onMount } from "svelte";
  import {
    getState,
    setActiveTab,
    closeSidebar,
  } from "../stores/sidebar.svelte.js";
  import { getFeatureFlags, SIDEBAR_OVERLAY_BREAKPOINT } from "../../config.js";
  import AskTab from "./sidebar/AskTab.svelte";
  import CommentsTab from "./sidebar/CommentsTab.svelte";
  import LinksTab from "./sidebar/LinksTab.svelte";
  import DevTab from "./sidebar/DevTab.svelte";
  import RewindTab from "../../rewind/RewindTab.svelte";

  const state = getState();
  const featureFlags = getFeatureFlags();

  // Derived state for reactivity
  let isOpen = $derived(state.isOpen);
  let isCollapsed = $derived(state.isCollapsed);
  let activeTab = $derived(state.activeTab);
  let tabs = $derived(state.tabs);

  onMount(() => {
    // Manually attach click handlers since Svelte's onclick doesn't work with mount().
    // Use getElementById instead of bind:this since $state refs cause errors with mount().
    const overlay = document.getElementById("chat-overlay");
    const tabsContainer = document.querySelector(".sidebar-tabs");

    const handleOverlayClick = () => closeSidebar();
    overlay?.addEventListener("click", handleOverlayClick);

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
      if (window.innerWidth > SIDEBAR_OVERLAY_BREAKPOINT && isOpen) {
        closeSidebar();
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      overlay?.removeEventListener("click", handleOverlayClick);
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
    <button id="sidebar-panel-toggle" class="sidebar-panel-toggle" title="Toggle sidebar">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect class="panel-fill" x="15" y="3" width="6" height="18" rx="2" ry="2" stroke="none" />
        <rect x="3" y="3" width="18" height="18" rx="2" />
        <line x1="15" y1="3" x2="15" y2="21" />
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

  <!-- Comments Tab -->
  <div
    class="sidebar-tab-content"
    class:hidden={activeTab !== "comments"}
    data-tab-content="comments"
  >
    <CommentsTab />
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

  <!-- Rewind Tab (conditionally rendered) -->
  {#if featureFlags.rewind}
    <div
      class="sidebar-tab-content"
      class:hidden={activeTab !== "rewind"}
      data-tab-content="rewind"
    >
      <RewindTab />
    </div>
  {/if}

  <!-- Private tabs will be dynamically added -->
  {#each tabs.filter(t => t.id !== "ask" && t.id !== "comments" && t.id !== "links" && t.id !== "dev" && t.id !== "rewind") as tab (tab.id)}
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
