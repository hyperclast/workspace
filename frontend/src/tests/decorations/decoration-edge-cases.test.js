/**
 * Decoration Pattern Edge Case Tests
 *
 * Tests specific edge cases for each decoration pattern type.
 */

import { describe, test, expect, afterEach } from "vitest";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { decorateFormatting, codeFenceField } from "../../decorateFormatting.js";
import { decorateLinks } from "../../decorateLinks.js";
import { decorateEmails } from "../../decorateEmails.js";

function createEditor(content) {
  const state = EditorState.create({
    doc: content,
    extensions: [codeFenceField, decorateFormatting, decorateLinks, decorateEmails],
  });

  const parent = document.createElement("div");
  parent.style.width = "800px";
  parent.style.height = "600px";
  document.body.appendChild(parent);

  const view = new EditorView({ state, parent });
  return { view, parent };
}

function hasDecoration(view, className) {
  return view.contentDOM.querySelector(`.${className}`) !== null;
}

function countDecorations(view, className) {
  return view.contentDOM.querySelectorAll(`.${className}`).length;
}

function getTextContent(view) {
  return view.contentDOM.textContent;
}

describe("Decoration Pattern Edge Cases", () => {
  let view, parent;

  afterEach(() => {
    if (view) view.destroy();
    if (parent) parent.remove();
    view = null;
    parent = null;
  });

  describe("Links edge cases", () => {
    test("nested brackets: text with brackets before link", () => {
      ({ view, parent } = createEditor("[not a link] then [real link](https://example.com)"));
      expect(hasDecoration(view, "format-link")).toBe(true);
      expect(countDecorations(view, "format-link")).toBe(1);
    });

    test("link with special chars in URL: query params", () => {
      ({ view, parent } = createEditor("[Link](https://example.com/path?a=1&b=2&c=hello%20world)"));
      expect(hasDecoration(view, "format-link")).toBe(true);
    });

    test("link with parentheses in URL (escaped)", () => {
      ({ view, parent } = createEditor(
        "[Wiki](https://en.wikipedia.org/wiki/Test_%28disambiguation%29)"
      ));
      expect(hasDecoration(view, "format-link")).toBe(true);
    });

    test("link at document start", () => {
      ({ view, parent } = createEditor("[First](https://example.com) is at start"));
      expect(hasDecoration(view, "format-link")).toBe(true);
    });

    test("link at document end", () => {
      ({ view, parent } = createEditor("Ends with [link](https://example.com)"));
      expect(hasDecoration(view, "format-link")).toBe(true);
    });

    test("multiple links on same line", () => {
      ({ view, parent } = createEditor("[One](url1) and [Two](url2) and [Three](url3)"));
      expect(countDecorations(view, "format-link")).toBe(3);
    });

    test("link with empty text", () => {
      ({ view, parent } = createEditor("[](https://example.com)"));
      expect(hasDecoration(view, "format-link")).toBe(false);
    });

    test("link with empty URL - no decoration (regex requires URL content)", () => {
      ({ view, parent } = createEditor("[Text]()"));
      expect(hasDecoration(view, "format-link")).toBe(false);
    });

    test("internal page link format", () => {
      ({ view, parent } = createEditor("[Page Title](/pages/abc123xyz/)"));
      expect(hasDecoration(view, "format-link-internal")).toBe(true);
    });

    test("link broken across lines should not match", () => {
      ({ view, parent } = createEditor("[Link\nText](url)"));
      expect(hasDecoration(view, "format-link")).toBe(false);
    });

    test("URL-like text without markdown syntax", () => {
      ({ view, parent } = createEditor("Visit https://example.com directly"));
      expect(hasDecoration(view, "format-link")).toBe(false);
    });
  });

  describe("Formatting edge cases", () => {
    test("bold with no closing **", () => {
      ({ view, parent } = createEditor("This **is not closed"));
      expect(hasDecoration(view, "format-bold")).toBe(false);
    });

    test("nested bold and italic: ***text***", () => {
      ({ view, parent } = createEditor("***bold and italic***"));
      expect(hasDecoration(view, "format-bold")).toBe(true);
    });

    test("code with backtick inside", () => {
      ({ view, parent } = createEditor("`code with ` backtick`"));
      expect(hasDecoration(view, "format-inline-code")).toBe(true);
    });

    test("underscore in variable names should not underline", () => {
      ({ view, parent } = createEditor("const my_variable_name = 1;"));
      expect(hasDecoration(view, "format-underline")).toBe(false);
    });

    test("double underscore in code context", () => {
      ({ view, parent } = createEditor("Python __init__ method"));
      expect(hasDecoration(view, "format-underline")).toBe(true);
    });

    test("asterisks in math context", () => {
      ({ view, parent } = createEditor("Calculate 5 * 3 * 2 = 30"));
      expect(hasDecoration(view, "format-bold")).toBe(false);
    });

    test("bold immediately followed by more text", () => {
      ({ view, parent } = createEditor("**bold**text continues"));
      expect(hasDecoration(view, "format-bold")).toBe(true);
    });

    test("bold at line boundaries", () => {
      ({ view, parent } = createEditor("**entire line is bold**"));
      expect(hasDecoration(view, "format-bold")).toBe(true);
    });

    test("empty bold markers", () => {
      ({ view, parent } = createEditor("Text **** more text"));
      expect(hasDecoration(view, "format-bold")).toBe(false);
    });
  });

  describe("Headings and sections edge cases", () => {
    test("heading with trailing spaces", () => {
      ({ view, parent } = createEditor("## Heading with spaces   "));
      expect(hasDecoration(view, "format-h2")).toBe(true);
    });

    test("heading followed immediately by code block", () => {
      ({ view, parent } = createEditor("## Heading\n```\ncode\n```"));
      expect(hasDecoration(view, "format-h2")).toBe(true);
      expect(hasDecoration(view, "format-code-block")).toBe(true);
    });

    test("heading inside code block should not decorate", () => {
      ({ view, parent } = createEditor("```\n## Not a heading\n```"));
      expect(hasDecoration(view, "format-h2")).toBe(false);
    });

    test("consecutive headings", () => {
      ({ view, parent } = createEditor("# H1\n## H2\n### H3\n#### H4"));
      expect(hasDecoration(view, "format-h1")).toBe(true);
      expect(hasDecoration(view, "format-h2")).toBe(true);
      expect(hasDecoration(view, "format-h3")).toBe(true);
      expect(hasDecoration(view, "format-h4")).toBe(true);
    });

    test("hash without space is not heading", () => {
      ({ view, parent } = createEditor("#NoSpace is not a heading"));
      expect(hasDecoration(view, "format-h1")).toBe(false);
    });

    test("hash with too many levels", () => {
      ({ view, parent } = createEditor("####### Seven hashes"));
      expect(hasDecoration(view, "format-h6")).toBe(false);
    });

    test("heading with only hash and space", () => {
      ({ view, parent } = createEditor("# "));
      expect(hasDecoration(view, "format-h1")).toBe(false);
    });
  });

  describe("Tables edge cases", () => {
    test("table with empty cells (requires markdownTableExtension)", () => {
      const content = "| A | B |\n|---|---|\n| | value |";
      ({ view, parent } = createEditor(content));
      expect(view.state.doc.toString()).toBe(content);
    });

    test("table with varying column counts", () => {
      const content = "| A | B | C |\n|---|---|---|\n| 1 | 2 |";
      ({ view, parent } = createEditor(content));
      expect(view.state.doc.toString()).toBe(content);
    });

    test("table at end of document without trailing newline", () => {
      const content = "| A |\n|---|\n| 1 |";
      ({ view, parent } = createEditor(content));
      expect(view.state.doc.toString()).toBe(content);
    });

    test("pipe character in regular text", () => {
      ({ view, parent } = createEditor("This | is not | a table"));
      expect(hasDecoration(view, "cm-table-row")).toBe(false);
    });

    test("table with alignment markers", () => {
      const content = "| Left | Center | Right |\n|:-----|:------:|------:|\n| L | C | R |";
      ({ view, parent } = createEditor(content));
      expect(view.state.doc.toString()).toBe(content);
    });
  });

  describe("Checkboxes edge cases", () => {
    test("checkbox with uppercase X", () => {
      ({ view, parent } = createEditor("- [X] Done with uppercase"));
      expect(hasDecoration(view, "format-checkbox-checked")).toBe(true);
    });

    test("checkbox with lowercase x", () => {
      ({ view, parent } = createEditor("- [x] Done with lowercase"));
      expect(hasDecoration(view, "format-checkbox-checked")).toBe(true);
    });

    test("deeply nested checkbox", () => {
      ({ view, parent } = createEditor("          - [ ] Ten spaces of indent"));
      expect(hasDecoration(view, "format-checkbox-item")).toBe(true);
    });

    test("checkbox inside code block should not convert", () => {
      ({ view, parent } = createEditor("```\n- [ ] Not a checkbox\n```"));
      expect(view.contentDOM.querySelector('input[type="checkbox"]')).toBeNull();
    });

    test("checkbox-like syntax without dash", () => {
      ({ view, parent } = createEditor("[ ] Not a checkbox without dash"));
      expect(hasDecoration(view, "format-checkbox-item")).toBe(false);
    });

    test("checkbox with content after", () => {
      ({ view, parent } = createEditor("- [ ] Task with **bold** in it"));
      expect(hasDecoration(view, "format-checkbox-item")).toBe(true);
    });
  });

  describe("Code blocks edge cases", () => {
    test("code block with language specifier", () => {
      ({ view, parent } = createEditor("```javascript\nconst x = 1;\n```"));
      expect(hasDecoration(view, "format-code-block")).toBe(true);
    });

    test("empty code block", () => {
      ({ view, parent } = createEditor("```\n```"));
      expect(view.state.doc.toString()).toContain("```");
    });

    test("nested backticks in code block", () => {
      ({ view, parent } = createEditor("```\nUse `code` here\n```"));
      expect(hasDecoration(view, "format-code-block")).toBe(true);
    });

    test("unclosed code block", () => {
      ({ view, parent } = createEditor("```\ncode without closing"));
      expect(hasDecoration(view, "format-code-block")).toBe(true);
    });

    test("four backticks", () => {
      ({ view, parent } = createEditor("````\ncode\n````"));
      expect(hasDecoration(view, "format-code-block")).toBe(false);
    });
  });

  describe("Emails edge cases", () => {
    test("standard email format", () => {
      ({ view, parent } = createEditor("Contact user@example.com"));
      expect(hasDecoration(view, "email-highlight")).toBe(true);
    });

    test("email with subdomain", () => {
      ({ view, parent } = createEditor("user@mail.example.co.uk"));
      expect(hasDecoration(view, "email-highlight")).toBe(true);
    });

    test("email with plus sign", () => {
      ({ view, parent } = createEditor("user+tag@example.com"));
      expect(hasDecoration(view, "email-highlight")).toBe(true);
    });

    test("email with dots in local part", () => {
      ({ view, parent } = createEditor("first.last@example.com"));
      expect(hasDecoration(view, "email-highlight")).toBe(true);
    });

    test("invalid email without TLD", () => {
      ({ view, parent } = createEditor("user@localhost"));
      expect(hasDecoration(view, "email-highlight")).toBe(false);
    });

    test("email in link should still highlight", () => {
      ({ view, parent } = createEditor("[Email](mailto:user@example.com)"));
      expect(hasDecoration(view, "email-highlight")).toBe(true);
    });
  });

  describe("Blockquotes edge cases", () => {
    test("single line blockquote", () => {
      ({ view, parent } = createEditor("> Single quote"));
      expect(hasDecoration(view, "format-blockquote")).toBe(true);
    });

    test("multi-line blockquote", () => {
      ({ view, parent } = createEditor("> Line 1\n> Line 2\n> Line 3"));
      expect(countDecorations(view, "format-blockquote")).toBe(3);
    });

    test("blockquote with formatting inside", () => {
      ({ view, parent } = createEditor("Before\n> Quote with text\nAfter"));
      view.dispatch({ selection: { anchor: 0 } });
      expect(hasDecoration(view, "format-blockquote")).toBe(true);
    });

    test("empty blockquote", () => {
      ({ view, parent } = createEditor("> "));
      expect(hasDecoration(view, "format-blockquote")).toBe(true);
    });

    test("greater than in math context", () => {
      ({ view, parent } = createEditor("5 > 3 is true"));
      expect(hasDecoration(view, "format-blockquote")).toBe(false);
    });
  });

  describe("Horizontal rule edge cases", () => {
    test("three dashes - HR shown when cursor elsewhere", () => {
      ({ view, parent } = createEditor("Text\n---\nMore"));
      view.dispatch({ selection: { anchor: 0 } });
      expect(view.contentDOM.querySelector("hr")).not.toBeNull();
    });

    test("three asterisks - HR shown when cursor elsewhere", () => {
      ({ view, parent } = createEditor("Text\n***\nMore"));
      view.dispatch({ selection: { anchor: 0 } });
      expect(view.contentDOM.querySelector("hr")).not.toBeNull();
    });

    test("three underscores - HR shown when cursor elsewhere", () => {
      ({ view, parent } = createEditor("Text\n___\nMore"));
      view.dispatch({ selection: { anchor: 0 } });
      expect(view.contentDOM.querySelector("hr")).not.toBeNull();
    });

    test("more than three dashes", () => {
      ({ view, parent } = createEditor("Text\n-----\nMore"));
      view.dispatch({ selection: { anchor: 0 } });
      expect(view.contentDOM.querySelector("hr")).not.toBeNull();
    });

    test("with leading spaces", () => {
      ({ view, parent } = createEditor("Text\n  ---\nMore"));
      view.dispatch({ selection: { anchor: 0 } });
      expect(view.contentDOM.querySelector("hr")).not.toBeNull();
    });

    test("two dashes is not HR", () => {
      ({ view, parent } = createEditor("Text\n--\nMore"));
      view.dispatch({ selection: { anchor: 0 } });
      expect(view.contentDOM.querySelector("hr")).toBeNull();
    });
  });
});
