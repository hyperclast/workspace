/**
 * Adversarial and edge-case end-to-end tests for the markdown table widget.
 *
 * The "happy path" lives in table-widget.spec.js. This file intentionally
 * tries to break the widget: malicious content, malformed input, boundary
 * conditions, and unusual structural shapes. All of these must:
 *
 *   - Never produce a <script>/<iframe>/<img> element from cell content
 *   - Never produce a clickable javascript:/data:/vbscript: href
 *   - Either widgetize correctly, or not widgetize at all — but never crash
 *   - Keep cursor-in-table / cursor-out-of-table toggle working
 *
 * Run with:
 *   npm run test:e2e -- table-widget-adversarial.spec.js
 */

import { test, expect } from "@playwright/test";

const BASE_URL = process.env.TEST_BASE_URL || "http://localhost:9800";
const TEST_EMAIL = process.env.TEST_EMAIL || "dev@localhost";
const TEST_PASSWORD = process.env.TEST_PASSWORD || "dev";

async function login(page) {
  await page.goto(`${BASE_URL}/login`);
  await page.waitForSelector("#login-email", { timeout: 10000 });
  await page.fill("#login-email", TEST_EMAIL);
  await page.fill("#login-password", TEST_PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForSelector(".sidebar-new-page-btn", { timeout: 20000 });
}

async function createEmptyPage(page, titlePrefix) {
  const newPageBtn = page.locator(".sidebar-new-page-btn").first();
  await newPageBtn.click();
  const modal = page.locator(".modal");
  await expect(modal).toBeVisible({ timeout: 5000 });
  await page.fill("#page-title-input", `${titlePrefix} ${Date.now()}`);
  await page.click(".modal-btn-primary");
  await page.waitForSelector(".cm-content", { timeout: 10000 });
  await page.waitForTimeout(500);
}

async function setDocContent(page, text) {
  await page.evaluate((t) => {
    const view = window.editorView;
    view.dispatch({
      changes: { from: 0, to: view.state.doc.length, insert: t },
      selection: { anchor: t.length },
    });
  }, text);
  await page.waitForTimeout(200);
}

async function moveCursorTo(page, pos) {
  await page.evaluate((p) => {
    const view = window.editorView;
    view.dispatch({ selection: { anchor: p } });
    view.focus();
  }, pos);
  await page.waitForTimeout(120);
}

test.describe("Table widget — adversarial & edge cases", () => {
  test.setTimeout(120000);

  // ==========================================================================
  // Security: XSS attempts in cell content
  // ==========================================================================

  test("HTML tags in cells render as literal text, never as real DOM", async ({ page }) => {
    await login(page);
    await createEmptyPage(page, "Widget XSS HTML");

    const doc = `| Col A | Col B |
| :---- | :---- |
| <script>window.__pwned = 1</script> | <img src=x onerror="window.__pwned=2"> |
| <iframe src="javascript:alert(1)"></iframe> | plain |

After.
`;
    await setDocContent(page, doc);

    const widget = page.locator(".cm-table-widget");
    await expect(widget).toBeVisible({ timeout: 5000 });

    // No dangerous elements should have been created from cell content.
    const dangerous = await widget.evaluate((tbl) => ({
      scripts: tbl.querySelectorAll("script").length,
      iframes: tbl.querySelectorAll("iframe").length,
      images: tbl.querySelectorAll("img").length,
    }));
    expect(dangerous).toEqual({ scripts: 0, iframes: 0, images: 0 });

    // The raw text is still visible as text in the rendered cells.
    const rowText = await widget.locator("tbody tr").first().textContent();
    expect(rowText).toContain("<script>");
    expect(rowText).toContain("onerror");

    // And no side-effect was executed.
    const pwned = await page.evaluate(() => window.__pwned);
    expect(pwned).toBeUndefined();
  });

  test("javascript: URL in a link is neutralized to #", async ({ page }) => {
    await login(page);
    await createEmptyPage(page, "Widget XSS Link");

    const doc = `| Link             | Note            |
| :--------------- | :-------------- |
| [click](javascript:window.__pwned=1) | bad scheme   |
| [data](data:text/html,<script>window.__pwned=2</script>) | data scheme |
| [safe](https://example.com) | safe scheme |
| [rel](/pages/abc/) | relative |

After.
`;
    await setDocContent(page, doc);
    const widget = page.locator(".cm-table-widget");
    await expect(widget).toBeVisible({ timeout: 5000 });

    // Enumerate every <a> href — dangerous schemes must have been rewritten to #.
    const hrefs = await widget.evaluate((tbl) =>
      Array.from(tbl.querySelectorAll("a")).map((a) => ({
        href: a.getAttribute("href"),
        text: a.textContent,
      }))
    );

    // Must have at least our four anchors.
    expect(hrefs.length).toBeGreaterThanOrEqual(4);

    for (const { href } of hrefs) {
      const lower = (href || "").toLowerCase();
      expect(lower.startsWith("javascript:")).toBe(false);
      expect(lower.startsWith("data:")).toBe(false);
      expect(lower.startsWith("vbscript:")).toBe(false);
    }

    // The safe URLs should have survived unchanged.
    const safeHrefs = hrefs.map((h) => h.href);
    expect(safeHrefs).toContain("https://example.com");
    expect(safeHrefs).toContain("/pages/abc/");

    // Clicking the neutralized link must not execute script.
    const badLink = widget.locator("a", { hasText: "click" }).first();
    await badLink.click({ noWaitAfter: true }).catch(() => {});
    await page.waitForTimeout(200);
    const pwned = await page.evaluate(() => window.__pwned);
    expect(pwned).toBeUndefined();
  });

  // ==========================================================================
  // Malformed / unusual markdown
  // ==========================================================================

  test("unclosed inline markers render as literal text inside cells", async ({ page }) => {
    await login(page);
    await createEmptyPage(page, "Widget Malformed Inline");

    const doc = `| Header |
| :----- |
| unclosed \`code  |
| **bold |
| *italic |
| ~~strike |
| [link](no-close |

After.
`;
    await setDocContent(page, doc);
    const widget = page.locator(".cm-table-widget");
    await expect(widget).toBeVisible({ timeout: 5000 });

    const rowsText = await widget.evaluate((tbl) =>
      Array.from(tbl.querySelectorAll("tbody tr")).map((r) => r.textContent)
    );
    expect(rowsText.length).toBe(5);

    // Each unclosed marker must still be visible as text.
    expect(rowsText[0]).toContain("`");
    expect(rowsText[1]).toContain("**bold");
    expect(rowsText[2]).toContain("*italic");
    expect(rowsText[3]).toContain("~~strike");
    expect(rowsText[4]).toContain("[link](no-close");

    // And none of them should have produced a real element of the formatting type.
    const elementCounts = await widget.evaluate((tbl) => ({
      codes: tbl.querySelectorAll("tbody code").length,
      strongs: tbl.querySelectorAll("tbody strong").length,
      ems: tbl.querySelectorAll("tbody em").length,
      dels: tbl.querySelectorAll("tbody del").length,
      links: tbl.querySelectorAll("tbody a").length,
    }));
    expect(elementCounts).toEqual({ codes: 0, strongs: 0, ems: 0, dels: 0, links: 0 });
  });

  test("empty cells and whitespace-only cells render without breaking layout", async ({ page }) => {
    await login(page);
    await createEmptyPage(page, "Widget Empty Cells");

    const doc = `| A | B | C |
| :- | :- | :- |
|   |   |   |
| x |   | z |
|   | y |   |

End.
`;
    await setDocContent(page, doc);
    const widget = page.locator(".cm-table-widget");
    await expect(widget).toBeVisible({ timeout: 5000 });

    const rows = widget.locator("tbody tr");
    await expect(rows).toHaveCount(3);

    // Every row must have exactly 3 cells, even when some are blank.
    const colCounts = await widget.evaluate((tbl) =>
      Array.from(tbl.querySelectorAll("tbody tr")).map((r) => r.querySelectorAll("td").length)
    );
    expect(colCounts).toEqual([3, 3, 3]);

    // Columns stay pixel-aligned even with empty cells.
    const columnXs = await widget.evaluate((tbl) => {
      const xs = [];
      for (const row of tbl.querySelectorAll("tr")) {
        row.querySelectorAll("th, td").forEach((c, col) => {
          if (!xs[col]) xs[col] = [];
          xs[col].push(Math.round(c.getBoundingClientRect().left));
        });
      }
      return xs;
    });
    for (const xs of columnXs) {
      for (const x of xs) expect(Math.abs(x - xs[0])).toBeLessThanOrEqual(1);
    }
  });

  test("uneven row column counts do not crash the widget", async ({ page }) => {
    await login(page);
    await createEmptyPage(page, "Widget Uneven Rows");

    // Row 1 has 2 cells, row 2 has 4 cells, row 3 has 3 cells.
    const doc = `| A | B | C |
| :- | :- | :- |
| 1 | 2 |
| 1 | 2 | 3 | 4 |
| 1 | 2 | 3 |

End.
`;
    await setDocContent(page, doc);
    const widget = page.locator(".cm-table-widget");
    await expect(widget).toBeVisible({ timeout: 5000 });

    // Widget should render — we don't assert a specific column count since the
    // parser's column count is max-across-rows. The guarantee is: no crash, no
    // XSS, rows are present, and the table is internally consistent.
    await expect(widget.locator("tbody tr")).toHaveCount(3);
    const scripts = await widget.evaluate((tbl) => tbl.querySelectorAll("script").length);
    expect(scripts).toBe(0);

    // All trs in the body must have the same number of cells (grid-like output).
    const counts = await widget.evaluate((tbl) =>
      Array.from(tbl.querySelectorAll("tbody tr")).map((r) => r.querySelectorAll("td").length)
    );
    const first = counts[0];
    for (const c of counts) expect(c).toBe(first);
  });

  // ==========================================================================
  // Structural edge cases
  // ==========================================================================

  test("table immediately at document start renders correctly", async ({ page }) => {
    await login(page);
    await createEmptyPage(page, "Widget Doc Start");

    const doc = `| A | B |
| :- | :- |
| 1 | 2 |

Body.
`;
    await setDocContent(page, doc);
    const widget = page.locator(".cm-table-widget");
    await expect(widget).toBeVisible({ timeout: 5000 });
    await expect(widget.locator("thead th")).toHaveCount(2);
    await expect(widget.locator("tbody tr")).toHaveCount(1);
  });

  test("table at document end (no trailing newline) renders correctly", async ({ page }) => {
    await login(page);
    await createEmptyPage(page, "Widget Doc End");

    const doc = `Intro paragraph.

| A | B |
| :- | :- |
| 1 | 2 |
| 3 | 4 |`;
    await setDocContent(page, doc);
    // Move cursor to the very start so selection is outside the table.
    await moveCursorTo(page, 0);
    const widget = page.locator(".cm-table-widget");
    await expect(widget).toBeVisible({ timeout: 5000 });
    await expect(widget.locator("tbody tr")).toHaveCount(2);
  });

  test("two adjacent tables each widgetize independently", async ({ page }) => {
    await login(page);
    await createEmptyPage(page, "Widget Two Tables");

    const doc = `Intro.

| A | B |
| :- | :- |
| 1 | 2 |

Middle paragraph.

| X | Y | Z |
| :- | :- | :- |
| a | b | c |
| d | e | f |

End.
`;
    await setDocContent(page, doc);
    await expect(page.locator(".cm-table-widget")).toHaveCount(2, { timeout: 5000 });

    // Move cursor into the first table's source. Only the first widget drops.
    await page.evaluate(() => {
      const view = window.editorView;
      const idx = view.state.doc.toString().indexOf("| 1 | 2 |");
      view.dispatch({ selection: { anchor: idx + 2 } });
      view.focus();
    });
    await page.waitForTimeout(200);
    await expect(page.locator(".cm-table-widget")).toHaveCount(1);

    // Both come back when cursor moves to doc start.
    await moveCursorTo(page, 0);
    await expect(page.locator(".cm-table-widget")).toHaveCount(2);
  });

  test("header+separator with no data rows still renders header", async ({ page }) => {
    await login(page);
    await createEmptyPage(page, "Widget No Data");

    const doc = `| A | B |
| :- | :- |

After.
`;
    await setDocContent(page, doc);
    const widget = page.locator(".cm-table-widget");
    await expect(widget).toBeVisible({ timeout: 5000 });
    await expect(widget.locator("thead th")).toHaveCount(2);
    await expect(widget.locator("tbody tr")).toHaveCount(0);
  });

  // ==========================================================================
  // Content edge cases
  // ==========================================================================

  test("unicode, emoji, and RTL text in cells render as text", async ({ page }) => {
    await login(page);
    await createEmptyPage(page, "Widget Unicode");

    const doc = `| Script  | Sample          |
| :------ | :-------------- |
| Emoji   | 🎉 🚀 💯        |
| CJK     | 你好，世界      |
| Arabic  | مرحبا بالعالم   |
| Combined | café → über |

End.
`;
    await setDocContent(page, doc);
    const widget = page.locator(".cm-table-widget");
    await expect(widget).toBeVisible({ timeout: 5000 });

    const text = await widget.textContent();
    expect(text).toContain("🎉");
    expect(text).toContain("你好");
    expect(text).toContain("مرحبا");
    expect(text).toContain("café");
  });

  test("very wide table (many columns) renders with pixel-aligned columns", async ({ page }) => {
    await login(page);
    await createEmptyPage(page, "Widget Wide Table");

    const cols = 8;
    const header = "| " + Array.from({ length: cols }, (_, i) => `C${i}`).join(" | ") + " |";
    const sep = "| " + Array.from({ length: cols }, () => ":-").join(" | ") + " |";
    const rows = [];
    for (let r = 0; r < 5; r++) {
      rows.push("| " + Array.from({ length: cols }, (_, i) => `r${r}c${i}`).join(" | ") + " |");
    }
    const doc = `${header}\n${sep}\n${rows.join("\n")}\n\nAfter.\n`;
    await setDocContent(page, doc);
    const widget = page.locator(".cm-table-widget");
    await expect(widget).toBeVisible({ timeout: 5000 });

    await expect(widget.locator("thead th")).toHaveCount(cols);
    await expect(widget.locator("tbody tr")).toHaveCount(5);

    const columnXs = await widget.evaluate((tbl) => {
      const xs = [];
      for (const row of tbl.querySelectorAll("tr")) {
        row.querySelectorAll("th, td").forEach((c, col) => {
          if (!xs[col]) xs[col] = [];
          xs[col].push(Math.round(c.getBoundingClientRect().left));
        });
      }
      return xs;
    });
    expect(columnXs.length).toBe(cols);
    for (const xs of columnXs) {
      for (const x of xs) expect(Math.abs(x - xs[0])).toBeLessThanOrEqual(1);
    }
  });

  // ==========================================================================
  // Selection / toggle dynamics
  // ==========================================================================

  test("rapid cursor in/out toggling does not crash or leak decorations", async ({ page }) => {
    await login(page);
    await createEmptyPage(page, "Widget Rapid Toggle");

    const doc = `Before.

| A | B |
| :- | :- |
| 1 | 2 |
| 3 | 4 |

After.
`;
    await setDocContent(page, doc);
    await expect(page.locator(".cm-table-widget")).toBeVisible({ timeout: 5000 });

    // Toggle 20 times in quick succession.
    for (let i = 0; i < 20; i++) {
      await page.evaluate(() => {
        const view = window.editorView;
        const text = view.state.doc.toString();
        const inside = text.indexOf("| 1 |") + 2;
        view.dispatch({ selection: { anchor: inside } });
      });
      await page.evaluate(() => {
        const view = window.editorView;
        view.dispatch({ selection: { anchor: 0 } });
      });
    }
    await page.waitForTimeout(200);

    // Final state: cursor at 0, widget should be visible and there should be
    // exactly one widget (no duplicates / stale decorations).
    await expect(page.locator(".cm-table-widget")).toHaveCount(1);

    // Also: no stale raw-table decorations leaking while widget is up.
    await expect(page.locator(".cm-table-row")).toHaveCount(0);
  });

  test("selection spanning table boundary drops the widget", async ({ page }) => {
    await login(page);
    await createEmptyPage(page, "Widget Selection Span");

    const doc = `Before paragraph.

| A | B |
| :- | :- |
| 1 | 2 |

After.
`;
    await setDocContent(page, doc);
    await expect(page.locator(".cm-table-widget")).toBeVisible({ timeout: 5000 });

    // Select from outside the table into the middle of it.
    await page.evaluate(() => {
      const view = window.editorView;
      const text = view.state.doc.toString();
      const start = text.indexOf("Before paragraph") + 3;
      const end = text.indexOf("| 1 | 2 |") + 5;
      view.dispatch({ selection: { anchor: start, head: end } });
      view.focus();
    });
    await page.waitForTimeout(200);

    // Widget should be gone because the selection intersects the table.
    await expect(page.locator(".cm-table-widget")).toHaveCount(0);
    // And the raw decorations should be back.
    expect(await page.locator(".cm-table-row").count()).toBeGreaterThan(0);
  });
});
