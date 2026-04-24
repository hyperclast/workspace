/**
 * End-to-end tests for the rendered markdown table widget.
 *
 * When the cursor is outside a markdown pipe table, the editor replaces
 * the raw pipe-delimited source with an actual HTML <table>. When the
 * cursor (selection) re-enters the table range, the widget drops out and
 * the raw source comes back for editing.
 *
 * Covered:
 *  - Widget renders when cursor is outside the table.
 *  - Columns are actually aligned — every row's <td> in a given column
 *    starts at the same x-coordinate (this is the whole point of the fix).
 *  - Inline backtick chips inside cells render as <code>.
 *  - Clicking a cell moves the cursor into the source and drops the widget.
 *  - Moving the cursor back outside brings the widget back.
 *
 * Run with:
 *   npx playwright test table-widget.spec.js --headed
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
  // The sidebar always loads; the editor's .cm-content only appears once a
  // page is opened, so wait for the project sidebar and let callers create a
  // page to get the editor up.
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

/**
 * Insert the document contents directly via the CodeMirror view so we don't
 * have to rely on the auto-format / paste-detection pipeline (which can add
 * padding, escape pipes, etc. and obscures what we're actually testing).
 */
async function setDocContent(page, text) {
  await page.evaluate((t) => {
    const view = window.editorView;
    view.dispatch({
      changes: { from: 0, to: view.state.doc.length, insert: t },
      selection: { anchor: t.length },
    });
  }, text);
  // Allow a frame for decorations to rebuild.
  await page.waitForTimeout(200);
}

async function moveCursorTo(page, pos) {
  await page.evaluate((p) => {
    const view = window.editorView;
    view.dispatch({ selection: { anchor: p } });
    view.focus();
  }, pos);
  await page.waitForTimeout(150);
}

const SAMPLE_TABLE = `Before table.

| View                        | Domain                                            |
| :-------------------------- | :------------------------------------------------ |
| \`v0r0.mxr_person\`           | Unified person record across data sources         |
| \`v0r0.mxr_company\`          | Unified company record across data sources        |
| \`v0r0.lkd_profile\`          | LinkedIn people profiles                          |
| \`v0r0.lkd_profile_snapshot\` | Historical snapshots of LinkedIn people profiles  |
| \`v0r0.lkd_company_snapshot\` | Historical snapshots of LinkedIn company profiles |
| \`v0r0.ghb_profile\`          | GitHub profiles                                   |

After table.
`;

test.describe("Markdown table widget", () => {
  test.setTimeout(90000);

  test("renders a real <table> when the cursor is outside the table", async ({ page }) => {
    await login(page);
    await createEmptyPage(page, "Table Widget Test");
    await setDocContent(page, SAMPLE_TABLE);

    // Cursor is at end-of-doc (after "After table.\n"), which is outside the table.
    // Widget should be present.
    const widget = page.locator(".cm-table-widget");
    await expect(widget).toBeVisible({ timeout: 5000 });

    // The widget should have one <thead> row and the right number of data rows.
    const headerCells = widget.locator("thead th");
    await expect(headerCells).toHaveCount(2);
    await expect(headerCells.nth(0)).toHaveText("View");
    await expect(headerCells.nth(1)).toHaveText("Domain");

    const dataRows = widget.locator("tbody tr");
    await expect(dataRows).toHaveCount(6);

    // The raw per-line table decorations must NOT be present while the widget
    // is showing, or we'd be rendering the table twice.
    const rawTableLines = page.locator(".cm-table-row");
    await expect(rawTableLines).toHaveCount(0);
  });

  test("inline backtick chips render as <code> inside cells", async ({ page }) => {
    await login(page);
    await createEmptyPage(page, "Table Widget Chip Test");
    await setDocContent(page, SAMPLE_TABLE);

    const firstDataRow = page.locator(".cm-table-widget tbody tr").first();
    await expect(firstDataRow).toBeVisible({ timeout: 5000 });

    const chip = firstDataRow.locator("code.cm-table-widget-code").first();
    await expect(chip).toBeVisible();
    await expect(chip).toHaveText("v0r0.mxr_person");

    // No raw backticks should leak into the rendered output.
    const rowText = await firstDataRow.textContent();
    expect(rowText).not.toContain("`");
  });

  test("columns are pixel-aligned across rows", async ({ page }) => {
    await login(page);
    await createEmptyPage(page, "Table Widget Alignment");
    await setDocContent(page, SAMPLE_TABLE);

    const widget = page.locator(".cm-table-widget");
    await expect(widget).toBeVisible({ timeout: 5000 });

    // Gather every cell's {column index, left x}. All cells in a given
    // column must start at the exact same x — that's what a real <table>
    // buys us, and the whole reason for the widget.
    const columnXs = await widget.evaluate((tbl) => {
      const xsByCol = [];
      const allRows = tbl.querySelectorAll("tr");
      for (const row of allRows) {
        const cells = row.querySelectorAll("th, td");
        cells.forEach((cell, col) => {
          const rect = cell.getBoundingClientRect();
          if (!xsByCol[col]) xsByCol[col] = [];
          xsByCol[col].push(Math.round(rect.left));
        });
      }
      return xsByCol;
    });

    expect(columnXs.length).toBe(2);
    for (let col = 0; col < columnXs.length; col++) {
      const xs = columnXs[col];
      expect(xs.length).toBeGreaterThan(1);
      const first = xs[0];
      for (const x of xs) {
        // Exact match: this is what was broken in the decoration-on-source
        // approach and is what the widget fixes. Allow 1px of slack for
        // subpixel rounding quirks but no more.
        expect(Math.abs(x - first)).toBeLessThanOrEqual(1);
      }
    }
  });

  test("clicking a cell drops the widget and puts the cursor in the source", async ({ page }) => {
    await login(page);
    await createEmptyPage(page, "Table Widget Click");
    await setDocContent(page, SAMPLE_TABLE);

    // Confirm the widget is initially present.
    const widget = page.locator(".cm-table-widget");
    await expect(widget).toBeVisible({ timeout: 5000 });

    // Click the "LinkedIn people profiles" cell.
    const targetCell = widget.locator("td", { hasText: "LinkedIn people profiles" }).first();
    await targetCell.click();
    await page.waitForTimeout(300);

    // The widget must be gone now — we're editing the raw source of that table.
    await expect(widget).toHaveCount(0);

    // And the per-line table decorations should be back.
    const rawTableLines = page.locator(".cm-table-row");
    const rawRowCount = await rawTableLines.count();
    expect(rawRowCount).toBeGreaterThan(0);

    // The cursor should be inside the source of the table (specifically, in
    // the range of the row we clicked). Verify by inspecting the selection.
    const selInfo = await page.evaluate(() => {
      const view = window.editorView;
      const head = view.state.selection.main.head;
      const line = view.state.doc.lineAt(head);
      return { head, lineText: line.text };
    });
    expect(selInfo.lineText).toContain("LinkedIn people profiles");
  });

  test("widget comes back when cursor leaves the table", async ({ page }) => {
    await login(page);
    await createEmptyPage(page, "Table Widget Toggle");
    await setDocContent(page, SAMPLE_TABLE);

    const widget = page.locator(".cm-table-widget");
    await expect(widget).toBeVisible({ timeout: 5000 });

    // Move cursor into the table, widget drops.
    await page.evaluate(() => {
      const view = window.editorView;
      const text = view.state.doc.toString();
      const idx = text.indexOf("`v0r0.mxr_person`");
      view.dispatch({ selection: { anchor: idx + 2 } });
      view.focus();
    });
    await page.waitForTimeout(200);
    await expect(widget).toHaveCount(0);

    // Move cursor far outside the table, widget reappears.
    await moveCursorTo(page, 0);
    await expect(page.locator(".cm-table-widget")).toBeVisible({ timeout: 3000 });
  });
});
