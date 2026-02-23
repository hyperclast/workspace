/**
 * presence.js Tests
 *
 * Tests for presence UI rendering, specifically verifying that user-controlled
 * data (names, colors) from Yjs awareness state is safely rendered into the DOM
 * without XSS vulnerabilities.
 */

import { describe, test, expect, beforeEach, afterEach, vi } from "vitest";
import { setupPresenceUI } from "../presence.js";

/**
 * Minimal mock of Yjs awareness API surface used by setupPresenceUI.
 */
function createMockAwareness(users = []) {
  const listeners = new Map();
  const states = new Map();

  users.forEach((user, i) => {
    states.set(i, { user });
  });

  return {
    getStates: () => states,
    on: (event, fn) => {
      if (!listeners.has(event)) listeners.set(event, []);
      listeners.get(event).push(fn);
    },
    off: (event, fn) => {
      const fns = listeners.get(event) || [];
      listeners.set(
        event,
        fns.filter((f) => f !== fn)
      );
    },
    /** Simulate an awareness change to trigger UI update */
    _setUsers: (newUsers) => {
      states.clear();
      newUsers.forEach((user, i) => {
        states.set(i, { user });
      });
      (listeners.get("change") || []).forEach((fn) => fn());
    },
  };
}

/**
 * Create the mount target that setupPresenceUI expects.
 * Child elements (#user-count, #presence-popover, #presence-list)
 * are created by the Svelte component after mount, so we return
 * getters that query the DOM fresh each time.
 */
function createPresenceDOM() {
  const indicator = document.createElement("div");
  indicator.id = "presence-indicator";
  document.body.appendChild(indicator);

  return {
    indicator,
    get popover() {
      return document.getElementById("presence-popover");
    },
    get userCount() {
      return document.getElementById("user-count");
    },
    get presenceList() {
      return document.getElementById("presence-list");
    },
  };
}

describe("presence UI", () => {
  let dom;
  let cleanup;

  beforeEach(() => {
    dom = createPresenceDOM();
  });

  afterEach(() => {
    if (cleanup) cleanup();
    cleanup = null;
    dom.indicator.remove();
  });

  describe("XSS prevention in user names", () => {
    test("script tag in user name is not rendered as HTML", () => {
      const awareness = createMockAwareness([
        { name: "<script>alert('xss')</script>", color: "#f00" },
      ]);
      cleanup = setupPresenceUI(awareness);

      // The script tag must not appear as an actual element
      expect(dom.presenceList.querySelector("script")).toBeNull();
      // The text content should contain the literal string
      expect(dom.presenceList.textContent).toContain("<script>");
    });

    test("img onerror payload in user name is not rendered as HTML", () => {
      const awareness = createMockAwareness([
        { name: "<img src=x onerror=\"alert('xss')\">", color: "#f00" },
      ]);
      cleanup = setupPresenceUI(awareness);

      expect(dom.presenceList.querySelector("img")).toBeNull();
      expect(dom.presenceList.textContent).toContain("<img");
    });

    test("event handler attribute in user name is not rendered as HTML", () => {
      const awareness = createMockAwareness([
        { name: '<div onmouseover="alert(1)">hover</div>', color: "#f00" },
      ]);
      cleanup = setupPresenceUI(awareness);

      // Should not create a div with an event handler
      const innerDivs = dom.presenceList.querySelectorAll("div");
      innerDivs.forEach((div) => {
        expect(div.getAttribute("onmouseover")).toBeNull();
      });
    });

    test("HTML entities in user name are displayed as literal text", () => {
      const awareness = createMockAwareness([{ name: "Alice & Bob <Team>", color: "#0f0" }]);
      cleanup = setupPresenceUI(awareness);

      expect(dom.presenceList.textContent).toContain("Alice & Bob <Team>");
    });

    test("XSS payload in name is neutralized after awareness update", () => {
      const awareness = createMockAwareness([{ name: "Safe Name", color: "#0f0" }]);
      cleanup = setupPresenceUI(awareness);

      // Initially safe
      expect(dom.presenceList.textContent).toContain("Safe Name");

      // Simulate a user changing their name to an XSS payload
      awareness._setUsers([{ name: "<script>alert('xss')</script>", color: "#f00" }]);

      expect(dom.presenceList.querySelector("script")).toBeNull();
      expect(dom.presenceList.textContent).toContain("<script>");
    });
  });

  describe("XSS prevention in user colors", () => {
    test("CSS injection via color value is not possible", () => {
      // Attempt to break out of background-color and inject arbitrary styles/HTML
      const maliciousColor = 'red" onclick="alert(1)" style="';
      const awareness = createMockAwareness([{ name: "User", color: maliciousColor }]);
      cleanup = setupPresenceUI(awareness);

      // The color div should not have an onclick handler
      const colorDivs = dom.presenceList.querySelectorAll(".presence-user-color");
      colorDivs.forEach((div) => {
        expect(div.getAttribute("onclick")).toBeNull();
      });
    });
  });

  describe("basic rendering", () => {
    test("renders correct user count for single user", () => {
      const awareness = createMockAwareness([{ name: "Alice", color: "#f00" }]);
      cleanup = setupPresenceUI(awareness);

      expect(dom.userCount.textContent).toBe("1 user editing");
    });

    test("renders correct user count for multiple users", () => {
      const awareness = createMockAwareness([
        { name: "Alice", color: "#f00" },
        { name: "Bob", color: "#0f0" },
      ]);
      cleanup = setupPresenceUI(awareness);

      expect(dom.userCount.textContent).toBe("2 users editing");
    });

    test("renders user names in presence list", () => {
      const awareness = createMockAwareness([
        { name: "Alice", color: "#f00" },
        { name: "Bob", color: "#0f0" },
      ]);
      cleanup = setupPresenceUI(awareness);

      expect(dom.presenceList.textContent).toContain("Alice");
      expect(dom.presenceList.textContent).toContain("Bob");
    });

    test("sets data-count attribute on user count span", () => {
      const awareness = createMockAwareness([
        { name: "Alice", color: "#f00" },
        { name: "Bob", color: "#0f0" },
        { name: "Charlie", color: "#00f" },
      ]);
      cleanup = setupPresenceUI(awareness);

      expect(dom.userCount.getAttribute("data-count")).toBe("3");
    });

    test("renders user color indicators with correct background", () => {
      const awareness = createMockAwareness([{ name: "Alice", color: "#ff0000" }]);
      cleanup = setupPresenceUI(awareness);

      const colorDiv = dom.presenceList.querySelector(".presence-user-color");
      expect(colorDiv).not.toBeNull();
      // jsdom may return the value as-is or normalized; check it was set
      expect(colorDiv.style.backgroundColor).toBe("#ff0000");
    });

    test("renders correct DOM structure for each user entry", () => {
      const awareness = createMockAwareness([{ name: "Alice", color: "#f00" }]);
      cleanup = setupPresenceUI(awareness);

      const userDiv = dom.presenceList.querySelector(".presence-user");
      expect(userDiv).not.toBeNull();
      expect(userDiv.querySelector(".presence-user-color")).not.toBeNull();
      expect(userDiv.querySelector("span")).not.toBeNull();
      expect(userDiv.querySelector("span").textContent).toBe("Alice");
    });
  });

  describe("edge cases", () => {
    test("defaults to 'Anonymous' when user name is missing", () => {
      const awareness = createMockAwareness([{ color: "#f00" }]);
      cleanup = setupPresenceUI(awareness);

      expect(dom.presenceList.textContent).toContain("Anonymous");
    });

    test("defaults to '#999' color when user color is missing", () => {
      const awareness = createMockAwareness([{ name: "Alice" }]);
      cleanup = setupPresenceUI(awareness);

      const colorDiv = dom.presenceList.querySelector(".presence-user-color");
      expect(colorDiv.style.backgroundColor).toBe("#999");
    });

    test("skips awareness states without a user property", () => {
      const awareness = createMockAwareness([]);
      // Manually add a state without .user
      awareness.getStates().set(99, { cursor: { line: 5 } });
      cleanup = setupPresenceUI(awareness);

      expect(dom.userCount.textContent).toBe("0 users editing");
      expect(dom.presenceList.children.length).toBe(0);
    });

    test("awareness update replaces previous list (does not append)", () => {
      const awareness = createMockAwareness([
        { name: "Alice", color: "#f00" },
        { name: "Bob", color: "#0f0" },
      ]);
      cleanup = setupPresenceUI(awareness);
      expect(dom.presenceList.querySelectorAll(".presence-user").length).toBe(2);

      // Update to a single user
      awareness._setUsers([{ name: "Charlie", color: "#00f" }]);
      expect(dom.presenceList.querySelectorAll(".presence-user").length).toBe(1);
      expect(dom.presenceList.textContent).toContain("Charlie");
      expect(dom.presenceList.textContent).not.toContain("Alice");
    });

    test("handles zero users", () => {
      const awareness = createMockAwareness([]);
      cleanup = setupPresenceUI(awareness);

      expect(dom.userCount.textContent).toBe("0 users editing");
      expect(dom.presenceList.children.length).toBe(0);
    });
  });

  describe("popover show/hide behavior", () => {
    test("shows popover on mouseenter", () => {
      const awareness = createMockAwareness([{ name: "Alice", color: "#f00" }]);
      cleanup = setupPresenceUI(awareness);

      dom.indicator.dispatchEvent(new Event("mouseenter"));
      expect(dom.popover.style.display).toBe("block");
    });

    test("hides popover on mouseleave after delay", () => {
      vi.useFakeTimers();
      const awareness = createMockAwareness([{ name: "Alice", color: "#f00" }]);
      cleanup = setupPresenceUI(awareness);

      // Show popover
      dom.indicator.dispatchEvent(new Event("mouseenter"));
      expect(dom.popover.style.display).toBe("block");

      // Start hiding
      dom.indicator.dispatchEvent(new Event("mouseleave"));
      // Should not hide immediately
      expect(dom.popover.style.display).toBe("block");

      // Advance past the 300ms timeout
      vi.advanceTimersByTime(300);
      expect(dom.popover.style.display).toBe("none");

      vi.useRealTimers();
    });

    test("cancels hide when re-entering indicator before timeout", () => {
      vi.useFakeTimers();
      const awareness = createMockAwareness([{ name: "Alice", color: "#f00" }]);
      cleanup = setupPresenceUI(awareness);

      dom.indicator.dispatchEvent(new Event("mouseenter"));
      dom.indicator.dispatchEvent(new Event("mouseleave"));

      // Re-enter before timeout fires
      vi.advanceTimersByTime(100);
      dom.indicator.dispatchEvent(new Event("mouseenter"));

      // Advance past original timeout
      vi.advanceTimersByTime(300);
      expect(dom.popover.style.display).toBe("block");

      vi.useRealTimers();
    });

    test("keeps popover open when hovering over the popover itself", () => {
      vi.useFakeTimers();
      const awareness = createMockAwareness([{ name: "Alice", color: "#f00" }]);
      cleanup = setupPresenceUI(awareness);

      dom.indicator.dispatchEvent(new Event("mouseenter"));
      dom.indicator.dispatchEvent(new Event("mouseleave"));

      // Mouse enters the popover before timeout
      vi.advanceTimersByTime(100);
      dom.popover.dispatchEvent(new Event("mouseenter"));

      vi.advanceTimersByTime(300);
      expect(dom.popover.style.display).toBe("block");

      vi.useRealTimers();
    });

    test("hides popover after leaving the popover", () => {
      vi.useFakeTimers();
      const awareness = createMockAwareness([{ name: "Alice", color: "#f00" }]);
      cleanup = setupPresenceUI(awareness);

      dom.indicator.dispatchEvent(new Event("mouseenter"));
      dom.popover.dispatchEvent(new Event("mouseenter"));
      dom.popover.dispatchEvent(new Event("mouseleave"));

      vi.advanceTimersByTime(300);
      expect(dom.popover.style.display).toBe("none");

      vi.useRealTimers();
    });

    test("shows popover on click (touch devices)", () => {
      const awareness = createMockAwareness([{ name: "Alice", color: "#f00" }]);
      cleanup = setupPresenceUI(awareness);

      dom.indicator.dispatchEvent(new Event("click", { bubbles: true }));
      expect(dom.popover.style.display).toBe("block");
    });

    test("hides popover on click outside", () => {
      const awareness = createMockAwareness([{ name: "Alice", color: "#f00" }]);
      cleanup = setupPresenceUI(awareness);

      // Open
      dom.indicator.dispatchEvent(new Event("mouseenter"));
      expect(dom.popover.style.display).toBe("block");

      // Click outside (on document body, not inside the indicator)
      const outsideClick = new Event("click", { bubbles: true });
      document.body.dispatchEvent(outsideClick);
      expect(dom.popover.style.display).toBe("none");
    });
  });

  describe("cleanup", () => {
    test("cleanup function removes awareness listener", () => {
      const awareness = createMockAwareness([{ name: "Alice", color: "#f00" }]);
      cleanup = setupPresenceUI(awareness);

      expect(dom.presenceList.textContent).toContain("Alice");

      // Call cleanup
      cleanup();

      // Awareness update should no longer affect the DOM
      awareness._setUsers([{ name: "Bob", color: "#0f0" }]);
      expect(dom.presenceList.textContent).toContain("Alice");
      expect(dom.presenceList.textContent).not.toContain("Bob");

      cleanup = null; // Prevent double-cleanup in afterEach
    });
  });
});
