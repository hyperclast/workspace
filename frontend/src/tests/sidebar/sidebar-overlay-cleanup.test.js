/**
 * Sidebar Overlay Event Listener Cleanup Tests
 *
 * Verifies that the Sidebar.svelte component properly cleans up all event
 * listeners when unmounted. This guards against a regression where anonymous
 * arrow functions were used with addEventListener/removeEventListener, making
 * the removal a no-op (since removeEventListener requires the same function
 * reference that was passed to addEventListener).
 *
 * See: issue 18.1 / 7.1 in CLAUDE.current_master.md
 */

import { describe, test, expect, vi, beforeEach, afterEach } from "vitest";
import { readFileSync } from "fs";
import { resolve } from "path";

describe("Sidebar overlay listener cleanup", () => {
  describe("Source-level pattern verification", () => {
    const sidebarSource = readFileSync(
      resolve(__dirname, "../../lib/components/Sidebar.svelte"),
      "utf-8"
    );

    test("does not use anonymous functions in addEventListener", () => {
      // Match addEventListener("click", () => ...) pattern — the bug was using
      // an inline arrow instead of a named reference
      const anonymousListenerPattern = /addEventListener\(\s*"click"\s*,\s*\(\)\s*=>/g;
      const matches = sidebarSource.match(anonymousListenerPattern);
      expect(matches).toBeNull();
    });

    test("does not use anonymous functions in removeEventListener", () => {
      const anonymousRemovePattern = /removeEventListener\(\s*"click"\s*,\s*\(\)\s*=>/g;
      const matches = sidebarSource.match(anonymousRemovePattern);
      expect(matches).toBeNull();
    });

    test("all addEventListener calls have matching removeEventListener calls", () => {
      // Extract all named handler variables used in addEventListener
      const addPattern = /addEventListener\(\s*"(\w+)"\s*,\s*(\w+)/g;
      const removePattern = /removeEventListener\(\s*"(\w+)"\s*,\s*(\w+)/g;

      const added = [];
      let match;
      while ((match = addPattern.exec(sidebarSource)) !== null) {
        added.push({ event: match[1], handler: match[2] });
      }

      const removed = [];
      while ((match = removePattern.exec(sidebarSource)) !== null) {
        removed.push({ event: match[1], handler: match[2] });
      }

      // Every addEventListener should have a matching removeEventListener
      // with the same event type and handler name
      for (const { event, handler } of added) {
        const hasMatch = removed.some((r) => r.event === event && r.handler === handler);
        expect(
          hasMatch,
          `addEventListener("${event}", ${handler}) has no matching removeEventListener`
        ).toBe(true);
      }
    });
  });

  describe("DOM-level listener lifecycle", () => {
    let overlay;
    let addSpy;
    let removeSpy;

    beforeEach(() => {
      overlay = document.createElement("div");
      overlay.id = "chat-overlay";
      document.body.appendChild(overlay);
      addSpy = vi.spyOn(overlay, "addEventListener");
      removeSpy = vi.spyOn(overlay, "removeEventListener");
    });

    afterEach(() => {
      overlay.remove();
      vi.restoreAllMocks();
    });

    test("removeEventListener receives the same function reference as addEventListener", () => {
      // Simulate the fixed pattern from Sidebar.svelte onMount
      const closeSidebar = vi.fn();
      const handleOverlayClick = () => closeSidebar();

      overlay.addEventListener("click", handleOverlayClick);
      overlay.removeEventListener("click", handleOverlayClick);

      // Both calls should use the exact same function reference
      const addedFn = addSpy.mock.calls[0][1];
      const removedFn = removeSpy.mock.calls[0][1];
      expect(addedFn).toBe(removedFn);
    });

    test("listener is actually removed after cleanup", () => {
      const closeSidebar = vi.fn();
      const handleOverlayClick = () => closeSidebar();

      overlay.addEventListener("click", handleOverlayClick);

      // Click should fire the handler
      overlay.click();
      expect(closeSidebar).toHaveBeenCalledTimes(1);

      // After removal, click should NOT fire the handler
      overlay.removeEventListener("click", handleOverlayClick);
      overlay.click();
      expect(closeSidebar).toHaveBeenCalledTimes(1); // still 1, not 2
    });

    test("anonymous arrow functions fail to remove (documents the original bug)", () => {
      const closeSidebar = vi.fn();

      // This is the OLD buggy pattern — two different anonymous arrows
      overlay.addEventListener("click", () => closeSidebar());
      overlay.removeEventListener("click", () => closeSidebar());

      // The listener is still attached because the function references differ
      overlay.click();
      expect(closeSidebar).toHaveBeenCalledTimes(1); // leaked!
    });
  });
});
