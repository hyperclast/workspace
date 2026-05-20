/**
 * Unit tests for the recent-pages list.
 *
 * The command palette filters its recent list by the current org so the
 * user never sees a page from another workspace they jumped through.
 * That filter is only meaningful if every entry written to localStorage
 * carries an `orgId`. The early-return guard inside `addRecentPage` is
 * the single enforcement point — these tests pin it so a future caller
 * that drops the argument can't silently re-introduce cross-org leaks
 * into the recent list.
 */

import { describe, test, expect, beforeEach } from "vitest";
import {
  addRecentPage,
  getRecentPages,
  getRecentPagesForOrg,
  clearRecentPages,
} from "../lib/recentPages.js";

const STORAGE_KEY = "hyperclast_recent_pages";

describe("addRecentPage — every persisted entry carries an orgId", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  test("call with orgId writes the entry with orgId field set", () => {
    addRecentPage("page-1", "My Page", "My Project", "org-a");

    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY));
    expect(stored).toHaveLength(1);
    expect(stored[0].orgId).toBe("org-a");
    expect(stored[0].id).toBe("page-1");
  });

  test("call without orgId is a no-op", () => {
    // The only path that doesn't write is the guard at the top of the
    // function. If a future call site forgets to thread orgId through,
    // we want the data to never reach localStorage rather than land
    // there with a missing field.
    addRecentPage("page-1", "My Page", "My Project", undefined);
    addRecentPage("page-2", "Other Page", "My Project", "");
    addRecentPage("page-3", "Third Page", "My Project", null);

    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
  });

  test("re-adding an existing page replaces its entry (still with orgId)", () => {
    addRecentPage("page-1", "Original Title", "Proj A", "org-a");
    addRecentPage("page-1", "New Title", "Proj A", "org-a");

    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY));
    expect(stored).toHaveLength(1);
    expect(stored[0].title).toBe("New Title");
    expect(stored[0].orgId).toBe("org-a");
  });

  test("getRecentPagesForOrg only returns entries matching the org", () => {
    addRecentPage("page-a", "A", "Proj A", "org-a");
    addRecentPage("page-b", "B", "Proj B", "org-b");
    addRecentPage("page-a2", "A2", "Proj A", "org-a");

    const aOnly = getRecentPagesForOrg("org-a");
    expect(aOnly.map((p) => p.id).sort()).toEqual(["page-a", "page-a2"]);
    expect(getRecentPagesForOrg("org-b").map((p) => p.id)).toEqual(["page-b"]);
  });
});

describe("getRecentPages — legacy entries without orgId are dropped on read", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  test("entries missing orgId are filtered out of the returned list", () => {
    // A pre-org build could have left these in storage. Reading must
    // pretend they don't exist so the org-scoped filter has nothing to
    // accidentally leak.
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify([
        { id: "legacy", title: "No org", projectName: "x", timestamp: 1 },
        { id: "fresh", title: "Has org", projectName: "y", orgId: "org-a", timestamp: 2 },
      ])
    );

    const result = getRecentPages();
    expect(result.map((p) => p.id)).toEqual(["fresh"]);
  });

  test("clearRecentPages removes the storage key entirely", () => {
    addRecentPage("page-1", "T", "P", "org-a");
    clearRecentPages();
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
  });
});
