import { describe, test, expect, vi, beforeEach, afterEach } from "vitest";
import { formatRelativeTime, groupByDay } from "../../rewind/timeFormat.js";

describe("formatRelativeTime", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-03-05T12:00:00Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  test("returns 'just now' for less than 1 minute ago", () => {
    const date = new Date("2026-03-05T11:59:30Z").toISOString();
    expect(formatRelativeTime(date)).toBe("just now");
  });

  test("returns minutes ago for < 60 minutes", () => {
    const date = new Date("2026-03-05T11:55:00Z").toISOString();
    expect(formatRelativeTime(date)).toBe("5m ago");
  });

  test("returns hours ago for < 24 hours", () => {
    const date = new Date("2026-03-05T09:00:00Z").toISOString();
    expect(formatRelativeTime(date)).toBe("3h ago");
  });

  test("returns 'Yesterday' for yesterday's date (>24h ago)", () => {
    // Must be >24h ago so it passes the `diffHr < 24` check
    const date = new Date("2026-03-04T08:00:00Z").toISOString();
    expect(formatRelativeTime(date)).toBe("Yesterday");
  });

  test("returns short date for older dates", () => {
    const date = new Date("2026-03-01T12:00:00Z").toISOString();
    const result = formatRelativeTime(date);
    // Should contain month and day
    expect(result).toMatch(/Mar/);
    expect(result).toMatch(/1/);
  });
});

describe("groupByDay", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-03-05T12:00:00Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  test("returns empty array for no entries", () => {
    expect(groupByDay([])).toEqual([]);
  });

  test("groups entries from today", () => {
    const entries = [
      { created: "2026-03-05T11:00:00Z", external_id: "a" },
      { created: "2026-03-05T10:00:00Z", external_id: "b" },
    ];
    const groups = groupByDay(entries);
    expect(groups).toHaveLength(1);
    expect(groups[0].label).toBe("Today");
    expect(groups[0].entries).toHaveLength(2);
  });

  test("separates today and yesterday", () => {
    const entries = [
      { created: "2026-03-05T11:00:00Z", external_id: "a" },
      { created: "2026-03-04T10:00:00Z", external_id: "b" },
    ];
    const groups = groupByDay(entries);
    expect(groups).toHaveLength(2);
    expect(groups[0].label).toBe("Today");
    expect(groups[1].label).toBe("Yesterday");
  });

  test("groups older entries by date", () => {
    const entries = [
      { created: "2026-03-05T11:00:00Z", external_id: "a" },
      { created: "2026-03-01T10:00:00Z", external_id: "b" },
      { created: "2026-03-01T09:00:00Z", external_id: "c" },
    ];
    const groups = groupByDay(entries);
    expect(groups).toHaveLength(2);
    expect(groups[0].label).toBe("Today");
    expect(groups[1].entries).toHaveLength(2);
  });

  test("single entry returns one group", () => {
    const entries = [{ created: "2026-03-05T10:00:00Z", external_id: "a" }];
    const groups = groupByDay(entries);
    expect(groups).toHaveLength(1);
    expect(groups[0].entries).toHaveLength(1);
  });
});
