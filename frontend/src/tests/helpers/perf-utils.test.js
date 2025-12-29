/**
 * Tests for performance utilities
 */

import { describe, test, expect } from "vitest";
import {
  isFullMode,
  getConfig,
  measureTime,
  measureSize,
  formatBytes,
  calculateOverhead,
  assertPerf,
} from "./perf-utils.js";

describe("Performance Utilities", () => {
  test("isFullMode reads environment variable", () => {
    // Should be false by default (unless PERF_FULL=1 is set)
    expect(typeof isFullMode()).toBe("boolean");
  });

  test("getConfig returns correct value based on mode", () => {
    const defaultValue = 100;
    const fullValue = 50;
    const result = getConfig(defaultValue, fullValue);

    // Should return one of the two values
    expect([defaultValue, fullValue]).toContain(result);
  });

  test("measureTime measures execution duration", async () => {
    const delay = 10; // ms
    const fn = () => new Promise((resolve) => setTimeout(resolve, delay));

    const { duration, result } = await measureTime(fn);

    // Allow some variance since setTimeout is not perfectly precise
    // Can be slightly under due to timer precision
    expect(duration).toBeGreaterThanOrEqual(delay - 1); // Allow 1ms under
    expect(duration).toBeLessThan(delay + 50); // Allow variance above
    expect(result).toBeUndefined(); // fn returns undefined
  });

  test("measureTime returns function result", async () => {
    const expectedResult = "test-result";
    const fn = () => Promise.resolve(expectedResult);

    const { result } = await measureTime(fn);

    expect(result).toBe(expectedResult);
  });

  test("measureSize works with Uint8Array", () => {
    const data = new Uint8Array([1, 2, 3, 4, 5]);
    expect(measureSize(data)).toBe(5);
  });

  test("measureSize works with string", () => {
    const data = "hello";
    expect(measureSize(data)).toBe(5);
  });

  test("formatBytes formats correctly", () => {
    expect(formatBytes(500)).toBe("500 B");
    expect(formatBytes(1024)).toBe("1.00 KB");
    expect(formatBytes(1024 * 1024)).toBe("1.00 MB");
    expect(formatBytes(1536)).toBe("1.50 KB");
  });

  test("calculateOverhead computes percentage correctly", () => {
    expect(calculateOverhead(150, 100)).toBe(50); // 50% overhead
    expect(calculateOverhead(100, 100)).toBe(0); // 0% overhead
    expect(calculateOverhead(200, 100)).toBe(100); // 100% overhead
  });

  test("assertPerf passes when within threshold", () => {
    expect(() => {
      assertPerf(50, 100, "test");
    }).not.toThrow();
  });

  test("assertPerf fails when 3x over threshold", () => {
    expect(() => {
      assertPerf(350, 100, "test");
    }).toThrow(/Performance assertion failed/);
  });

  test("assertPerf warns but does not fail when 2x over threshold", () => {
    // Should warn but not throw
    expect(() => {
      assertPerf(250, 100, "test");
    }).not.toThrow();
  });
});
