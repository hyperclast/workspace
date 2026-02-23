/**
 * collabStatus.js Tests
 *
 * Tests for collaboration status indicator UI, covering:
 * 1. updateCollabStatus — DOM creation, status updates, popover content
 * 2. setupIndicatorPopover — hover/click show/hide behavior
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
});

describe("setupIndicatorPopover", () => {
  let wrapper;
  let popover;

  beforeEach(() => {
    wrapper = document.createElement("div");
    popover = document.createElement("div");
    wrapper.appendChild(popover);
    document.body.appendChild(wrapper);

    setupIndicatorPopover(wrapper, popover);
  });

  afterEach(() => {
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
});
