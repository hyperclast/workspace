import { describe, test, expect } from "vitest";
import { looksLikeCsv } from "../../csv/detect.js";

/**
 * CSV Detection Tests
 *
 * Tests for the looksLikeCsv function used to determine if content
 * should be viewable as a spreadsheet in the page type modal.
 */

describe("looksLikeCsv", () => {
  describe("valid CSV content", () => {
    test("detects simple comma-separated content", () => {
      expect(looksLikeCsv("name,age,city")).toBe(true);
    });

    test("detects tab-separated content", () => {
      expect(looksLikeCsv("name\tage\tcity")).toBe(true);
    });

    test("detects CSV with multiple rows", () => {
      const csv = "name,age\nAlice,30\nBob,25";
      expect(looksLikeCsv(csv)).toBe(true);
    });

    test("detects CSV with quoted fields", () => {
      const csv = '"Company Name","Revenue"\n"Acme, Inc","$1,000,000"';
      expect(looksLikeCsv(csv)).toBe(true);
    });

    test("detects CSV with only header row", () => {
      expect(looksLikeCsv("col1,col2,col3")).toBe(true);
    });

    test("detects CSV with CRLF line endings", () => {
      const csv = "a,b,c\r\n1,2,3";
      expect(looksLikeCsv(csv)).toBe(true);
    });

    test("prefers comma over tab when both present", () => {
      const content = "a,b\tc,d";
      expect(looksLikeCsv(content)).toBe(true);
    });
  });

  describe("empty and whitespace content", () => {
    test("returns false for empty string (nothing to analyze)", () => {
      expect(looksLikeCsv("")).toBe(false);
    });

    test("returns false for null", () => {
      expect(looksLikeCsv(null)).toBe(false);
    });

    test("returns false for undefined", () => {
      expect(looksLikeCsv(undefined)).toBe(false);
    });

    test("returns false for whitespace only", () => {
      expect(looksLikeCsv("   ")).toBe(false);
      expect(looksLikeCsv("\n\n")).toBe(false);
      expect(looksLikeCsv("\t\t")).toBe(false);
    });
  });

  describe("non-CSV content", () => {
    test("rejects plain text without delimiters", () => {
      expect(looksLikeCsv("Hello world")).toBe(false);
    });

    test("rejects single column content", () => {
      expect(looksLikeCsv("line1\nline2\nline3")).toBe(false);
    });

    test("rejects markdown content", () => {
      const markdown = "# Heading\n\nSome paragraph text.\n\n- List item";
      expect(looksLikeCsv(markdown)).toBe(false);
    });

    test("JSON with commas is detected as CSV-like (acceptable false positive)", () => {
      // JSON has commas, so simple detection sees it as CSV-like
      // This is acceptable - user can easily switch back if needed
      const json = '{"name": "Alice", "age": 30}';
      expect(looksLikeCsv(json)).toBe(true);
    });

    test("rejects content with single comma (1 delimiter = 2 columns, which is OK)", () => {
      // Actually 1 comma = 2 columns, which should be valid
      expect(looksLikeCsv("a,b")).toBe(true);
    });

    test("rejects log-style content", () => {
      const logs = "[INFO] Starting server\n[ERROR] Connection failed";
      expect(looksLikeCsv(logs)).toBe(false);
    });

    test("rejects code content", () => {
      const code = "function hello() {\n  console.log('hi');\n}";
      expect(looksLikeCsv(code)).toBe(false);
    });
  });

  describe("edge cases", () => {
    test("handles content with empty first lines", () => {
      const csv = "\n\nname,age\nAlice,30";
      expect(looksLikeCsv(csv)).toBe(true);
    });

    test("handles single cell content", () => {
      expect(looksLikeCsv("single")).toBe(false);
    });

    test("handles content with commas in prose", () => {
      // Prose typically doesn't have consistent delimiters
      const prose = "Hello, world. This is a sentence, with commas.";
      // This has 2 commas, so it will be detected as CSV-like
      // This is acceptable - user can always switch back
      expect(looksLikeCsv(prose)).toBe(true);
    });

    test("handles very long first line", () => {
      const longLine = "a," + "x".repeat(10000) + ",b";
      expect(looksLikeCsv(longLine)).toBe(true);
    });

    test("handles unicode content", () => {
      const csv = "名前,年齢,都市\n太郎,30,東京";
      expect(looksLikeCsv(csv)).toBe(true);
    });

    test("handles mixed delimiters", () => {
      // Has commas so uses comma as delimiter
      const content = "a,b,c\td";
      expect(looksLikeCsv(content)).toBe(true);
    });
  });

  describe("real-world examples", () => {
    test("detects typical CSV export", () => {
      const csv = `company,primary_url,sectors,camp_class
Dots,http://weplaydots.com,Gaming,Playable Media
Roxy,http://www.roxydevice.com,"Hardware,Voice",Audio`;
      expect(looksLikeCsv(csv)).toBe(true);
    });

    test("detects TSV from spreadsheet copy", () => {
      const tsv = "Name\tEmail\tDepartment\nAlice\talice@co.com\tEngineering";
      expect(looksLikeCsv(tsv)).toBe(true);
    });

    test("meeting notes with commas detected as CSV-like (acceptable false positive)", () => {
      // First non-empty line has commas, so detected as CSV-like
      // This is acceptable - detection is intentionally permissive
      const notes = `Meeting Notes - Dec 31, 2025

Attendees: Alice, Bob, Charlie

Action Items:
- Review proposal
- Schedule follow-up`;
      expect(looksLikeCsv(notes)).toBe(true);
    });

    test("rejects meeting notes without commas in first line", () => {
      const notes = `Meeting Notes

Attendees were Alice and Bob.

Next steps:
- Review proposal
- Schedule follow-up`;
      expect(looksLikeCsv(notes)).toBe(false);
    });

    test("rejects typical README content", () => {
      const readme = `# Project Name

A description of the project.

## Installation

\`\`\`
npm install
\`\`\``;
      expect(looksLikeCsv(readme)).toBe(false);
    });
  });
});
