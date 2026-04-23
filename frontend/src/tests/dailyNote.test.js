import { describe, it, expect } from "vitest";
import { countUnorganizedDailyNotes } from "../lib/dailyNote.js";

describe("countUnorganizedDailyNotes", () => {
  it("returns 0 for empty arrays", () => {
    expect(countUnorganizedDailyNotes([], [])).toBe(0);
  });

  it("counts pages with YYYY-MM-DD titles not in correct folders", () => {
    const pages = [
      { title: "2026-04-01", folder_id: null },
      { title: "2026-04-02", folder_id: null },
    ];
    expect(countUnorganizedDailyNotes(pages, [])).toBe(2);
  });

  it("skips pages with non-date titles", () => {
    const pages = [
      { title: "2026-04-01", folder_id: null },
      { title: "Meeting Notes", folder_id: null },
      { title: "Random Page", folder_id: null },
    ];
    expect(countUnorganizedDailyNotes(pages, [])).toBe(1);
  });

  it("skips pages with non-numeric month segments", () => {
    const pages = [
      { title: "2026-04-01", folder_id: null },
      { title: "2026-ab-01", folder_id: null },
    ];
    // "2026-ab-01" is already rejected by the regex (\d only matches 0-9),
    // but this confirms the numeric guard also works as a safety net.
    expect(countUnorganizedDailyNotes(pages, [])).toBe(1);
  });

  it("skips pages already in correct YYYY/MM folder", () => {
    const folders = [
      { external_id: "f-year", name: "2026", parent_id: null },
      { external_id: "f-month", name: "04", parent_id: "f-year" },
    ];
    const pages = [{ title: "2026-04-01", folder_id: "f-month" }];
    expect(countUnorganizedDailyNotes(pages, folders)).toBe(0);
  });

  it("counts pages in wrong folder as unorganized", () => {
    const folders = [
      { external_id: "f-year", name: "2026", parent_id: null },
      { external_id: "f-month", name: "03", parent_id: "f-year" },
    ];
    const pages = [
      { title: "2026-04-01", folder_id: "f-month" }, // in 03 folder, not 04
    ];
    expect(countUnorganizedDailyNotes(pages, folders)).toBe(1);
  });

  it("counts pages in nested folder (not root year) as unorganized", () => {
    const folders = [
      { external_id: "f-root", name: "Archive", parent_id: null },
      { external_id: "f-year", name: "2026", parent_id: "f-root" },
      { external_id: "f-month", name: "04", parent_id: "f-year" },
    ];
    const pages = [{ title: "2026-04-01", folder_id: "f-month" }];
    // Year folder has a parent (not a root-level folder), so not correctly organized
    expect(countUnorganizedDailyNotes(pages, folders)).toBe(1);
  });

  it("handles null/undefined titles gracefully", () => {
    const pages = [
      { title: null, folder_id: null },
      { title: undefined, folder_id: null },
      { title: "2026-04-01", folder_id: null },
    ];
    expect(countUnorganizedDailyNotes(pages, [])).toBe(1);
  });
});
