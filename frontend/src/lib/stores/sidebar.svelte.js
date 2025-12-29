/**
 * Sidebar store - manages right sidebar state
 */

import { getFeatureFlags } from "../../config.js";

const TAB_STORAGE_KEY = "ws-sidebar-tab";
const COLLAPSED_STORAGE_KEY = "ws-sidebar-collapsed";

// Build initial tabs list based on feature flags (alphabetical order)
function getInitialTabs() {
  const tabs = [{ id: "ask", label: "Ask" }];
  const flags = getFeatureFlags();
  if (flags.devSidebar) {
    tabs.push({ id: "dev", label: "Dev" });
  }
  tabs.push({ id: "links", label: "Ref" });
  return tabs;
}

// Reactive state
let isOpen = $state(false);
let isCollapsed = $state(localStorage.getItem(COLLAPSED_STORAGE_KEY) === "true");
let activeTab = $state(localStorage.getItem(TAB_STORAGE_KEY) || "links");
let currentPageId = $state(null);

// Available tabs (can be extended by private features)
let tabs = $state(getInitialTabs());

// Tab handlers for when tabs become active
const tabHandlers = new Map();

// Page change handlers
const pageChangeHandlers = [];

// Actions
export function openSidebar() {
  isOpen = true;
}

export function closeSidebar() {
  isOpen = false;
}

export function toggleSidebar() {
  isOpen = !isOpen;
}

export function collapseSidebar() {
  isCollapsed = true;
  localStorage.setItem(COLLAPSED_STORAGE_KEY, "true");
}

export function expandSidebar() {
  isCollapsed = false;
  localStorage.setItem(COLLAPSED_STORAGE_KEY, "false");
}

export function setActiveTab(tabId) {
  activeTab = tabId;
  localStorage.setItem(TAB_STORAGE_KEY, tabId);

  // Call tab handler if registered
  const handler = tabHandlers.get(tabId);
  if (handler) {
    handler();
  }
}

export function registerTab(tab) {
  // Add tab if not already present
  if (!tabs.some((t) => t.id === tab.id)) {
    tabs = [...tabs, tab];
  }
}

export function registerTabHandler(tabId, handler) {
  tabHandlers.set(tabId, handler);
}

export function registerPageChangeHandler(handler) {
  pageChangeHandlers.push(handler);
  // Call immediately if page is set
  if (currentPageId !== null) {
    handler(currentPageId);
  }
}

export function notifyPageChange(pageId) {
  currentPageId = pageId;
  pageChangeHandlers.forEach((handler) => handler(pageId));
}

export function setCurrentPageId(pageId) {
  currentPageId = pageId;
}

// Get state for components
export function getState() {
  return {
    get isOpen() {
      return isOpen;
    },
    get isCollapsed() {
      return isCollapsed;
    },
    get activeTab() {
      return activeTab;
    },
    get currentPageId() {
      return currentPageId;
    },
    get tabs() {
      return tabs;
    },
  };
}

// Initialize - restore saved tab
export function initSidebarState() {
  const savedTab = localStorage.getItem(TAB_STORAGE_KEY);
  if (savedTab && tabs.some((t) => t.id === savedTab)) {
    activeTab = savedTab;
  }
}
