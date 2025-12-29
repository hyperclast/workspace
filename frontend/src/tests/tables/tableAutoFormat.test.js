/**
 * Tests for table auto-formatting when cursor leaves the table
 */
import { describe, test, expect, beforeEach, afterEach } from "vitest";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { markdownTableExtension, tablesField } from "../../markdownTable.js";

describe("Table auto-format on cursor leave", () => {
  let view;
  let container;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
  });

  afterEach(() => {
    if (view) {
      view.destroy();
      view = null;
    }
    if (container) {
      container.remove();
      container = null;
    }
  });

  test("formats table when cursor moves out of table", async () => {
    // Create a misaligned table
    const doc = `Some text before

| Name | Age |
|---|---|
| Alice | 30 |

Some text after`;

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [markdownTableExtension],
      }),
      parent: container,
    });

    // Position cursor inside the table (in "Alice" cell)
    const alicePos = doc.indexOf("Alice");
    view.dispatch({
      selection: { anchor: alicePos },
    });

    // Now move cursor outside the table (to "Some text after")
    const afterPos = doc.indexOf("Some text after");
    view.dispatch({
      selection: { anchor: afterPos },
    });

    // Wait a tick for the formatting to be applied
    await new Promise((resolve) => setTimeout(resolve, 10));

    // The table should now be formatted with aligned columns
    const newDoc = view.state.doc.toString();

    // Check that columns are aligned (Name and Alice should have same width)
    const lines = newDoc.split("\n");
    const headerLine = lines.find((l) => l.includes("Name"));
    const dataLine = lines.find((l) => l.includes("Alice"));

    // Both lines should have the same structure with aligned pipes
    expect(headerLine).toContain("| Name  |");
    expect(dataLine).toContain("| Alice |");
  });

  test("does not format when cursor moves within same table", async () => {
    const doc = `| Name | Age |
|------|-----|
| Alice | 30 |`;

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [markdownTableExtension],
      }),
      parent: container,
    });

    // Get the original content
    const originalDoc = view.state.doc.toString();

    // Position cursor in "Name" cell
    view.dispatch({
      selection: { anchor: 2 },
    });

    // Move cursor to "Alice" cell (still in same table)
    const alicePos = doc.indexOf("Alice");
    view.dispatch({
      selection: { anchor: alicePos },
    });

    await new Promise((resolve) => setTimeout(resolve, 10));

    // Content should be unchanged (no formatting triggered)
    expect(view.state.doc.toString()).toBe(originalDoc);
  });

  test("formats misaligned table with varying cell widths", async () => {
    const doc = `Text

| A | Very Long Header |
|---|---|
| Short | X |

End`;

    view = new EditorView({
      state: EditorState.create({
        doc,
        extensions: [markdownTableExtension],
      }),
      parent: container,
    });

    // Position cursor inside the table
    const shortPos = doc.indexOf("Short");
    view.dispatch({
      selection: { anchor: shortPos },
    });

    // Move cursor outside
    const endPos = doc.indexOf("End");
    view.dispatch({
      selection: { anchor: endPos },
    });

    await new Promise((resolve) => setTimeout(resolve, 10));

    const newDoc = view.state.doc.toString();

    // The separator row should now have proper dashes matching column widths
    expect(newDoc).toContain("Very Long Header");
    // The short values should be padded
    const lines = newDoc.split("\n");
    const dataLine = lines.find((l) => l.includes("Short"));
    expect(dataLine).toMatch(/Short\s+\|/);
  });
});
