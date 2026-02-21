/**
 * presence.js Tests
 *
 * Tests for presence UI rendering, specifically verifying that user-controlled
 * data (names, colors) from Yjs awareness state is safely rendered into the DOM
 * without XSS vulnerabilities.
 */

import { describe, test, expect, beforeEach, afterEach } from "vitest";
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
 * Create the DOM elements that setupPresenceUI expects.
 */
function createPresenceDOM() {
  const indicator = document.createElement("div");
  indicator.id = "presence-indicator";

  const popover = document.createElement("div");
  popover.id = "presence-popover";

  const userCount = document.createElement("span");
  userCount.id = "user-count";

  const presenceList = document.createElement("div");
  presenceList.id = "presence-list";

  indicator.appendChild(userCount);
  popover.appendChild(presenceList);
  indicator.appendChild(popover);
  document.body.appendChild(indicator);

  return { indicator, popover, userCount, presenceList };
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
  });
});
