/**
 * Sidebar bridge - mounts Svelte component and exposes functions
 */

import { mount } from "svelte";
import Sidebar from "./components/Sidebar.svelte";
import {
  openSidebar,
  closeSidebar,
  toggleSidebar,
  collapseSidebar,
  expandSidebar,
  setActiveTab,
  registerTab,
  registerTabHandler,
  registerPageChangeHandler,
  notifyPageChange,
  setCurrentPageId,
  initSidebarState,
} from "./stores/sidebar.svelte.js";

let mounted = false;

/**
 * Initialize the sidebar by mounting the Svelte component.
 */
export function initSidebar() {
  const container = document.getElementById("sidebar-root");
  if (!container) {
    console.error("[Sidebar] Container #sidebar-root not found");
    return;
  }

  // Check if already mounted and DOM element has content
  if (mounted && container.children.length > 0) return;

  // Clear any existing content and (re)mount
  container.innerHTML = "";

  // Mount the Svelte component
  mount(Sidebar, { target: container });

  // Initialize state (restore saved tab, etc.)
  initSidebarState();

  // Setup resize handlers after a brief delay to ensure DOM is ready
  setTimeout(() => setupSidebarResize(), 0);

  // Load private features
  loadPrivateFeatures();

  mounted = true;
}

async function loadPrivateFeatures() {
  try {
    // Construct path dynamically to prevent Vite's static analysis
    // This allows the OSS build to succeed when private/ directory doesn't exist
    const modulePath = [".", ".", "private", "index.js"].join("/");
    const { setupPrivateFeatures } = await import(/* @vite-ignore */ modulePath);
    await setupPrivateFeatures();
  } catch {
    // Private module not available (OSS version)
  }
}

// Re-export store functions for external use
export {
  openSidebar,
  closeSidebar,
  toggleSidebar,
  collapseSidebar,
  expandSidebar,
  setActiveTab,
  registerTab,
  registerTabHandler,
  registerPageChangeHandler,
  notifyPageChange,
  setCurrentPageId,
};

// Also export for backwards compatibility with setupSidebar
export function setupSidebar() {
  initSidebar();
}

// Sidebar resize functionality (kept as vanilla JS)
const LEFT_SIDEBAR_KEY = "ws-left-sidebar-width";
const RIGHT_SIDEBAR_KEY = "ws-right-sidebar-width";

const LEFT_MIN_WIDTH = 180;
const LEFT_MAX_WIDTH = 400;
const LEFT_DEFAULT_WIDTH = 260;

const RIGHT_MIN_WIDTH = 280;
const RIGHT_MAX_WIDTH = 600;
const RIGHT_DEFAULT_WIDTH = 360;

function setupSidebarResize() {
  setupLeftSidebarResize();
  setupRightSidebarResize();
}

function createResizeHandler(
  sidebar,
  handle,
  storageKey,
  minWidth,
  maxWidth,
  defaultWidth,
  getDelta
) {
  const savedWidth = localStorage.getItem(storageKey);
  if (savedWidth) {
    sidebar.style.width = `${savedWidth}px`;
  }

  let startX = 0;
  let startWidth = 0;

  function onPointerMove(e) {
    const delta = getDelta(e.clientX, startX);
    const newWidth = Math.min(maxWidth, Math.max(minWidth, startWidth + delta));
    sidebar.style.width = `${newWidth}px`;
  }

  function stopResize() {
    handle.classList.remove("active");
    document.body.classList.remove("sidebar-resizing");
    document.removeEventListener("pointermove", onPointerMove);
    document.removeEventListener("pointerup", stopResize);
    document.removeEventListener("pointercancel", stopResize);
    localStorage.setItem(storageKey, sidebar.offsetWidth);
  }

  handle.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    e.preventDefault();
    handle.setPointerCapture(e.pointerId);
    startX = e.clientX;
    startWidth = sidebar.offsetWidth;
    handle.classList.add("active");
    document.body.classList.add("sidebar-resizing");
    document.addEventListener("pointermove", onPointerMove);
    document.addEventListener("pointerup", stopResize);
    document.addEventListener("pointercancel", stopResize);
  });

  handle.addEventListener("dblclick", () => {
    sidebar.style.width = `${defaultWidth}px`;
    localStorage.setItem(storageKey, defaultWidth);
  });
}

function setupLeftSidebarResize() {
  const sidebar = document.getElementById("note-sidebar");
  if (!sidebar) return;

  // Check if handle already exists
  if (sidebar.querySelector(".sidebar-resize-handle-right")) return;

  const handle = document.createElement("div");
  handle.className = "sidebar-resize-handle sidebar-resize-handle-right";
  sidebar.appendChild(handle);

  createResizeHandler(
    sidebar,
    handle,
    LEFT_SIDEBAR_KEY,
    LEFT_MIN_WIDTH,
    LEFT_MAX_WIDTH,
    LEFT_DEFAULT_WIDTH,
    (clientX, startX) => clientX - startX
  );
}

function setupRightSidebarResize() {
  const sidebar = document.getElementById("chat-sidebar");
  if (!sidebar) return;

  // Check if handle already exists
  if (sidebar.querySelector(".sidebar-resize-handle-left")) return;

  const handle = document.createElement("div");
  handle.className = "sidebar-resize-handle sidebar-resize-handle-left";
  sidebar.appendChild(handle);

  createResizeHandler(
    sidebar,
    handle,
    RIGHT_SIDEBAR_KEY,
    RIGHT_MIN_WIDTH,
    RIGHT_MAX_WIDTH,
    RIGHT_DEFAULT_WIDTH,
    (clientX, startX) => startX - clientX
  );
}
