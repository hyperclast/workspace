/**
 * debouncedFetch.js Tests
 *
 * Tests for the shared debounced fetch utility used by autocomplete modules.
 */

import { describe, test, expect, vi, beforeEach, afterEach } from "vitest";
import { createDebouncedFetcher } from "../../debouncedFetch.js";

describe("createDebouncedFetcher", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  test("creates a fetcher with fetch and reset methods", () => {
    const fetcher = createDebouncedFetcher();
    expect(typeof fetcher.fetch).toBe("function");
    expect(typeof fetcher.reset).toBe("function");
  });

  test("delays fetch by specified milliseconds", async () => {
    const fetcher = createDebouncedFetcher(100);
    const fetchFn = vi.fn().mockResolvedValue("result");

    const promise = fetcher.fetch("query", fetchFn);

    // Not called immediately
    expect(fetchFn).not.toHaveBeenCalled();

    // Called after delay
    await vi.advanceTimersByTimeAsync(100);
    await promise;

    expect(fetchFn).toHaveBeenCalledTimes(1);
  });

  test("uses default 150ms delay", async () => {
    const fetcher = createDebouncedFetcher();
    const fetchFn = vi.fn().mockResolvedValue("result");

    const promise = fetcher.fetch("query", fetchFn);

    // Not called at 100ms
    await vi.advanceTimersByTimeAsync(100);
    expect(fetchFn).not.toHaveBeenCalled();

    // Called at 150ms
    await vi.advanceTimersByTimeAsync(50);
    await promise;

    expect(fetchFn).toHaveBeenCalledTimes(1);
  });

  test("returns cached result for same query", async () => {
    const fetcher = createDebouncedFetcher(100);
    const fetchFn = vi.fn().mockResolvedValue("result");

    // First call
    const promise1 = fetcher.fetch("query", fetchFn);
    await vi.advanceTimersByTimeAsync(100);
    await promise1;

    expect(fetchFn).toHaveBeenCalledTimes(1);

    // Second call with same query - should use cache
    const result = await fetcher.fetch("query", fetchFn);

    expect(result).toBe("result");
    expect(fetchFn).toHaveBeenCalledTimes(1); // Still 1, used cache
  });

  test("fetches new data for different query", async () => {
    const fetcher = createDebouncedFetcher(100);
    const fetchFn = vi.fn().mockResolvedValue("result");

    // First query
    const promise1 = fetcher.fetch("query1", fetchFn);
    await vi.advanceTimersByTimeAsync(100);
    await promise1;

    expect(fetchFn).toHaveBeenCalledTimes(1);

    // Different query - should fetch again
    const promise2 = fetcher.fetch("query2", fetchFn);
    await vi.advanceTimersByTimeAsync(100);
    await promise2;

    expect(fetchFn).toHaveBeenCalledTimes(2);
  });

  test("cancels pending fetch when new query comes in", async () => {
    const fetcher = createDebouncedFetcher(100);
    const fetchFn1 = vi.fn().mockResolvedValue("result1");
    const fetchFn2 = vi.fn().mockResolvedValue("result2");

    // First query
    fetcher.fetch("query1", fetchFn1);

    // Wait 50ms (not enough for first to fire)
    await vi.advanceTimersByTimeAsync(50);
    expect(fetchFn1).not.toHaveBeenCalled();

    // Second query cancels first
    const promise = fetcher.fetch("query2", fetchFn2);

    // Wait 100ms more
    await vi.advanceTimersByTimeAsync(100);
    await promise;

    // First was cancelled, only second was called
    expect(fetchFn1).not.toHaveBeenCalled();
    expect(fetchFn2).toHaveBeenCalledTimes(1);
  });

  test("reset clears cache and pending fetch", async () => {
    const fetcher = createDebouncedFetcher(100);
    const fetchFn = vi.fn().mockResolvedValue("result");

    // First call
    const promise1 = fetcher.fetch("query", fetchFn);
    await vi.advanceTimersByTimeAsync(100);
    await promise1;

    expect(fetchFn).toHaveBeenCalledTimes(1);

    // Reset
    fetcher.reset();

    // Same query now fetches again (cache was cleared)
    const promise2 = fetcher.fetch("query", fetchFn);
    await vi.advanceTimersByTimeAsync(100);
    await promise2;

    expect(fetchFn).toHaveBeenCalledTimes(2);
  });

  test("propagates errors from fetch function", async () => {
    // Use real timers for this test to avoid async rejection handling issues
    vi.useRealTimers();

    const fetcher = createDebouncedFetcher(10); // Use short delay for real timers
    const fetchFn = vi.fn().mockImplementation(async () => {
      throw new Error("Network error");
    });

    await expect(fetcher.fetch("query", fetchFn)).rejects.toThrow("Network error");

    // Re-enable fake timers for other tests
    vi.useFakeTimers();
  });

  test("returns result from fetch function", async () => {
    const fetcher = createDebouncedFetcher(100);
    const data = { items: [1, 2, 3] };
    const fetchFn = vi.fn().mockResolvedValue(data);

    const promise = fetcher.fetch("query", fetchFn);
    await vi.advanceTimersByTimeAsync(100);
    const result = await promise;

    expect(result).toEqual(data);
  });
});
