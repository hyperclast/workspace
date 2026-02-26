/**
 * Collaboration status indicator UI
 *
 * Shows users the current state of real-time collaboration (connected,
 * offline, denied, etc.) with a popover for details.
 *
 * Thin wrapper around CollabStatus.svelte — maintains the same
 * updateCollabStatus() and setupIndicatorPopover() APIs while
 * delegating rendering to Svelte.
 */

import { mount, flushSync } from "svelte";
import CollabStatus from "./lib/components/CollabStatus.svelte";
import { setStatus, setShowPopover } from "./lib/stores/collabStatus.svelte.js";

let instance = null;

/**
 * Update the collaboration status indicator in the UI.
 * Creates the indicator DOM elements on first call if they don't exist.
 *
 * @returns {Function|undefined} cleanup function on first call, undefined on subsequent calls
 */
export function updateCollabStatus(status) {
  // Find or create the wrapper
  let wrapper = document.getElementById("collab-status-wrapper");

  if (!wrapper) {
    const presenceIndicator = document.getElementById("presence-indicator");
    if (!presenceIndicator?.parentElement) return;

    wrapper = document.createElement("div");
    wrapper.id = "collab-status-wrapper";
    wrapper.className = "collab-status-wrapper";

    presenceIndicator.parentElement.insertBefore(wrapper, presenceIndicator);

    // Set initial state before mounting
    flushSync(() => {
      setStatus(status);
      setShowPopover(false);
    });

    // Mount the Svelte component into the wrapper
    instance = mount(CollabStatus, { target: wrapper });

    // Force render with status
    flushSync(() => {
      setStatus(status);
    });

    // Setup hover/click handlers for showing/hiding the popover.
    // Unlike setupIndicatorPopover (which uses direct DOM mutation),
    // this updates the Svelte store so re-renders don't overwrite visibility.
    let hideTimeout;
    const popover = document.getElementById("collab-popover");

    function show() {
      clearTimeout(hideTimeout);
      flushSync(() => setShowPopover(true));
    }

    function scheduleHide() {
      hideTimeout = setTimeout(() => {
        flushSync(() => setShowPopover(false));
      }, 200);
    }

    function cancelHide() {
      clearTimeout(hideTimeout);
    }

    function handleClickOutside(e) {
      if (!wrapper.contains(e.target)) {
        clearTimeout(hideTimeout);
        flushSync(() => setShowPopover(false));
      }
    }

    wrapper.addEventListener("mouseenter", show);
    wrapper.addEventListener("mouseleave", scheduleHide);
    wrapper.addEventListener("click", show);
    document.addEventListener("click", handleClickOutside);

    if (popover) {
      popover.addEventListener("mouseenter", cancelHide);
      popover.addEventListener("mouseleave", scheduleHide);
    }

    return () => {
      clearTimeout(hideTimeout);
      wrapper.removeEventListener("mouseenter", show);
      wrapper.removeEventListener("mouseleave", scheduleHide);
      wrapper.removeEventListener("click", show);
      document.removeEventListener("click", handleClickOutside);
      if (popover) {
        popover.removeEventListener("mouseenter", cancelHide);
        popover.removeEventListener("mouseleave", scheduleHide);
      }
    };
  }

  // Subsequent calls: just update the store
  flushSync(() => {
    setStatus(status);
  });
}

/**
 * Setup hover handlers for indicator popovers.
 * Used for both the collab status and readonly link indicators.
 *
 * @returns {Function} cleanup function that removes all listeners
 */
export function setupIndicatorPopover(wrapper, popover) {
  let hideTimeout;

  function show() {
    clearTimeout(hideTimeout);
    popover.style.display = "block";
  }

  function scheduleHide() {
    hideTimeout = setTimeout(() => {
      popover.style.display = "none";
    }, 200);
  }

  function cancelHide() {
    clearTimeout(hideTimeout);
  }

  function handleClickOutside(e) {
    if (!wrapper.contains(e.target)) {
      clearTimeout(hideTimeout);
      popover.style.display = "none";
    }
  }

  wrapper.addEventListener("mouseenter", show);
  wrapper.addEventListener("mouseleave", scheduleHide);
  popover.addEventListener("mouseenter", cancelHide);
  popover.addEventListener("mouseleave", scheduleHide);
  wrapper.addEventListener("click", show);
  document.addEventListener("click", handleClickOutside);

  return () => {
    clearTimeout(hideTimeout);
    wrapper.removeEventListener("mouseenter", show);
    wrapper.removeEventListener("mouseleave", scheduleHide);
    popover.removeEventListener("mouseenter", cancelHide);
    popover.removeEventListener("mouseleave", scheduleHide);
    wrapper.removeEventListener("click", show);
    document.removeEventListener("click", handleClickOutside);
  };
}
