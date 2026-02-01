/**
 * linkAutocomplete.js Tests
 *
 * Tests for [page link] autocomplete functionality including context detection,
 * completion source behavior, and debounce functionality.
 */

import { describe, test, expect, afterEach, vi, beforeEach } from "vitest";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { autocompletion } from "@codemirror/autocomplete";

// Mock the csrf fetch
vi.mock("../../csrf.js", () => ({
  csrfFetch: vi.fn(),
}));

import { csrfFetch } from "../../csrf.js";
import { linkCompletionSource } from "../../linkAutocomplete.js";

describe("linkAutocomplete", () => {
  let view, parent;

  beforeEach(() => {
    // Set up mock for getCurrentPage
    window.getCurrentPage = () => ({ external_id: "current-page-id" });

    // Default mock for fetch
    csrfFetch.mockImplementation(async (url) => {
      if (url.includes("/pages/autocomplete/")) {
        return {
          ok: true,
          json: async () => ({
            pages: [
              { external_id: "page1", title: "First Page" },
              { external_id: "page2", title: "Second Page" },
              { external_id: "page3", title: "Third Page" },
            ],
          }),
        };
      }
      return { ok: false };
    });
  });

  afterEach(() => {
    if (view) view.destroy();
    if (parent) parent.remove();
    view = null;
    parent = null;
    vi.clearAllMocks();
    delete window.getCurrentPage;
  });

  function createEditor(content) {
    const state = EditorState.create({
      doc: content,
      extensions: [
        autocompletion({
          override: [linkCompletionSource],
          activateOnTyping: true,
        }),
      ],
    });

    parent = document.createElement("div");
    parent.style.width = "800px";
    parent.style.height = "400px";
    document.body.appendChild(parent);

    view = new EditorView({ state, parent });
    return view;
  }

  describe("Context detection", () => {
    test("detects [ for starting a link", async () => {
      createEditor("[test");
      view.dispatch({ selection: { anchor: 5 } });

      const context = {
        state: view.state,
        pos: view.state.selection.main.head,
        explicit: false,
      };

      const result = await linkCompletionSource(context);
      expect(result).not.toBeNull();
      expect(result.from).toBe(1);
      expect(result.to).toBe(5);
    });

    test("detects [text]( for URL completion", async () => {
      createEditor("[Test Page](");
      view.dispatch({ selection: { anchor: 12 } });

      const context = {
        state: view.state,
        pos: view.state.selection.main.head,
        explicit: false,
      };

      const result = await linkCompletionSource(context);
      expect(result).not.toBeNull();
    });

    test("does not trigger without [", async () => {
      createEditor("Hello world");
      view.dispatch({ selection: { anchor: 5 } });

      const context = {
        state: view.state,
        pos: view.state.selection.main.head,
        explicit: false,
      };

      const result = await linkCompletionSource(context);
      expect(result).toBeNull();
    });
  });

  describe("API interaction", () => {
    test("fetches pages from autocomplete endpoint", async () => {
      createEditor("[test");
      view.dispatch({ selection: { anchor: 5 } });

      const context = {
        state: view.state,
        pos: view.state.selection.main.head,
        explicit: false,
      };

      await linkCompletionSource(context);

      expect(csrfFetch).toHaveBeenCalledWith(expect.stringContaining("/api/pages/autocomplete/"));
    });

    test("passes query parameter to API", async () => {
      createEditor("[myquery");
      view.dispatch({ selection: { anchor: 8 } });

      const context = {
        state: view.state,
        pos: view.state.selection.main.head,
        explicit: false,
      };

      await linkCompletionSource(context);

      expect(csrfFetch).toHaveBeenCalledWith(expect.stringContaining("q=myquery"));
    });

    test("handles API error gracefully", async () => {
      csrfFetch.mockRejectedValueOnce(new Error("Network error"));

      createEditor("[errortest");
      view.dispatch({ selection: { anchor: 10 } });

      const context = {
        state: view.state,
        pos: view.state.selection.main.head,
        explicit: false,
      };

      const result = await linkCompletionSource(context);
      expect(result).toBeNull();
    });

    test("handles non-ok response gracefully", async () => {
      csrfFetch.mockImplementation(async () => ({ ok: false }));

      createEditor("[failtest");
      view.dispatch({ selection: { anchor: 9 } });

      const context = {
        state: view.state,
        pos: view.state.selection.main.head,
        explicit: false,
      };

      const result = await linkCompletionSource(context);
      expect(result).toBeNull();
    });
  });

  describe("Completion options", () => {
    test("returns options with page title as label", async () => {
      createEditor("[first");
      view.dispatch({ selection: { anchor: 6 } });

      const context = {
        state: view.state,
        pos: view.state.selection.main.head,
        explicit: false,
      };

      const result = await linkCompletionSource(context);
      expect(result.options.length).toBe(3);
      expect(result.options[0].label).toBe("First Page");
      expect(result.options[1].label).toBe("Second Page");
      expect(result.options[2].label).toBe("Third Page");
    });

    test("options have type=link", async () => {
      createEditor("[linktype");
      view.dispatch({ selection: { anchor: 9 } });

      const context = {
        state: view.state,
        pos: view.state.selection.main.head,
        explicit: false,
      };

      const result = await linkCompletionSource(context);
      expect(result.options[0].type).toBe("link");
    });

    test("excludes current page from options", async () => {
      // Mock to return pages including current-page-id
      csrfFetch.mockImplementation(async () => ({
        ok: true,
        json: async () => ({
          pages: [
            { external_id: "current-page-id", title: "Current Page" },
            { external_id: "other-page", title: "Other Page" },
          ],
        }),
      }));

      createEditor("[exclude");
      view.dispatch({ selection: { anchor: 8 } });

      const context = {
        state: view.state,
        pos: view.state.selection.main.head,
        explicit: false,
      };

      const result = await linkCompletionSource(context);
      expect(result.options.length).toBe(1);
      expect(result.options[0].label).toBe("Other Page");
    });

    test("returns null when no pages found", async () => {
      csrfFetch.mockImplementation(async () => ({
        ok: true,
        json: async () => ({ pages: [] }),
      }));

      createEditor("[nopages");
      view.dispatch({ selection: { anchor: 8 } });

      const context = {
        state: view.state,
        pos: view.state.selection.main.head,
        explicit: false,
      };

      const result = await linkCompletionSource(context);
      expect(result).toBeNull();
    });
  });

  describe("Debounce behavior", () => {
    beforeEach(() => {
      vi.useFakeTimers();
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    test("debounces API calls - does not fetch immediately", async () => {
      createEditor("[debounce1");
      view.dispatch({ selection: { anchor: 10 } });

      const context = {
        state: view.state,
        pos: view.state.selection.main.head,
        explicit: false,
      };

      // Start the completion source but don't await yet
      const promise = linkCompletionSource(context);

      // Check immediately - fetch should not have been called yet
      expect(csrfFetch).not.toHaveBeenCalled();

      // Advance timers past the debounce delay
      await vi.advanceTimersByTimeAsync(200);

      // Now await the result
      await promise;

      // Now fetch should have been called
      expect(csrfFetch).toHaveBeenCalledTimes(1);
    });

    test("debounces API calls - cancels pending fetch on new query", async () => {
      // First query
      createEditor("[debounce2a");
      view.dispatch({ selection: { anchor: 11 } });

      const context1 = {
        state: view.state,
        pos: view.state.selection.main.head,
        explicit: false,
      };

      // Start first completion source - don't await it
      linkCompletionSource(context1);

      // Check no fetch happened yet
      expect(csrfFetch).not.toHaveBeenCalled();

      // Don't wait for debounce to complete - simulate rapid typing
      await vi.advanceTimersByTimeAsync(50);

      // Still no fetch
      expect(csrfFetch).not.toHaveBeenCalled();

      // Second query before first debounce fires - this should cancel first
      view.destroy();
      parent.remove();
      view = createEditor("[debounce2b");
      parent = view.dom.parentElement;
      view.dispatch({ selection: { anchor: 11 } });

      const context2 = {
        state: view.state,
        pos: view.state.selection.main.head,
        explicit: false,
      };

      const promise2 = linkCompletionSource(context2);

      // Advance timers to let second debounce complete
      await vi.advanceTimersByTimeAsync(200);

      // Await second promise
      await promise2;

      // Only the second query should result in a fetch (first was cancelled)
      expect(csrfFetch).toHaveBeenCalledTimes(1);
      expect(csrfFetch).toHaveBeenCalledWith(expect.stringContaining("q=debounce2b"));
    });

    test("uses 150ms debounce delay", async () => {
      createEditor("[debounce3");
      view.dispatch({ selection: { anchor: 10 } });

      const context = {
        state: view.state,
        pos: view.state.selection.main.head,
        explicit: false,
      };

      const promise = linkCompletionSource(context);

      // At 100ms, should not have fetched yet
      await vi.advanceTimersByTimeAsync(100);
      expect(csrfFetch).not.toHaveBeenCalled();

      // At 150ms, should have fetched
      await vi.advanceTimersByTimeAsync(50);
      await promise;
      expect(csrfFetch).toHaveBeenCalledTimes(1);
    });
  });

  describe("Caching", () => {
    test("caches pages and reuses on same query", async () => {
      vi.useFakeTimers();

      // Use unique query for this test
      createEditor("[cachelink1");
      view.dispatch({ selection: { anchor: 11 } });

      // Clear call history
      csrfFetch.mockClear();

      const context = {
        state: view.state,
        pos: view.state.selection.main.head,
        explicit: false,
      };

      // First call - should fetch
      const promise1 = linkCompletionSource(context);
      await vi.advanceTimersByTimeAsync(200);
      await promise1;
      expect(csrfFetch).toHaveBeenCalledTimes(1);

      // Second call with same query - should use cache
      const context2 = {
        state: view.state,
        pos: view.state.selection.main.head,
        explicit: false,
      };

      const result = await linkCompletionSource(context2);
      // Should still be 1 because query didn't change
      expect(csrfFetch).toHaveBeenCalledTimes(1);
      expect(result).not.toBeNull();

      vi.useRealTimers();
    });

    test("fetches new data when query changes", async () => {
      vi.useFakeTimers();

      // Clear call history
      csrfFetch.mockClear();

      // First query
      view = createEditor("[cachelink2a");
      view.dispatch({ selection: { anchor: 12 } });

      const promise1 = linkCompletionSource({
        state: view.state,
        pos: view.state.selection.main.head,
        explicit: false,
      });
      await vi.advanceTimersByTimeAsync(200);
      await promise1;

      expect(csrfFetch).toHaveBeenCalledTimes(1);

      // Change to different query
      view.destroy();
      parent.remove();
      view = createEditor("[cachelink2b");
      parent = view.dom.parentElement;
      view.dispatch({ selection: { anchor: 12 } });

      const promise2 = linkCompletionSource({
        state: view.state,
        pos: view.state.selection.main.head,
        explicit: false,
      });
      await vi.advanceTimersByTimeAsync(200);
      await promise2;

      expect(csrfFetch).toHaveBeenCalledTimes(2);

      vi.useRealTimers();
    });
  });
});
