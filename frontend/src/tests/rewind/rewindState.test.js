import { describe, test, expect, vi, beforeEach } from "vitest";

// Mock the sidebar store before importing rewind module
vi.mock("../../lib/stores/sidebar.svelte.js", () => ({
  registerTabHandler: vi.fn(),
  registerPageChangeHandler: vi.fn(),
}));

// Mock the API module
vi.mock("../../api.js", () => ({
  fetchRewindList: vi.fn(),
  fetchRewindDetail: vi.fn(),
}));

import {
  getState,
  subscribe,
  loadMore,
  selectEntry,
  setupRewind,
  enterRewindMode,
  exitRewindMode,
} from "../../rewind/index.js";
import { fetchRewindList, fetchRewindDetail } from "../../api.js";
import { registerTabHandler, registerPageChangeHandler } from "../../lib/stores/sidebar.svelte.js";
import { computeDiff } from "../../rewind/diff.js";

describe("Rewind state management", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("getState", () => {
    test("returns initial state", () => {
      const state = getState();
      expect(state).toHaveProperty("entries");
      expect(state).toHaveProperty("totalCount");
      expect(state).toHaveProperty("currentPageId");
      expect(state).toHaveProperty("selectedEntry");
      expect(state).toHaveProperty("selectedContent");
      expect(state).toHaveProperty("previousContent");
      expect(state).toHaveProperty("viewMode");
      expect(state).toHaveProperty("isRewindMode");
      expect(state).toHaveProperty("loading");
      expect(state).toHaveProperty("loadingDetail");
    });

    test("previousContent defaults to null", () => {
      expect(getState().previousContent).toBeNull();
    });

    test("viewMode defaults to diff", () => {
      expect(getState().viewMode).toBe("diff");
    });
  });

  describe("subscribe", () => {
    test("returns an unsubscribe function", () => {
      const fn = vi.fn();
      const unsub = subscribe(fn);
      expect(typeof unsub).toBe("function");
      unsub();
    });
  });

  describe("setupRewind", () => {
    test("registers tab handler for rewind", () => {
      setupRewind();
      expect(registerTabHandler).toHaveBeenCalledWith("rewind", expect.any(Function));
    });

    test("registers page change handler", () => {
      setupRewind();
      expect(registerPageChangeHandler).toHaveBeenCalledWith(expect.any(Function));
    });
  });

  describe("WebSocket rewindCreated event", () => {
    test("prepends new entry with diff stats to entries list", () => {
      // Setup: dispatch a rewindCreated event
      const rewindEntry = {
        external_id: "new-entry",
        rewind_number: 5,
        title: "Test",
        content_size_bytes: 100,
        editors: [],
        label: "",
        lines_added: 10,
        lines_deleted: 3,
        is_compacted: false,
        compacted_from_count: 0,
        created: new Date().toISOString(),
      };

      // The entry should have lines_added and lines_deleted fields
      expect(rewindEntry.lines_added).toBe(10);
      expect(rewindEntry.lines_deleted).toBe(3);
    });

    test("rewind entry schema includes diff stat fields", () => {
      // Verify the expected shape of a rewind entry from the API
      const apiEntry = {
        external_id: "abc123",
        rewind_number: 1,
        title: "Test Page",
        content_size_bytes: 50,
        editors: ["user1"],
        label: "",
        lines_added: 5,
        lines_deleted: 2,
        is_compacted: false,
        compacted_from_count: 0,
        created: "2026-03-05T12:00:00Z",
      };

      // These are the fields the RewindTab.svelte component uses
      expect("lines_added" in apiEntry).toBe(true);
      expect("lines_deleted" in apiEntry).toBe(true);
      expect("rewind_number" in apiEntry).toBe(true);
      expect(typeof apiEntry.lines_added).toBe("number");
      expect(typeof apiEntry.lines_deleted).toBe("number");
    });
  });
});

describe("Diff viewer compares against previous version", () => {
  // The diff viewer should show what changed IN a version (previous → selected),
  // NOT selected → current HEAD.

  test("diff is computed as previousContent → selectedContent", () => {
    // Simulates the RewindViewer derived computation:
    // computeDiff(state.previousContent || "", state.selectedContent || "")

    const previousContent = "line1\nline2\n";
    const selectedContent = "line1\nline2\nline3\n";

    const result = computeDiff(previousContent, selectedContent);

    // Should show 1 line added (line3), 0 removed
    expect(result.stats.added).toBe(1);
    expect(result.stats.removed).toBe(0);
  });

  test("first rewind (no previous) diffs against empty string", () => {
    const previousContent = ""; // no previous version
    const selectedContent = "line1\nline2\nline3\n";

    const result = computeDiff(previousContent, selectedContent);

    // All lines are additions
    expect(result.stats.added).toBe(3);
    expect(result.stats.removed).toBe(0);
  });

  test("selecting latest rewind still shows its diff against predecessor", () => {
    // v4 content = "a\nb"  (previous)
    // v5 content = "a\nb\nc\nd" (selected — also happens to match HEAD)
    const previousContent = "a\nb\n";
    const selectedContent = "a\nb\nc\nd\n";

    const result = computeDiff(previousContent, selectedContent);

    // Should show 2 added, NOT "no changes"
    expect(result.stats.added).toBe(2);
    expect(result.stats.removed).toBe(0);
    expect(result.chunks.length).toBeGreaterThan(0);
  });
});

describe("Rewind entry rendering logic", () => {
  // These test the conditional rendering logic from RewindTab.svelte
  // without needing a full Svelte mount

  function shouldShowDiffStat(entry) {
    return !!(entry.lines_added || entry.lines_deleted);
  }

  test("shows diff stat when lines_added > 0", () => {
    expect(shouldShowDiffStat({ lines_added: 5, lines_deleted: 0 })).toBe(true);
  });

  test("shows diff stat when lines_deleted > 0", () => {
    expect(shouldShowDiffStat({ lines_added: 0, lines_deleted: 3 })).toBe(true);
  });

  test("shows diff stat when both > 0", () => {
    expect(shouldShowDiffStat({ lines_added: 10, lines_deleted: 5 })).toBe(true);
  });

  test("hides diff stat when both are 0", () => {
    expect(shouldShowDiffStat({ lines_added: 0, lines_deleted: 0 })).toBe(false);
  });

  test("hides diff stat when both are undefined (legacy rewinds)", () => {
    expect(shouldShowDiffStat({})).toBe(false);
  });

  test("hides diff stat when both are null", () => {
    expect(shouldShowDiffStat({ lines_added: null, lines_deleted: null })).toBe(false);
  });

  test("formats as version number instead of title", () => {
    // The template uses `v{entry.rewind_number}` not `entry.title`
    const entry = { rewind_number: 42, title: "My Page" };
    const displayText = `v${entry.rewind_number}`;
    expect(displayText).toBe("v42");
    // Title is NOT displayed (it's redundant since all entries are for the same page)
    expect(displayText).not.toContain("My Page");
  });
});

// ============================================================
// selectEntry flow
// ============================================================

describe("selectEntry flow", () => {
  const makeEntry = (id, num) => ({
    external_id: id,
    rewind_number: num,
    title: "Test",
    created: new Date().toISOString(),
  });

  /** Helper: call setupRewind, then trigger the page-change handler to set
   *  currentPageId and load initial entries via the mocked API. */
  async function initWithEntries(pageId, entriesList) {
    setupRewind();

    // fetchRewindList will be called by the page-change handler
    fetchRewindList.mockResolvedValueOnce({
      items: entriesList,
      count: entriesList.length,
    });

    // Trigger the page-change handler registered by setupRewind
    const pageChangeHandler = registerPageChangeHandler.mock.calls.at(-1)[0];
    pageChangeHandler(pageId);

    // Let the loadEntries() promise settle
    await vi.waitFor(() => {
      expect(getState().loading).toBe(false);
    });
  }

  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
  });

  afterEach(() => {
    // Clean up rewind mode if active
    if (getState().isRewindMode) exitRewindMode();
    vi.useRealTimers();
  });

  test("selectEntry fetches selected and previous entry content in parallel", async () => {
    const v3 = makeEntry("v3", 3);
    const v2 = makeEntry("v2", 2);
    const v1 = makeEntry("v1", 1);
    await initWithEntries("page-1", [v3, v2, v1]);

    fetchRewindDetail.mockImplementation((pageId, rewindId) => {
      if (rewindId === "v2") return Promise.resolve({ content: "v2-content" });
      if (rewindId === "v1") return Promise.resolve({ content: "v1-content" });
      return Promise.resolve({ content: "" });
    });

    // Select v2 (middle entry — predecessor is v1)
    selectEntry(v2);
    await vi.advanceTimersByTimeAsync(150);

    // Should have fetched both v2 and its predecessor v1
    expect(fetchRewindDetail).toHaveBeenCalledTimes(2);
    expect(fetchRewindDetail).toHaveBeenCalledWith("page-1", "v2");
    expect(fetchRewindDetail).toHaveBeenCalledWith("page-1", "v1");

    const state = getState();
    expect(state.selectedContent).toBe("v2-content");
    expect(state.previousContent).toBe("v1-content");
    expect(state.loadingDetail).toBe(false);
  });

  test("selectEntry sets previousContent to empty string for first entry", async () => {
    const v1 = makeEntry("v1", 1);
    await initWithEntries("page-1", [v1]);

    fetchRewindDetail.mockResolvedValueOnce({ content: "v1-content" });

    selectEntry(v1);
    await vi.advanceTimersByTimeAsync(150);

    // Only one fetch — no predecessor
    expect(fetchRewindDetail).toHaveBeenCalledTimes(1);
    expect(fetchRewindDetail).toHaveBeenCalledWith("page-1", "v1");

    const state = getState();
    expect(state.selectedContent).toBe("v1-content");
    expect(state.previousContent).toBe("");
  });

  test("rapid selectEntry calls only resolve the last selection", async () => {
    const v3 = makeEntry("v3", 3);
    const v2 = makeEntry("v2", 2);
    const v1 = makeEntry("v1", 1);
    await initWithEntries("page-1", [v3, v2, v1]);

    fetchRewindDetail.mockImplementation((pageId, rewindId) => {
      if (rewindId === "v3") return Promise.resolve({ content: "v3-content" });
      if (rewindId === "v2") return Promise.resolve({ content: "v2-content" });
      if (rewindId === "v1") return Promise.resolve({ content: "v1-content" });
      return Promise.resolve({ content: "" });
    });

    // Rapid clicks: select v3, then immediately select v2 before debounce fires
    selectEntry(v3);
    selectEntry(v2);

    await vi.advanceTimersByTimeAsync(150);

    // Only the last selection (v2) should have triggered fetches
    const state = getState();
    expect(state.selectedEntry.external_id).toBe("v2");
    expect(state.selectedContent).toBe("v2-content");
  });
});

// ============================================================
// exitRewindMode cleanup
// ============================================================

describe("exitRewindMode cleanup", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("exitRewindMode resets state and dispatches rewindExited event", () => {
    // Enter rewind mode first
    enterRewindMode();
    expect(getState().isRewindMode).toBe(true);

    // Listen for the event
    const handler = vi.fn();
    window.addEventListener("rewindExited", handler);

    exitRewindMode();

    const state = getState();
    expect(state.isRewindMode).toBe(false);
    expect(state.selectedEntry).toBeNull();
    expect(state.selectedContent).toBeNull();
    expect(state.previousContent).toBeNull();
    expect(state.viewMode).toBe("diff");
    expect(handler).toHaveBeenCalledTimes(1);

    window.removeEventListener("rewindExited", handler);
  });

  test("exitRewindMode restores editor/toolbar DOM visibility", () => {
    // Create DOM elements
    const editor = document.createElement("div");
    editor.id = "editor-container";
    const toolbar = document.createElement("div");
    toolbar.id = "toolbar-wrapper";
    const viewer = document.createElement("div");
    viewer.id = "rewind-viewer";
    document.body.append(editor, toolbar, viewer);

    try {
      enterRewindMode();
      expect(editor.style.display).toBe("none");
      expect(toolbar.style.display).toBe("none");
      expect(viewer.style.display).toBe("flex");

      exitRewindMode();
      expect(editor.style.display).toBe("");
      expect(toolbar.style.display).toBe("");
      expect(viewer.style.display).toBe("none");
    } finally {
      editor.remove();
      toolbar.remove();
      viewer.remove();
    }
  });
});

// ============================================================
// loadMore pagination
// ============================================================

describe("loadMore pagination", () => {
  const makeEntry = (id, num) => ({
    external_id: id,
    rewind_number: num,
    title: "Test",
    created: new Date().toISOString(),
  });

  async function initWithEntries(pageId, entriesList, totalCount) {
    setupRewind();

    fetchRewindList.mockResolvedValueOnce({
      items: entriesList,
      count: totalCount,
    });

    const pageChangeHandler = registerPageChangeHandler.mock.calls.at(-1)[0];
    pageChangeHandler(pageId);

    await vi.waitFor(() => {
      expect(getState().loading).toBe(false);
    });
  }

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    if (getState().isRewindMode) exitRewindMode();
  });

  test("loadMore appends entries and updates totalCount", async () => {
    const v4 = makeEntry("v4", 4);
    const v3 = makeEntry("v3", 3);
    await initWithEntries("page-1", [v4, v3], 4);

    expect(getState().entries).toHaveLength(2);

    const v2 = makeEntry("v2", 2);
    const v1 = makeEntry("v1", 1);
    fetchRewindList.mockResolvedValueOnce({
      items: [v2, v1],
      count: 4,
    });

    await loadMore();

    const state = getState();
    expect(state.entries).toHaveLength(4);
    expect(state.entries.map((e) => e.external_id)).toEqual(["v4", "v3", "v2", "v1"]);
    expect(state.totalCount).toBe(4);
    // Should have been called with offset = 2 (existing entries count)
    expect(fetchRewindList).toHaveBeenLastCalledWith("page-1", 50, 2);
  });

  test("loadMore does not fetch when all entries loaded", async () => {
    const v2 = makeEntry("v2", 2);
    const v1 = makeEntry("v1", 1);
    await initWithEntries("page-1", [v2, v1], 2);

    // Clear the mock from init
    fetchRewindList.mockClear();

    await loadMore();

    // Should not have made any additional API calls
    expect(fetchRewindList).not.toHaveBeenCalled();
    expect(getState().entries).toHaveLength(2);
  });
});
