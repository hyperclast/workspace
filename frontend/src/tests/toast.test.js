/**
 * toast.svelte.js Tests
 *
 * Tests for the toast notification store:
 * 1. showToast — creates toasts, returns IDs, auto-removes after duration
 * 2. Deduplication — identical message+type pairs are not duplicated
 * 3. removeToast — removes a toast by ID
 */

import { describe, test, expect, beforeEach, afterEach, vi } from "vitest";
import { getToasts, showToast, removeToast } from "../lib/stores/toast.svelte.js";

describe("showToast", () => {
  afterEach(() => {
    // Clear all toasts between tests
    for (const t of [...getToasts()]) {
      removeToast(t.id);
    }
  });

  test("creates a toast and returns its ID", () => {
    const id = showToast("Hello", "success");
    expect(typeof id).toBe("number");

    const toasts = getToasts();
    expect(toasts).toHaveLength(1);
    expect(toasts[0].message).toBe("Hello");
    expect(toasts[0].type).toBe("success");
    expect(toasts[0].id).toBe(id);
  });

  test("defaults type to success", () => {
    showToast("Default type");
    expect(getToasts()[0].type).toBe("success");
  });

  test("auto-removes after duration", () => {
    vi.useFakeTimers();

    showToast("Temporary", "success", { duration: 3000 });
    expect(getToasts()).toHaveLength(1);

    vi.advanceTimersByTime(3000);
    expect(getToasts()).toHaveLength(0);

    vi.useRealTimers();
  });

  test("error toasts do not auto-remove (duration 0)", () => {
    vi.useFakeTimers();

    showToast("Error!", "error");
    expect(getToasts()).toHaveLength(1);

    vi.advanceTimersByTime(60000);
    expect(getToasts()).toHaveLength(1);

    vi.useRealTimers();
  });

  test("supports legacy duration parameter as number", () => {
    vi.useFakeTimers();

    showToast("Legacy", "success", 2000);
    expect(getToasts()).toHaveLength(1);

    vi.advanceTimersByTime(2000);
    expect(getToasts()).toHaveLength(0);

    vi.useRealTimers();
  });

  test("stores action option on the toast", () => {
    const action = { label: "Undo", onClick: () => {} };
    showToast("With action", "success", { action });
    expect(getToasts()[0].action).toStrictEqual(action);
  });
});

describe("deduplication", () => {
  afterEach(() => {
    for (const t of [...getToasts()]) {
      removeToast(t.id);
    }
  });

  test("returns existing ID when same message and type already showing", () => {
    const id1 = showToast("Connection limited", "warning");
    const id2 = showToast("Connection limited", "warning");

    expect(id2).toBe(id1);
    expect(getToasts()).toHaveLength(1);
  });

  test("allows same message with different type", () => {
    showToast("Something happened", "success");
    showToast("Something happened", "error");

    expect(getToasts()).toHaveLength(2);
  });

  test("allows same type with different message", () => {
    showToast("First warning", "warning");
    showToast("Second warning", "warning");

    expect(getToasts()).toHaveLength(2);
  });

  test("allows re-creating toast after the original is removed", () => {
    const id1 = showToast("Temporary", "success");
    removeToast(id1);

    const id2 = showToast("Temporary", "success");
    expect(id2).not.toBe(id1);
    expect(getToasts()).toHaveLength(1);
  });

  test("allows re-creating toast after auto-removal", () => {
    vi.useFakeTimers();

    const id1 = showToast("Auto", "success", { duration: 1000 });
    vi.advanceTimersByTime(1000);
    expect(getToasts()).toHaveLength(0);

    const id2 = showToast("Auto", "success", { duration: 1000 });
    expect(id2).not.toBe(id1);
    expect(getToasts()).toHaveLength(1);

    vi.useRealTimers();
  });
});

describe("removeToast", () => {
  afterEach(() => {
    for (const t of [...getToasts()]) {
      removeToast(t.id);
    }
  });

  test("removes a toast by ID", () => {
    const id = showToast("Remove me", "success");
    expect(getToasts()).toHaveLength(1);

    removeToast(id);
    expect(getToasts()).toHaveLength(0);
  });

  test("does nothing for non-existent ID", () => {
    showToast("Keep me", "success");
    removeToast(99999);
    expect(getToasts()).toHaveLength(1);
  });
});
