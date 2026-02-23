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

    wrapper.addEventListener("mouseenter", () => {
      clearTimeout(hideTimeout);
      flushSync(() => setShowPopover(true));
    });

    wrapper.addEventListener("mouseleave", () => {
      hideTimeout = setTimeout(() => {
        flushSync(() => setShowPopover(false));
      }, 200);
    });

    if (popover) {
      popover.addEventListener("mouseenter", () => {
        clearTimeout(hideTimeout);
      });

      popover.addEventListener("mouseleave", () => {
        hideTimeout = setTimeout(() => {
          flushSync(() => setShowPopover(false));
        }, 200);
      });
    }

    wrapper.addEventListener("click", () => {
      clearTimeout(hideTimeout);
      flushSync(() => setShowPopover(true));
    });

    document.addEventListener("click", (e) => {
      if (!wrapper.contains(e.target)) {
        clearTimeout(hideTimeout);
        flushSync(() => setShowPopover(false));
      }
    });

    return;
  }

  // Subsequent calls: just update the store
  flushSync(() => {
    setStatus(status);
  });
}

/**
 * Setup hover handlers for indicator popovers.
 * Used for both the collab status and readonly link indicators.
 */
export function setupIndicatorPopover(wrapper, popover) {
  let hideTimeout;

  wrapper.addEventListener("mouseenter", () => {
    clearTimeout(hideTimeout);
    popover.style.display = "block";
  });

  wrapper.addEventListener("mouseleave", () => {
    hideTimeout = setTimeout(() => {
      popover.style.display = "none";
    }, 200);
  });

  popover.addEventListener("mouseenter", () => {
    clearTimeout(hideTimeout);
  });

  popover.addEventListener("mouseleave", () => {
    hideTimeout = setTimeout(() => {
      popover.style.display = "none";
    }, 200);
  });

  // Click to open (for touch devices where hover doesn't work)
  wrapper.addEventListener("click", () => {
    clearTimeout(hideTimeout);
    popover.style.display = "block";
  });

  // Close on click/tap outside
  document.addEventListener("click", (e) => {
    if (!wrapper.contains(e.target)) {
      clearTimeout(hideTimeout);
      popover.style.display = "none";
    }
  });
}
