/**
 * mentionAutocomplete.js Tests
 *
 * Tests for @mention autocomplete functionality including context detection
 * and completion source behavior.
 */

import { describe, test, expect, afterEach, vi, beforeEach } from "vitest";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { autocompletion, startCompletion } from "@codemirror/autocomplete";

// Mock the csrf fetch
vi.mock("../../csrf.js", () => ({
  csrfFetch: vi.fn(),
}));

import { csrfFetch } from "../../csrf.js";
import { mentionCompletionSource } from "../../mentionAutocomplete.js";

describe("mentionAutocomplete", () => {
  let view, parent;

  beforeEach(() => {
    // Set up mock projects on window
    window._cachedProjects = [
      {
        external_id: "proj1",
        name: "Test Project",
        org: {
          external_id: "org123",
          name: "Test Org",
        },
        pages: [],
      },
    ];

    // Default mock for fetch
    csrfFetch.mockImplementation(async (url) => {
      if (url.includes("/members/autocomplete/")) {
        return {
          ok: true,
          json: async () => ({
            members: [
              { external_id: "user1", username: "alice", email: "alice@test.com" },
              { external_id: "user2", username: "bob", email: "bob@test.com" },
              { external_id: "user3", username: "carol", email: "carol@test.com" },
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
    delete window._cachedProjects;
  });

  function createEditor(content) {
    const state = EditorState.create({
      doc: content,
      extensions: [
        autocompletion({
          override: [mentionCompletionSource],
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
    test("detects @ at start of line", async () => {
      createEditor("@");
      view.dispatch({ selection: { anchor: 1 } });

      const context = {
        state: view.state,
        pos: view.state.selection.main.head,
        explicit: false,
      };

      const result = await mentionCompletionSource(context);
      expect(result).not.toBeNull();
      expect(result.from).toBe(0);
      expect(result.to).toBe(1);
    });

    test("detects @ after space", async () => {
      createEditor("Hello @");
      view.dispatch({ selection: { anchor: 7 } });

      const context = {
        state: view.state,
        pos: view.state.selection.main.head,
        explicit: false,
      };

      const result = await mentionCompletionSource(context);
      expect(result).not.toBeNull();
      expect(result.from).toBe(6);
    });

    test("detects @partial query", async () => {
      createEditor("@ali");
      view.dispatch({ selection: { anchor: 4 } });

      const context = {
        state: view.state,
        pos: view.state.selection.main.head,
        explicit: false,
      };

      const result = await mentionCompletionSource(context);
      expect(result).not.toBeNull();
      expect(result.from).toBe(0);
      expect(result.to).toBe(4);
    });

    test("does not detect @ in middle of word", async () => {
      createEditor("email@test");
      view.dispatch({ selection: { anchor: 10 } });

      const context = {
        state: view.state,
        pos: view.state.selection.main.head,
        explicit: false,
      };

      const result = await mentionCompletionSource(context);
      expect(result).toBeNull();
    });

    test("does not trigger without @", async () => {
      createEditor("Hello world");
      view.dispatch({ selection: { anchor: 5 } });

      const context = {
        state: view.state,
        pos: view.state.selection.main.head,
        explicit: false,
      };

      const result = await mentionCompletionSource(context);
      expect(result).toBeNull();
    });
  });

  describe("API interaction", () => {
    test("fetches members from correct org endpoint", async () => {
      createEditor("@");
      view.dispatch({ selection: { anchor: 1 } });

      const context = {
        state: view.state,
        pos: view.state.selection.main.head,
        explicit: false,
      };

      await mentionCompletionSource(context);

      expect(csrfFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/orgs/org123/members/autocomplete/")
      );
    });

    test("passes query parameter to API", async () => {
      createEditor("@bob");
      view.dispatch({ selection: { anchor: 4 } });

      const context = {
        state: view.state,
        pos: view.state.selection.main.head,
        explicit: false,
      };

      await mentionCompletionSource(context);

      expect(csrfFetch).toHaveBeenCalledWith(expect.stringContaining("q=bob"));
    });

    test("returns null when no projects available", async () => {
      window._cachedProjects = [];

      createEditor("@");
      view.dispatch({ selection: { anchor: 1 } });

      const context = {
        state: view.state,
        pos: view.state.selection.main.head,
        explicit: false,
      };

      const result = await mentionCompletionSource(context);
      expect(result).toBeNull();
    });

    test("returns null when project has no org", async () => {
      window._cachedProjects = [{ external_id: "proj1", org: null }];

      createEditor("@");
      view.dispatch({ selection: { anchor: 1 } });

      const context = {
        state: view.state,
        pos: view.state.selection.main.head,
        explicit: false,
      };

      const result = await mentionCompletionSource(context);
      expect(result).toBeNull();
    });

    test("handles API error gracefully", async () => {
      csrfFetch.mockRejectedValueOnce(new Error("Network error"));

      createEditor("@");
      view.dispatch({ selection: { anchor: 1 } });

      const context = {
        state: view.state,
        pos: view.state.selection.main.head,
        explicit: false,
      };

      const result = await mentionCompletionSource(context);
      expect(result).toBeNull();
    });

    test("handles non-ok response gracefully", async () => {
      // Override mock to return non-ok response
      csrfFetch.mockImplementation(async () => ({ ok: false }));

      // Use unique query to avoid cache
      createEditor("@nonoktest");
      view.dispatch({ selection: { anchor: 10 } });

      const context = {
        state: view.state,
        pos: view.state.selection.main.head,
        explicit: false,
      };

      const result = await mentionCompletionSource(context);
      expect(result).toBeNull();

      // Reset mock to default
      csrfFetch.mockImplementation(async (url) => {
        if (url.includes("/members/autocomplete/")) {
          return {
            ok: true,
            json: async () => ({
              members: [
                { external_id: "user1", username: "alice", email: "alice@test.com" },
                { external_id: "user2", username: "bob", email: "bob@test.com" },
                { external_id: "user3", username: "carol", email: "carol@test.com" },
              ],
            }),
          };
        }
        return { ok: false };
      });
    });
  });

  describe("Completion options", () => {
    test("returns options with username as label", async () => {
      createEditor("@");
      view.dispatch({ selection: { anchor: 1 } });

      const context = {
        state: view.state,
        pos: view.state.selection.main.head,
        explicit: false,
      };

      const result = await mentionCompletionSource(context);
      expect(result.options.length).toBe(3);
      expect(result.options[0].label).toBe("alice");
      expect(result.options[1].label).toBe("bob");
      expect(result.options[2].label).toBe("carol");
    });

    test("options do not include email detail", async () => {
      createEditor("@");
      view.dispatch({ selection: { anchor: 1 } });

      const context = {
        state: view.state,
        pos: view.state.selection.main.head,
        explicit: false,
      };

      const result = await mentionCompletionSource(context);
      expect(result.options[0].detail).toBeUndefined();
    });

    test("options have type=mention", async () => {
      createEditor("@");
      view.dispatch({ selection: { anchor: 1 } });

      const context = {
        state: view.state,
        pos: view.state.selection.main.head,
        explicit: false,
      };

      const result = await mentionCompletionSource(context);
      expect(result.options[0].type).toBe("mention");
    });

    test("returns null when no members found", async () => {
      // Override the mock to return empty members
      csrfFetch.mockImplementation(async () => ({
        ok: true,
        json: async () => ({ members: [] }),
      }));

      // Use a unique query string that's different from other tests
      createEditor("@nomembers123");
      view.dispatch({ selection: { anchor: 13 } });

      const context = {
        state: view.state,
        pos: view.state.selection.main.head,
        explicit: false,
      };

      const result = await mentionCompletionSource(context);
      expect(result).toBeNull();

      // Reset mock to default after this test
      csrfFetch.mockImplementation(async (url) => {
        if (url.includes("/members/autocomplete/")) {
          return {
            ok: true,
            json: async () => ({
              members: [
                { external_id: "user1", username: "alice", email: "alice@test.com" },
                { external_id: "user2", username: "bob", email: "bob@test.com" },
                { external_id: "user3", username: "carol", email: "carol@test.com" },
              ],
            }),
          };
        }
        return { ok: false };
      });
    });
  });

  describe("Completion application", () => {
    test("apply function inserts mention syntax with @ in ID", async () => {
      // Set up mock with known members
      csrfFetch.mockImplementation(async () => ({
        ok: true,
        json: async () => ({
          members: [{ external_id: "user1", username: "alice", email: "alice@test.com" }],
        }),
      }));

      createEditor("@applyinsert");
      view.dispatch({ selection: { anchor: 12 } });

      const context = {
        state: view.state,
        pos: view.state.selection.main.head,
        explicit: false,
      };

      const result = await mentionCompletionSource(context);
      expect(result).not.toBeNull();

      // Simulate applying the first option
      const option = result.options[0];
      option.apply(view, option, result.from, result.to);

      expect(view.state.doc.toString()).toBe("@[alice](@user1) ");
    });

    test("apply function replaces partial query", async () => {
      csrfFetch.mockImplementation(async () => ({
        ok: true,
        json: async () => ({
          members: [{ external_id: "user1", username: "alice", email: "alice@test.com" }],
        }),
      }));

      createEditor("@applyreplace");
      view.dispatch({ selection: { anchor: 13 } });

      const context = {
        state: view.state,
        pos: view.state.selection.main.head,
        explicit: false,
      };

      const result = await mentionCompletionSource(context);
      expect(result).not.toBeNull();

      const option = result.options[0];
      option.apply(view, option, result.from, result.to);

      expect(view.state.doc.toString()).toBe("@[alice](@user1) ");
    });

    test("apply function positions cursor after mention", async () => {
      csrfFetch.mockImplementation(async () => ({
        ok: true,
        json: async () => ({
          members: [{ external_id: "user1", username: "alice", email: "alice@test.com" }],
        }),
      }));

      createEditor("@applycursor");
      view.dispatch({ selection: { anchor: 12 } });

      const context = {
        state: view.state,
        pos: view.state.selection.main.head,
        explicit: false,
      };

      const result = await mentionCompletionSource(context);
      expect(result).not.toBeNull();

      const option = result.options[0];
      option.apply(view, option, result.from, result.to);

      // Cursor should be at the end of the inserted text
      expect(view.state.selection.main.head).toBe("@[alice](@user1) ".length);
    });
  });

  describe("Caching", () => {
    test("caches members and reuses on same query", async () => {
      // Use a unique query for this test
      createEditor("@cachetest1");
      view.dispatch({ selection: { anchor: 11 } });

      // Clear call history
      csrfFetch.mockClear();

      const context = {
        state: view.state,
        pos: view.state.selection.main.head,
        explicit: false,
      };

      // First call - should fetch
      await mentionCompletionSource(context);
      expect(csrfFetch).toHaveBeenCalledTimes(1);

      // Second call with same context - should use cache
      const context2 = {
        state: view.state,
        pos: view.state.selection.main.head,
        explicit: false,
      };

      await mentionCompletionSource(context2);
      // Should still be 1 because query and org didn't change
      expect(csrfFetch).toHaveBeenCalledTimes(1);
    });

    test("fetches new data when query changes", async () => {
      // Clear call history
      csrfFetch.mockClear();

      // First query: @cachequery1
      view = createEditor("@cachequery1");
      view.dispatch({ selection: { anchor: 12 } });

      await mentionCompletionSource({
        state: view.state,
        pos: view.state.selection.main.head,
        explicit: false,
      });

      expect(csrfFetch).toHaveBeenCalledTimes(1);

      // Change to @cachequery2 - different query
      view.destroy();
      parent.remove();

      view = createEditor("@cachequery2");
      parent = view.dom.parentElement;
      view.dispatch({ selection: { anchor: 12 } });

      await mentionCompletionSource({
        state: view.state,
        pos: view.state.selection.main.head,
        explicit: false,
      });

      expect(csrfFetch).toHaveBeenCalledTimes(2);
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
      createEditor("@debounce1");
      view.dispatch({ selection: { anchor: 10 } });

      const context = {
        state: view.state,
        pos: view.state.selection.main.head,
        explicit: false,
      };

      // Start the completion source but don't await yet
      const promise = mentionCompletionSource(context);

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
      createEditor("@debounce2a");
      view.dispatch({ selection: { anchor: 11 } });

      const context1 = {
        state: view.state,
        pos: view.state.selection.main.head,
        explicit: false,
      };

      // Start first completion source - don't await it
      mentionCompletionSource(context1);

      // Check no fetch happened yet
      expect(csrfFetch).not.toHaveBeenCalled();

      // Don't wait for debounce to complete - simulate rapid typing
      await vi.advanceTimersByTimeAsync(50);

      // Still no fetch
      expect(csrfFetch).not.toHaveBeenCalled();

      // Second query before first debounce fires - this should cancel first
      view.destroy();
      parent.remove();
      view = createEditor("@debounce2b");
      parent = view.dom.parentElement;
      view.dispatch({ selection: { anchor: 11 } });

      const context2 = {
        state: view.state,
        pos: view.state.selection.main.head,
        explicit: false,
      };

      const promise2 = mentionCompletionSource(context2);

      // Advance timers to let second debounce complete
      await vi.advanceTimersByTimeAsync(200);

      // Await second promise
      await promise2;

      // Only the second query should result in a fetch (first was cancelled)
      expect(csrfFetch).toHaveBeenCalledTimes(1);
      expect(csrfFetch).toHaveBeenCalledWith(expect.stringContaining("q=debounce2b"));
    });

    test("uses 150ms debounce delay", async () => {
      createEditor("@debounce3");
      view.dispatch({ selection: { anchor: 10 } });

      const context = {
        state: view.state,
        pos: view.state.selection.main.head,
        explicit: false,
      };

      const promise = mentionCompletionSource(context);

      // At 100ms, should not have fetched yet
      await vi.advanceTimersByTimeAsync(100);
      expect(csrfFetch).not.toHaveBeenCalled();

      // At 150ms, should have fetched
      await vi.advanceTimersByTimeAsync(50);
      await promise;
      expect(csrfFetch).toHaveBeenCalledTimes(1);
    });
  });
});
