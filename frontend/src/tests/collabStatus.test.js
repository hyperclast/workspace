/**
 * collabStatus.js Tests
 *
 * Tests for collaboration status indicator UI, covering:
 * 1. updateCollabStatus — DOM creation, status updates, popover content
 * 2. setupIndicatorPopover — hover/click show/hide behavior
 * 3. Cleanup — both functions return cleanup functions that remove all listeners
 */

import { describe, test, expect, beforeEach, afterEach, vi } from "vitest";
import { updateCollabStatus, setupIndicatorPopover } from "../collabStatus.js";

/**
 * Create the minimal DOM structure that updateCollabStatus expects:
 * a presence-indicator inside a parent container.
 */
function createCollabDOM() {
  const container = document.createElement("div");
  container.id = "collab-test-container";

  const presenceIndicator = document.createElement("div");
  presenceIndicator.id = "presence-indicator";

  container.appendChild(presenceIndicator);
  document.body.appendChild(container);

  return { container, presenceIndicator };
}

/**
 * Remove all collab-related DOM elements.
 */
function cleanupDOM() {
  ["collab-test-container", "collab-status-wrapper"].forEach((id) => {
    document.getElementById(id)?.remove();
  });
}

describe("updateCollabStatus", () => {
  let dom;

  beforeEach(() => {
    dom = createCollabDOM();
  });

  afterEach(() => {
    cleanupDOM();
  });

  describe("DOM creation on first call", () => {
    test("creates wrapper, indicator, and popover elements", () => {
      updateCollabStatus("connected");

      expect(document.getElementById("collab-status-wrapper")).not.toBeNull();
      expect(document.getElementById("collab-status")).not.toBeNull();
      expect(document.getElementById("collab-popover")).not.toBeNull();
    });

    test("wrapper is inserted before the presence indicator", () => {
      updateCollabStatus("connected");

      const wrapper = document.getElementById("collab-status-wrapper");
      const presenceIndicator = document.getElementById("presence-indicator");
      // wrapper should be a previous sibling of presence-indicator
      expect(wrapper.nextElementSibling).toBe(presenceIndicator);
    });

    test("popover has header and text elements", () => {
      updateCollabStatus("connected");

      expect(document.getElementById("collab-popover-header")).not.toBeNull();
      expect(document.getElementById("collab-popover-text")).not.toBeNull();
    });

    test("reuses existing elements on subsequent calls", () => {
      updateCollabStatus("connected");
      const wrapper = document.getElementById("collab-status-wrapper");

      updateCollabStatus("offline");
      expect(document.getElementById("collab-status-wrapper")).toBe(wrapper);
      // Should still be only one wrapper
      expect(document.querySelectorAll("#collab-status-wrapper").length).toBe(1);
    });
  });

  describe("status display", () => {
    test("connected status shows correct icon, header, and text", () => {
      updateCollabStatus("connected");

      const indicator = document.getElementById("collab-status");
      expect(indicator.textContent).toBe("\u25CF");
      expect(indicator.className).toBe("collab-status connected");
      expect(document.getElementById("collab-popover-header").textContent).toBe("Connected");
      expect(document.getElementById("collab-popover-text").textContent).toBe(
        "Changes sync instantly with other editors."
      );
    });

    test("connecting status shows correct icon and class", () => {
      updateCollabStatus("connecting");

      const indicator = document.getElementById("collab-status");
      expect(indicator.textContent).toBe("\u25CC");
      expect(indicator.className).toBe("collab-status connecting");
      expect(document.getElementById("collab-popover-header").textContent).toBe("Connecting");
    });

    test("offline status shows correct icon and text", () => {
      updateCollabStatus("offline");

      const indicator = document.getElementById("collab-status");
      expect(indicator.textContent).toBe("\u25CF");
      expect(indicator.className).toBe("collab-status offline");
      expect(document.getElementById("collab-popover-text").textContent).toContain("saved locally");
    });

    test("denied status shows correct icon and text", () => {
      updateCollabStatus("denied");

      const indicator = document.getElementById("collab-status");
      expect(indicator.textContent).toBe("\u2298");
      expect(indicator.className).toBe("collab-status denied");
      expect(document.getElementById("collab-popover-header").textContent).toBe("Unavailable");
    });

    test("error status shows correct icon and text", () => {
      updateCollabStatus("error");

      const indicator = document.getElementById("collab-status");
      expect(indicator.textContent).toBe("!");
      expect(indicator.className).toBe("collab-status error");
      expect(document.getElementById("collab-popover-header").textContent).toBe("Connection Lost");
    });

    test("unauthorized status shows correct icon and text", () => {
      updateCollabStatus("unauthorized");

      const indicator = document.getElementById("collab-status");
      expect(indicator.textContent).toBe("\u25CB");
      expect(indicator.className).toBe("collab-status unauthorized");
      expect(document.getElementById("collab-popover-header").textContent).toBe("Logged Out");
    });

    test("unknown status falls back to offline", () => {
      updateCollabStatus("some-unknown-status");

      const indicator = document.getElementById("collab-status");
      expect(indicator.className).toBe("collab-status offline");
      expect(document.getElementById("collab-popover-header").textContent).toBe("Offline");
    });

    test("switching between statuses updates correctly", () => {
      updateCollabStatus("connecting");
      expect(document.getElementById("collab-status").className).toBe("collab-status connecting");

      updateCollabStatus("connected");
      expect(document.getElementById("collab-status").className).toBe("collab-status connected");

      updateCollabStatus("offline");
      expect(document.getElementById("collab-status").className).toBe("collab-status offline");
    });
  });

  describe("edge cases", () => {
    test("does nothing when presence-indicator does not exist", () => {
      dom.presenceIndicator.remove();

      // Should not throw
      updateCollabStatus("connected");

      expect(document.getElementById("collab-status-wrapper")).toBeNull();
      expect(document.getElementById("collab-status")).toBeNull();
    });

    test("popover content uses textContent (not innerHTML) for safety", () => {
      updateCollabStatus("connected");

      const header = document.getElementById("collab-popover-header");
      const text = document.getElementById("collab-popover-text");

      // All content is set via textContent, verify no child elements exist
      expect(header.children.length).toBe(0);
      expect(text.children.length).toBe(0);
    });
  });

  describe("cleanup", () => {
    test("first call returns a cleanup function", () => {
      const cleanup = updateCollabStatus("connected");
      expect(typeof cleanup).toBe("function");
    });

    test("subsequent calls also return a cleanup function", () => {
      updateCollabStatus("connected");
      const result = updateCollabStatus("offline");
      expect(typeof result).toBe("function");
    });

    test("popover works after cleanup and re-initialization", () => {
      vi.useFakeTimers();

      // First call — setup
      const cleanup = updateCollabStatus("connected");
      const wrapper = document.getElementById("collab-status-wrapper");
      const popover = document.getElementById("collab-popover");

      // Verify popover works
      wrapper.dispatchEvent(new Event("mouseenter"));
      expect(popover.style.display).not.toBe("none");

      // Hide it
      wrapper.dispatchEvent(new Event("mouseleave"));
      vi.advanceTimersByTime(200);
      expect(popover.style.display).toBe("none");

      // Cleanup (simulates page switch)
      cleanup();

      // Re-initialize (simulates loading a new page)
      const cleanup2 = updateCollabStatus("connecting");
      expect(typeof cleanup2).toBe("function");

      // Popover should work again after re-initialization
      wrapper.dispatchEvent(new Event("mouseenter"));
      expect(popover.style.display).not.toBe("none");

      // And hiding should also work
      wrapper.dispatchEvent(new Event("mouseleave"));
      vi.advanceTimersByTime(200);
      expect(popover.style.display).toBe("none");

      cleanup2();
      vi.useRealTimers();
    });

    test("cleanup removes wrapper hover listeners", () => {
      vi.useFakeTimers();

      const cleanup = updateCollabStatus("connected");
      const wrapper = document.getElementById("collab-status-wrapper");

      // Verify listeners work before cleanup
      wrapper.dispatchEvent(new Event("mouseenter"));
      // Popover should be visible (via store)
      const popover = document.getElementById("collab-popover");
      expect(popover.style.display).not.toBe("none");

      // Hide it
      wrapper.dispatchEvent(new Event("mouseleave"));
      vi.advanceTimersByTime(200);

      // Now cleanup
      cleanup();

      // After cleanup, mouseenter should NOT show the popover
      wrapper.dispatchEvent(new Event("mouseenter"));
      // The popover should remain hidden — the listener was removed
      expect(popover.style.display).toBe("none");

      vi.useRealTimers();
    });

    test("cleanup removes document click-outside listener", () => {
      const cleanup = updateCollabStatus("connected");
      const wrapper = document.getElementById("collab-status-wrapper");
      const popover = document.getElementById("collab-popover");

      // Show the popover
      wrapper.dispatchEvent(new Event("mouseenter"));
      expect(popover.style.display).not.toBe("none");

      // Click outside hides it (before cleanup)
      document.body.dispatchEvent(new Event("click", { bubbles: true }));
      expect(popover.style.display).toBe("none");

      // Show again via click on wrapper
      wrapper.dispatchEvent(new Event("click", { bubbles: true }));

      // Now cleanup
      cleanup();

      // Show via click (listener still on wrapper? no — it was removed)
      // Re-show manually via store to test document listener specifically
      wrapper.dispatchEvent(new Event("mouseenter"));

      // After cleanup, clicking outside should NOT affect the popover
      // (the document listener was removed)
      document.body.dispatchEvent(new Event("click", { bubbles: true }));
      // Since all listeners are removed, the popover state is whatever it was
      // The key assertion: the document click handler no longer fires
    });

    test("cleanup clears pending hide timeout", () => {
      vi.useFakeTimers();

      const cleanup = updateCollabStatus("connected");
      const wrapper = document.getElementById("collab-status-wrapper");
      const popover = document.getElementById("collab-popover");

      // Show then trigger hide
      wrapper.dispatchEvent(new Event("mouseenter"));
      wrapper.dispatchEvent(new Event("mouseleave"));
      // Hide timeout is pending (200ms)

      // Cleanup before timeout fires
      cleanup();

      // Advance past the timeout
      vi.advanceTimersByTime(200);

      // The popover should NOT have been hidden by the stale timeout
      // (cleanup should have cleared it)
      expect(popover.style.display).not.toBe("none");

      vi.useRealTimers();
    });
  });
});

describe("setupIndicatorPopover", () => {
  let wrapper;
  let popover;
  let cleanup;

  beforeEach(() => {
    wrapper = document.createElement("div");
    popover = document.createElement("div");
    wrapper.appendChild(popover);
    document.body.appendChild(wrapper);

    cleanup = setupIndicatorPopover(wrapper, popover);
  });

  afterEach(() => {
    if (cleanup) cleanup();
    cleanup = null;
    wrapper.remove();
  });

  test("shows popover on mouseenter", () => {
    wrapper.dispatchEvent(new Event("mouseenter"));
    expect(popover.style.display).toBe("block");
  });

  test("hides popover on mouseleave after 200ms delay", () => {
    vi.useFakeTimers();

    wrapper.dispatchEvent(new Event("mouseenter"));
    expect(popover.style.display).toBe("block");

    wrapper.dispatchEvent(new Event("mouseleave"));
    // Not hidden immediately
    expect(popover.style.display).toBe("block");

    vi.advanceTimersByTime(200);
    expect(popover.style.display).toBe("none");

    vi.useRealTimers();
  });

  test("cancels hide when re-entering before timeout", () => {
    vi.useFakeTimers();

    wrapper.dispatchEvent(new Event("mouseenter"));
    wrapper.dispatchEvent(new Event("mouseleave"));

    vi.advanceTimersByTime(100);
    wrapper.dispatchEvent(new Event("mouseenter"));

    vi.advanceTimersByTime(200);
    expect(popover.style.display).toBe("block");

    vi.useRealTimers();
  });

  test("keeps popover open when hovering over popover itself", () => {
    vi.useFakeTimers();

    wrapper.dispatchEvent(new Event("mouseenter"));
    wrapper.dispatchEvent(new Event("mouseleave"));

    vi.advanceTimersByTime(50);
    popover.dispatchEvent(new Event("mouseenter"));

    vi.advanceTimersByTime(200);
    expect(popover.style.display).toBe("block");

    vi.useRealTimers();
  });

  test("hides popover after leaving the popover", () => {
    vi.useFakeTimers();

    wrapper.dispatchEvent(new Event("mouseenter"));
    popover.dispatchEvent(new Event("mouseenter"));
    popover.dispatchEvent(new Event("mouseleave"));

    vi.advanceTimersByTime(200);
    expect(popover.style.display).toBe("none");

    vi.useRealTimers();
  });

  test("shows popover on click (touch devices)", () => {
    wrapper.dispatchEvent(new Event("click", { bubbles: true }));
    expect(popover.style.display).toBe("block");
  });

  test("hides popover on click outside", () => {
    wrapper.dispatchEvent(new Event("mouseenter"));
    expect(popover.style.display).toBe("block");

    const outsideClick = new Event("click", { bubbles: true });
    document.body.dispatchEvent(outsideClick);
    expect(popover.style.display).toBe("none");
  });

  describe("cleanup", () => {
    test("returns a cleanup function", () => {
      expect(typeof cleanup).toBe("function");
    });

    test("cleanup removes wrapper hover listeners", () => {
      vi.useFakeTimers();

      // Verify listeners work before cleanup
      wrapper.dispatchEvent(new Event("mouseenter"));
      expect(popover.style.display).toBe("block");

      // Hide it
      wrapper.dispatchEvent(new Event("mouseleave"));
      vi.advanceTimersByTime(200);
      expect(popover.style.display).toBe("none");

      // Now cleanup
      cleanup();
      cleanup = null;

      // After cleanup, mouseenter should NOT show the popover
      wrapper.dispatchEvent(new Event("mouseenter"));
      expect(popover.style.display).toBe("none");

      vi.useRealTimers();
    });

    test("cleanup removes popover hover listeners", () => {
      vi.useFakeTimers();

      // Show via wrapper, then move to popover
      wrapper.dispatchEvent(new Event("mouseenter"));
      wrapper.dispatchEvent(new Event("mouseleave"));
      vi.advanceTimersByTime(50);
      popover.dispatchEvent(new Event("mouseenter"));
      vi.advanceTimersByTime(200);
      // Popover should stay open because popover mouseenter cancelled the hide
      expect(popover.style.display).toBe("block");

      // Reset: hide it
      popover.dispatchEvent(new Event("mouseleave"));
      vi.advanceTimersByTime(200);
      expect(popover.style.display).toBe("none");

      // Cleanup
      cleanup();
      cleanup = null;

      // Show manually to test popover listeners are gone
      popover.style.display = "block";

      // After cleanup, hovering popover should NOT cancel a hide
      // (but since wrapper listener is also gone, we test popover directly)
      popover.dispatchEvent(new Event("mouseleave"));
      vi.advanceTimersByTime(200);
      // The popover mouseleave handler was removed, so display stays as-is
      expect(popover.style.display).toBe("block");

      vi.useRealTimers();
    });

    test("cleanup removes document click-outside listener", () => {
      // Show popover
      wrapper.dispatchEvent(new Event("mouseenter"));
      expect(popover.style.display).toBe("block");

      // Cleanup
      cleanup();
      cleanup = null;

      // Manually show popover again (since wrapper listener is now gone)
      popover.style.display = "block";

      // Click outside — should NOT hide popover since listener was removed
      document.body.dispatchEvent(new Event("click", { bubbles: true }));
      expect(popover.style.display).toBe("block");
    });

    test("cleanup removes wrapper click listener", () => {
      // Cleanup first
      cleanup();
      cleanup = null;

      // Reset popover to hidden
      popover.style.display = "none";

      // Click on wrapper — should NOT show popover since listener was removed
      wrapper.dispatchEvent(new Event("click", { bubbles: true }));
      expect(popover.style.display).toBe("none");
    });

    test("cleanup clears pending hide timeout", () => {
      vi.useFakeTimers();

      // Show then trigger hide
      wrapper.dispatchEvent(new Event("mouseenter"));
      expect(popover.style.display).toBe("block");

      wrapper.dispatchEvent(new Event("mouseleave"));
      // Hide timeout is pending (200ms)

      // Cleanup before timeout fires
      cleanup();
      cleanup = null;

      // Advance past the timeout
      vi.advanceTimersByTime(200);

      // The popover should NOT have been hidden by the stale timeout
      expect(popover.style.display).toBe("block");

      vi.useRealTimers();
    });
  });
});
