import { describe, test, expect } from "vitest";
import { formatFileSize } from "../../lib/utils/formatFileSize.js";

describe("formatFileSize", () => {
  describe("default behavior (with decimals)", () => {
    test("returns '0 B' for 0 bytes", () => {
      expect(formatFileSize(0)).toBe("0 B");
    });

    test("returns '0 B' for null", () => {
      expect(formatFileSize(null)).toBe("0 B");
    });

    test("returns '0 B' for undefined", () => {
      expect(formatFileSize(undefined)).toBe("0 B");
    });

    test("formats bytes (< 1024)", () => {
      expect(formatFileSize(1)).toBe("1 B");
      expect(formatFileSize(512)).toBe("512 B");
      expect(formatFileSize(1023)).toBe("1023 B");
    });

    test("formats kilobytes with one decimal place", () => {
      expect(formatFileSize(1024)).toBe("1.0 KB");
      expect(formatFileSize(1536)).toBe("1.5 KB");
      expect(formatFileSize(2048)).toBe("2.0 KB");
      expect(formatFileSize(1024 * 500)).toBe("500.0 KB");
      expect(formatFileSize(1024 * 1023)).toBe("1023.0 KB");
    });

    test("formats megabytes with one decimal place", () => {
      expect(formatFileSize(1024 * 1024)).toBe("1.0 MB");
      expect(formatFileSize(1024 * 1024 * 1.5)).toBe("1.5 MB");
      expect(formatFileSize(1024 * 1024 * 100)).toBe("100.0 MB");
      expect(formatFileSize(1024 * 1024 * 1023)).toBe("1023.0 MB");
    });

    test("formats gigabytes with one decimal place", () => {
      expect(formatFileSize(1024 * 1024 * 1024)).toBe("1.0 GB");
      expect(formatFileSize(1024 * 1024 * 1024 * 2.5)).toBe("2.5 GB");
      expect(formatFileSize(1024 * 1024 * 1024 * 100)).toBe("100.0 GB");
    });

    test("handles edge case at unit boundaries", () => {
      // Just under 1 KB
      expect(formatFileSize(1023)).toBe("1023 B");
      // Exactly 1 KB
      expect(formatFileSize(1024)).toBe("1.0 KB");

      // Just under 1 MB
      expect(formatFileSize(1024 * 1024 - 1)).toBe("1024.0 KB");
      // Exactly 1 MB
      expect(formatFileSize(1024 * 1024)).toBe("1.0 MB");

      // Just under 1 GB
      expect(formatFileSize(1024 * 1024 * 1024 - 1)).toBe("1024.0 MB");
      // Exactly 1 GB
      expect(formatFileSize(1024 * 1024 * 1024)).toBe("1.0 GB");
    });
  });

  describe("compact mode (rounded, no decimals)", () => {
    test("returns empty string for 0 bytes", () => {
      expect(formatFileSize(0, { compact: true })).toBe("");
    });

    test("returns empty string for null", () => {
      expect(formatFileSize(null, { compact: true })).toBe("");
    });

    test("returns empty string for undefined", () => {
      expect(formatFileSize(undefined, { compact: true })).toBe("");
    });

    test("formats bytes (< 1024)", () => {
      expect(formatFileSize(1, { compact: true })).toBe("1 B");
      expect(formatFileSize(512, { compact: true })).toBe("512 B");
      expect(formatFileSize(1023, { compact: true })).toBe("1023 B");
    });

    test("formats kilobytes rounded to nearest integer", () => {
      expect(formatFileSize(1024, { compact: true })).toBe("1 KB");
      expect(formatFileSize(1536, { compact: true })).toBe("2 KB"); // 1.5 rounds to 2
      expect(formatFileSize(2048, { compact: true })).toBe("2 KB");
      expect(formatFileSize(1024 * 500, { compact: true })).toBe("500 KB");
    });

    test("formats megabytes rounded to nearest integer", () => {
      expect(formatFileSize(1024 * 1024, { compact: true })).toBe("1 MB");
      expect(formatFileSize(1024 * 1024 * 1.5, { compact: true })).toBe("2 MB"); // 1.5 rounds to 2
      expect(formatFileSize(1024 * 1024 * 100, { compact: true })).toBe("100 MB");
    });

    test("formats gigabytes rounded to nearest integer", () => {
      expect(formatFileSize(1024 * 1024 * 1024, { compact: true })).toBe("1 GB");
      expect(formatFileSize(1024 * 1024 * 1024 * 2.5, { compact: true })).toBe("3 GB"); // 2.5 rounds to 3
      expect(formatFileSize(1024 * 1024 * 1024 * 100, { compact: true })).toBe("100 GB");
    });
  });

  describe("edge cases", () => {
    test("handles negative numbers by returning appropriate zero value", () => {
      // Negative sizes don't make sense, treat as zero
      expect(formatFileSize(-1)).toBe("0 B");
      expect(formatFileSize(-1, { compact: true })).toBe("");
    });

    test("handles very large file sizes", () => {
      // 1 TB
      expect(formatFileSize(1024 * 1024 * 1024 * 1024)).toBe("1024.0 GB");
      expect(formatFileSize(1024 * 1024 * 1024 * 1024, { compact: true })).toBe("1024 GB");
    });

    test("handles decimal byte values by treating them as whole bytes", () => {
      // File sizes are always integers, but handle gracefully
      expect(formatFileSize(1.5)).toBe("1.5 B");
      expect(formatFileSize(1.5, { compact: true })).toBe("1.5 B");
    });
  });
});
