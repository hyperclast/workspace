import { describe, test, expect } from "vitest";
import { parseCSV, sortRows, filterRows } from "../../csv/parse.js";

/**
 * CSV Parser Tests
 *
 * The CSV parser handles RFC 4180 compliant CSV including:
 * - Quoted fields with commas, newlines, and escaped quotes
 * - Various line endings (LF, CRLF)
 * - Irregular column counts
 * - Empty cells and rows
 */

describe("parseCSV", () => {
  test("parses simple CSV", () => {
    const csv = "name,age,city\nAlice,30,NYC\nBob,25,LA";
    const result = parseCSV(csv);

    expect(result.headers).toEqual(["name", "age", "city"]);
    expect(result.rows).toEqual([
      ["Alice", "30", "NYC"],
      ["Bob", "25", "LA"],
    ]);
  });

  test("handles quoted fields", () => {
    const csv = 'name,description\nAlice,"Software Engineer"\nBob,"Product Manager"';
    const result = parseCSV(csv);

    expect(result.headers).toEqual(["name", "description"]);
    expect(result.rows).toEqual([
      ["Alice", "Software Engineer"],
      ["Bob", "Product Manager"],
    ]);
  });

  test("handles escaped quotes (doubled quotes)", () => {
    const csv = 'name,quote\nAlice,"She said ""Hello"""\nBob,"Test ""value"""';
    const result = parseCSV(csv);

    expect(result.rows[0]).toEqual(["Alice", 'She said "Hello"']);
    expect(result.rows[1]).toEqual(["Bob", 'Test "value"']);
  });

  test("handles commas within quoted fields", () => {
    const csv = 'name,address\nAlice,"123 Main St, Apt 4"\nBob,"456 Oak Ave, Suite 100"';
    const result = parseCSV(csv);

    expect(result.rows[0]).toEqual(["Alice", "123 Main St, Apt 4"]);
    expect(result.rows[1]).toEqual(["Bob", "456 Oak Ave, Suite 100"]);
  });

  test("handles newlines within quoted fields", () => {
    const csv = 'name,notes\nAlice,"Line 1\nLine 2"\nBob,"Single line"';
    const result = parseCSV(csv);

    expect(result.rows[0]).toEqual(["Alice", "Line 1\nLine 2"]);
    expect(result.rows[1]).toEqual(["Bob", "Single line"]);
  });

  test("handles empty cells", () => {
    const csv = "a,b,c\n1,,3\n,2,";
    const result = parseCSV(csv);

    expect(result.rows).toEqual([
      ["1", "", "3"],
      ["", "2", ""],
    ]);
  });

  test("filters out rows with all empty cells", () => {
    const csv = "a,b,c\n1,2,3\n,,\n4,5,6";
    const result = parseCSV(csv);

    expect(result.rows).toEqual([
      ["1", "2", "3"],
      ["4", "5", "6"],
    ]);
  });

  test("handles CRLF line endings", () => {
    const csv = "name,age\r\nAlice,30\r\nBob,25";
    const result = parseCSV(csv);

    expect(result.headers).toEqual(["name", "age"]);
    expect(result.rows).toEqual([
      ["Alice", "30"],
      ["Bob", "25"],
    ]);
  });

  test("normalizes rows with varying column counts", () => {
    const csv = "a,b,c\n1,2\n1,2,3,4";
    const result = parseCSV(csv);

    expect(result.headers).toHaveLength(4);
    expect(result.headers[3]).toBe("Column 4");
    expect(result.rows[0]).toEqual(["1", "2", "", ""]);
    expect(result.rows[1]).toEqual(["1", "2", "3", "4"]);
  });

  test("filters out empty rows", () => {
    const csv = "a,b\n1,2\n\n3,4\n   \n5,6";
    const result = parseCSV(csv);

    expect(result.rows).toHaveLength(3);
    expect(result.rows[0]).toEqual(["1", "2"]);
    expect(result.rows[1]).toEqual(["3", "4"]);
    expect(result.rows[2]).toEqual(["5", "6"]);
  });

  test("returns empty result for empty input", () => {
    expect(parseCSV("")).toEqual({ headers: [], rows: [] });
    expect(parseCSV(null)).toEqual({ headers: [], rows: [] });
    expect(parseCSV(undefined)).toEqual({ headers: [], rows: [] });
  });

  test("handles single column CSV", () => {
    const csv = "name\nAlice\nBob";
    const result = parseCSV(csv);

    expect(result.headers).toEqual(["name"]);
    expect(result.rows).toEqual([["Alice"], ["Bob"]]);
  });

  test("handles single row (headers only)", () => {
    const csv = "a,b,c";
    const result = parseCSV(csv);

    expect(result.headers).toEqual(["a", "b", "c"]);
    expect(result.rows).toEqual([]);
  });

  test("handles real-world CSV with mixed quoting", () => {
    const csv = `company,url,sectors,notes
Acme Inc,https://acme.com,"Software,SaaS",Great company
"Bob's Shop",http://bobs.com,Retail,
Test Co,https://test.io,"AI,ML,Data","Founded in 2020"`;
    const result = parseCSV(csv);

    expect(result.headers).toEqual(["company", "url", "sectors", "notes"]);
    expect(result.rows).toHaveLength(3);
    expect(result.rows[0]).toEqual([
      "Acme Inc",
      "https://acme.com",
      "Software,SaaS",
      "Great company",
    ]);
    expect(result.rows[1]).toEqual(["Bob's Shop", "http://bobs.com", "Retail", ""]);
    expect(result.rows[2]).toEqual(["Test Co", "https://test.io", "AI,ML,Data", "Founded in 2020"]);
  });

  test("handles whitespace in cells (preserved)", () => {
    const csv = "a,b,c\n  spaces  ,\ttabs\t,normal";
    const result = parseCSV(csv);

    expect(result.rows[0]).toEqual(["  spaces  ", "\ttabs\t", "normal"]);
  });

  test("handles unicode characters", () => {
    const csv = "name,city,emoji\n日本語,東京,🎉\nCafé,Zürich,☕";
    const result = parseCSV(csv);

    expect(result.rows[0]).toEqual(["日本語", "東京", "🎉"]);
    expect(result.rows[1]).toEqual(["Café", "Zürich", "☕"]);
  });

  test("handles very long fields", () => {
    const longText = "x".repeat(10000);
    const csv = `a,b\n${longText},short`;
    const result = parseCSV(csv);

    expect(result.rows[0][0]).toHaveLength(10000);
    expect(result.rows[0][1]).toBe("short");
  });

  test("handles quoted field at end of line", () => {
    const csv = 'a,b,c\n1,2,"quoted"';
    const result = parseCSV(csv);

    expect(result.rows[0]).toEqual(["1", "2", "quoted"]);
  });

  test("handles empty quoted field", () => {
    const csv = 'a,b,c\n"",middle,""';
    const result = parseCSV(csv);

    expect(result.rows[0]).toEqual(["", "middle", ""]);
  });

  test("handles consecutive delimiters", () => {
    const csv = "a,b,c,d\n1,,,4";
    const result = parseCSV(csv);

    expect(result.rows[0]).toEqual(["1", "", "", "4"]);
  });
});

describe("sortRows", () => {
  const rows = [
    ["Alice", "30", "NYC"],
    ["Bob", "25", "LA"],
    ["Charlie", "35", "Chicago"],
  ];

  test("sorts alphabetically ascending", () => {
    const sorted = sortRows(rows, 0, "asc");
    expect(sorted[0][0]).toBe("Alice");
    expect(sorted[1][0]).toBe("Bob");
    expect(sorted[2][0]).toBe("Charlie");
  });

  test("sorts alphabetically descending", () => {
    const sorted = sortRows(rows, 0, "desc");
    expect(sorted[0][0]).toBe("Charlie");
    expect(sorted[1][0]).toBe("Bob");
    expect(sorted[2][0]).toBe("Alice");
  });

  test("sorts numerically when values are numbers", () => {
    const sorted = sortRows(rows, 1, "asc");
    expect(sorted[0][1]).toBe("25");
    expect(sorted[1][1]).toBe("30");
    expect(sorted[2][1]).toBe("35");
  });

  test("sorts numerically descending", () => {
    const sorted = sortRows(rows, 1, "desc");
    expect(sorted[0][1]).toBe("35");
    expect(sorted[1][1]).toBe("30");
    expect(sorted[2][1]).toBe("25");
  });

  test("returns original rows for invalid column index", () => {
    const sorted = sortRows(rows, -1, "asc");
    expect(sorted).toEqual(rows);
  });

  test("does not mutate original array", () => {
    const original = [...rows];
    sortRows(rows, 0, "desc");
    expect(rows).toEqual(original);
  });

  test("handles mixed numeric and text values", () => {
    const mixedRows = [
      ["Item", "10"],
      ["Item", "2"],
      ["Item", "abc"],
    ];
    const sorted = sortRows(mixedRows, 1, "asc");
    expect(sorted[0][1]).toBe("2");
    expect(sorted[1][1]).toBe("10");
    expect(sorted[2][1]).toBe("abc");
  });

  test("handles empty rows array", () => {
    const sorted = sortRows([], 0, "asc");
    expect(sorted).toEqual([]);
  });

  test("handles single row", () => {
    const rows = [["Alice", "30"]];
    const sorted = sortRows(rows, 0, "asc");
    expect(sorted).toEqual([["Alice", "30"]]);
  });

  test("handles rows with empty cells", () => {
    const rows = [
      ["Alice", ""],
      ["", "25"],
      ["Charlie", "35"],
    ];
    const sorted = sortRows(rows, 0, "asc");
    expect(sorted[0][0]).toBe("");
    expect(sorted[1][0]).toBe("Alice");
    expect(sorted[2][0]).toBe("Charlie");
  });

  test("stable sort for equal values", () => {
    const rows = [
      ["Alice", "30"],
      ["Bob", "30"],
      ["Charlie", "30"],
    ];
    const sorted = sortRows(rows, 1, "asc");
    expect(sorted[0][0]).toBe("Alice");
    expect(sorted[1][0]).toBe("Bob");
    expect(sorted[2][0]).toBe("Charlie");
  });

  test("handles decimal numbers", () => {
    const rows = [
      ["A", "1.5"],
      ["B", "1.25"],
      ["C", "10.1"],
      ["D", "2"],
    ];
    const sorted = sortRows(rows, 1, "asc");
    expect(sorted.map((r) => r[1])).toEqual(["1.25", "1.5", "2", "10.1"]);
  });

  test("handles negative numbers", () => {
    const rows = [
      ["A", "-5"],
      ["B", "10"],
      ["C", "-20"],
      ["D", "0"],
    ];
    const sorted = sortRows(rows, 1, "asc");
    expect(sorted.map((r) => r[1])).toEqual(["-20", "-5", "0", "10"]);
  });
});

describe("filterRows", () => {
  const rows = [
    ["Alice", "Engineer", "NYC"],
    ["Bob", "Designer", "LA"],
    ["Charlie", "Engineer", "Chicago"],
  ];

  test("filters rows containing query (case-insensitive)", () => {
    const filtered = filterRows(rows, "engineer");
    expect(filtered).toHaveLength(2);
    expect(filtered[0][0]).toBe("Alice");
    expect(filtered[1][0]).toBe("Charlie");
  });

  test("filters by partial match", () => {
    const filtered = filterRows(rows, "li");
    expect(filtered).toHaveLength(2);
    expect(filtered[0][0]).toBe("Alice");
    expect(filtered[1][0]).toBe("Charlie");
  });

  test("matches any column", () => {
    const filtered = filterRows(rows, "NYC");
    expect(filtered).toHaveLength(1);
    expect(filtered[0][0]).toBe("Alice");
  });

  test("returns all rows for empty query", () => {
    expect(filterRows(rows, "")).toEqual(rows);
    expect(filterRows(rows, "   ")).toEqual(rows);
    expect(filterRows(rows, null)).toEqual(rows);
  });

  test("returns empty array when no matches", () => {
    const filtered = filterRows(rows, "xyz");
    expect(filtered).toHaveLength(0);
  });

  test("does not mutate original array", () => {
    const original = [...rows];
    filterRows(rows, "engineer");
    expect(rows).toEqual(original);
  });

  test("handles special regex characters in query", () => {
    const rows = [
      ["Price: $100", "Item"],
      ["(Optional)", "Note"],
      ["test.com", "URL"],
    ];
    expect(filterRows(rows, "$100")).toHaveLength(1);
    expect(filterRows(rows, "(Optional)")).toHaveLength(1);
    expect(filterRows(rows, "test.com")).toHaveLength(1);
  });

  test("handles multiple matches in same row", () => {
    const rows = [
      ["alice@alice.com", "Alice Alice"],
      ["bob@test.com", "Bob Smith"],
    ];
    const filtered = filterRows(rows, "alice");
    expect(filtered).toHaveLength(1);
    expect(filtered[0][1]).toBe("Alice Alice");
  });

  test("handles empty cells in filter", () => {
    const rows = [
      ["Alice", "", "NYC"],
      ["", "Designer", "LA"],
      ["Charlie", "Engineer", ""],
    ];
    const filtered = filterRows(rows, "NYC");
    expect(filtered).toHaveLength(1);
    expect(filtered[0][0]).toBe("Alice");
  });

  test("handles unicode in query", () => {
    const rows = [
      ["東京", "Japan"],
      ["Paris", "France"],
      ["北京", "China"],
    ];
    const filtered = filterRows(rows, "東京");
    expect(filtered).toHaveLength(1);
    expect(filtered[0][1]).toBe("Japan");
  });

  test("handles very long query", () => {
    const longQuery = "a".repeat(1000);
    const rows = [
      [longQuery, "match"],
      ["short", "no match"],
    ];
    const filtered = filterRows(rows, longQuery);
    expect(filtered).toHaveLength(1);
  });
});
