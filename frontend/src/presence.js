/**
 * Presence indicators UI management
 * Shows who's currently editing the document
 *
 * Thin wrapper around PresenceIndicator.svelte — maintains the same
 * setupPresenceUI(awareness) API while delegating rendering to Svelte.
 * Uses a reactive store so the component can be updated without unmount/remount.
 */

import { mount, unmount, flushSync } from "svelte";
import PresenceIndicator from "./lib/components/PresenceIndicator.svelte";
import { setUsers, setShowPopover } from "./lib/stores/presence.svelte.js";

let instance = null;

/**
 * Setup presence UI and listen to awareness changes.
 * Mounts a Svelte component into #presence-indicator.
 *
 * @param {Object} awareness - Yjs awareness object
 * @returns {Function} cleanup function
 */
export function setupPresenceUI(awareness) {
  const target = document.getElementById("presence-indicator");
  if (!target) return () => {};

  // Clean up previous instance if any
  if (instance) {
    unmount(instance);
    instance = null;
  }

  target.innerHTML = "";

  let hideTimeout;
  let cleaned = false;

  function collectUsers() {
    const states = awareness.getStates();
    const collected = [];
    states.forEach((state, clientId) => {
      if (state.user) {
        collected.push({
          clientId,
          name: state.user.name || "Anonymous",
          color: state.user.color || "#999",
        });
      }
    });
    return collected;
  }

  function updateUsers() {
    if (cleaned) return;
    flushSync(() => {
      setUsers(collectUsers());
    });
  }

  function show() {
    clearTimeout(hideTimeout);
    flushSync(() => {
      setShowPopover(true);
    });
  }

  function scheduleHide() {
    hideTimeout = setTimeout(() => {
      flushSync(() => {
        setShowPopover(false);
      });
    }, 300);
  }

  function cancelHide() {
    clearTimeout(hideTimeout);
  }

  function handleClickOutside(e) {
    if (!target.contains(e.target)) {
      clearTimeout(hideTimeout);
      flushSync(() => {
        setShowPopover(false);
      });
    }
  }

  // Mount the Svelte component (once — it reads from the store reactively)
  flushSync(() => {
    setUsers(collectUsers());
    setShowPopover(false);
  });

  instance = mount(PresenceIndicator, { target });

  // Force initial render with current users
  flushSync(() => {
    setUsers(collectUsers());
  });

  // Subscribe to awareness changes
  awareness.on("change", updateUsers);

  // Hover handlers on the indicator (parent container)
  target.addEventListener("mouseenter", show);
  target.addEventListener("mouseleave", scheduleHide);

  // Click to open (touch devices)
  target.addEventListener("click", show);

  // Click outside to close
  document.addEventListener("click", handleClickOutside);

  // Popover hover handlers — the popover element is stable (not re-created)
  // since we use store-based updates instead of unmount/remount.
  const popover = document.getElementById("presence-popover");
  if (popover) {
    popover.addEventListener("mouseenter", cancelHide);
    popover.addEventListener("mouseleave", scheduleHide);
  }

  return () => {
    cleaned = true;
    awareness.off("change", updateUsers);
    clearTimeout(hideTimeout);
    target.removeEventListener("mouseenter", show);
    target.removeEventListener("mouseleave", scheduleHide);
    target.removeEventListener("click", show);
    document.removeEventListener("click", handleClickOutside);
    if (popover) {
      popover.removeEventListener("mouseenter", cancelHide);
      popover.removeEventListener("mouseleave", scheduleHide);
    }
    // Don't unmount — leave the DOM as-is so existing content remains visible.
    // The component will be cleaned up on next setupPresenceUI call or page navigation.
    instance = null;
  };
}
