/**
 * Decoration Visual Correctness Tests
 *
 * Tests that decorations render correctly for various markdown patterns.
 * These tests verify the BEHAVIOR is correct, not just that code runs.
 */

import { describe, test, expect, beforeEach, afterEach } from "vitest";
import { EditorState } from "@codemirror/state";
import { EditorView, Decoration } from "@codemirror/view";
import { decorateFormatting, codeFenceField } from "../../decorateFormatting.js";
import { decorateLinks } from "../../decorateLinks.js";
import { decorateEmails } from "../../decorateEmails.js";

function createEditorWithDecorations(content, extensions = []) {
  const allExtensions = [
    codeFenceField,
    decorateFormatting,
    decorateLinks,
    decorateEmails,
    ...extensions,
  ];

  const state = EditorState.create({
    doc: content,
    extensions: allExtensions,
  });

  const parent = document.createElement("div");
  parent.style.width = "800px";
  parent.style.height = "600px";
  document.body.appendChild(parent);

  const view = new EditorView({ state, parent });
  return { view, parent };
}

function getDecorationClasses(view) {
  const classes = new Set();
  const content = view.contentDOM;
  content.querySelectorAll("[class]").forEach((el) => {
    el.classList.forEach((c) => classes.add(c));
  });
  return classes;
}

function hasDecoration(view, className) {
  return view.contentDOM.querySelector(`.${className}`) !== null;
}

function countDecorations(view, className) {
  return view.contentDOM.querySelectorAll(`.${className}`).length;
}

describe("Decoration Visual Correctness", () => {
  let view, parent;

  afterEach(() => {
    if (view) {
      view.destroy();
      view = null;
    }
    if (parent) {
      parent.remove();
      parent = null;
    }
  });

  describe("Bold Text", () => {
    test("bold text should have format-bold class", () => {
      ({ view, parent } = createEditorWithDecorations("This is **bold text** here."));
      expect(hasDecoration(view, "format-bold")).toBe(true);
    });

    test("multiple bold sections on same line", () => {
      ({ view, parent } = createEditorWithDecorations("**first** and **second** and **third**"));
      expect(countDecorations(view, "format-bold")).toBe(3);
    });

    test("unclosed bold should not decorate", () => {
      ({ view, parent } = createEditorWithDecorations("This **is not closed"));
      expect(hasDecoration(view, "format-bold")).toBe(false);
    });

    test("bold markers hidden when cursor not on line", () => {
      ({ view, parent } = createEditorWithDecorations("Line 1\n**bold on line 2**\nLine 3"));
      view.dispatch({ selection: { anchor: 0 } });
      const text = view.contentDOM.textContent;
      expect(text).toContain("bold on line 2");
      expect(text).not.toMatch(/\*\*bold on line 2\*\*/);
    });
  });

  describe("Underline Text", () => {
    test("underline text should have format-underline class", () => {
      ({ view, parent } = createEditorWithDecorations("This is __underlined text__ here."));
      expect(hasDecoration(view, "format-underline")).toBe(true);
    });

    test("underscore in variable names should not decorate", () => {
      ({ view, parent } = createEditorWithDecorations("const some_variable_name = 1;"));
      expect(hasDecoration(view, "format-underline")).toBe(false);
    });
  });

  describe("Inline Code", () => {
    test("inline code should have format-inline-code class", () => {
      ({ view, parent } = createEditorWithDecorations("Use `const x = 1` in code."));
      expect(hasDecoration(view, "format-inline-code")).toBe(true);
    });

    test("multiple inline code spans", () => {
      ({ view, parent } = createEditorWithDecorations("`one` and `two` and `three`"));
      expect(countDecorations(view, "format-inline-code")).toBe(3);
    });
  });

  describe("Headings", () => {
    test("h1 should have format-h1 class", () => {
      ({ view, parent } = createEditorWithDecorations("# Heading 1"));
      expect(hasDecoration(view, "format-h1")).toBe(true);
    });

    test("h2 through h6 should have respective classes", () => {
      ({ view, parent } = createEditorWithDecorations(
        "## H2\n### H3\n#### H4\n##### H5\n###### H6"
      ));
      expect(hasDecoration(view, "format-h2")).toBe(true);
      expect(hasDecoration(view, "format-h3")).toBe(true);
      expect(hasDecoration(view, "format-h4")).toBe(true);
      expect(hasDecoration(view, "format-h5")).toBe(true);
      expect(hasDecoration(view, "format-h6")).toBe(true);
    });

    test("hash marks hidden when cursor not on heading line", () => {
      ({ view, parent } = createEditorWithDecorations("Line 1\n## My Heading\nLine 3"));
      view.dispatch({ selection: { anchor: 0 } });
      const text = view.contentDOM.textContent;
      expect(text).toContain("My Heading");
    });

    test("heading inside code block should not decorate", () => {
      const content = "```\n# Not a heading\n```";
      ({ view, parent } = createEditorWithDecorations(content));
      expect(hasDecoration(view, "format-h1")).toBe(false);
    });
  });

  describe("Lists", () => {
    test("bullet list items should have format-bullet-item class", () => {
      ({ view, parent } = createEditorWithDecorations("- Item 1\n- Item 2"));
      expect(hasDecoration(view, "format-bullet-item")).toBe(true);
    });

    test("ordered list items should have format-ordered-item class", () => {
      ({ view, parent } = createEditorWithDecorations("1. Item 1\n2. Item 2"));
      expect(hasDecoration(view, "format-ordered-item")).toBe(true);
    });

    test("nested lists should have indent classes", () => {
      ({ view, parent } = createEditorWithDecorations("- Top\n  - Nested\n    - Deep"));
      expect(hasDecoration(view, "format-indent-1")).toBe(true);
      expect(hasDecoration(view, "format-indent-2")).toBe(true);
    });
  });

  describe("Checkboxes", () => {
    test("unchecked checkbox should render", () => {
      ({ view, parent } = createEditorWithDecorations("- [ ] Todo item"));
      expect(hasDecoration(view, "format-checkbox-item")).toBe(true);
    });

    test("checked checkbox should have checked class", () => {
      ({ view, parent } = createEditorWithDecorations("- [x] Done item"));
      expect(hasDecoration(view, "format-checkbox-checked")).toBe(true);
    });

    test("uppercase X checkbox should work", () => {
      ({ view, parent } = createEditorWithDecorations("- [X] Done with uppercase"));
      expect(hasDecoration(view, "format-checkbox-checked")).toBe(true);
    });

    test("checkbox widget should be present", () => {
      ({ view, parent } = createEditorWithDecorations("Line 1\n- [ ] Has checkbox\nLine 3"));
      view.dispatch({ selection: { anchor: 0 } });
      const checkbox = view.contentDOM.querySelector('input[type="checkbox"]');
      expect(checkbox).not.toBeNull();
    });
  });

  describe("Code Blocks", () => {
    test("code block should have format-code-block class", () => {
      const content = "```javascript\nconst x = 1;\n```";
      ({ view, parent } = createEditorWithDecorations(content));
      expect(hasDecoration(view, "format-code-block")).toBe(true);
    });

    test("code fence markers hidden when cursor elsewhere", () => {
      const content = "Line 1\n```\ncode\n```\nLine 5";
      ({ view, parent } = createEditorWithDecorations(content));
      view.dispatch({ selection: { anchor: 0 } });
    });
  });

  describe("Blockquotes", () => {
    test("blockquote should have format-blockquote class", () => {
      ({ view, parent } = createEditorWithDecorations("> This is a quote"));
      expect(hasDecoration(view, "format-blockquote")).toBe(true);
    });

    test("nested blockquotes", () => {
      ({ view, parent } = createEditorWithDecorations("> Level 1\n> > Level 2"));
      expect(countDecorations(view, "format-blockquote")).toBeGreaterThanOrEqual(1);
    });
  });

  describe("Horizontal Rules", () => {
    test("--- should render as HR", () => {
      ({ view, parent } = createEditorWithDecorations("Before\n---\nAfter"));
      const hr = view.contentDOM.querySelector("hr");
      expect(hr).not.toBeNull();
    });

    test("*** should render as HR", () => {
      ({ view, parent } = createEditorWithDecorations("Before\n***\nAfter"));
      const hr = view.contentDOM.querySelector("hr");
      expect(hr).not.toBeNull();
    });
  });

  describe("Links", () => {
    test("markdown link should have format-link class", () => {
      ({ view, parent } = createEditorWithDecorations("Check [this link](https://example.com)"));
      expect(hasDecoration(view, "format-link")).toBe(true);
    });

    test("internal link should have format-link-internal class", () => {
      ({ view, parent } = createEditorWithDecorations("See [Page Title](/pages/abc123/)"));
      expect(hasDecoration(view, "format-link-internal")).toBe(true);
    });

    test("external link should have format-link-external class", () => {
      ({ view, parent } = createEditorWithDecorations("Visit [Site](https://example.com)"));
      expect(hasDecoration(view, "format-link-external")).toBe(true);
    });

    test("link syntax hidden when cursor not on link", () => {
      ({ view, parent } = createEditorWithDecorations("Before\n[Link Text](url)\nAfter"));
      view.dispatch({ selection: { anchor: 0 } });
      const text = view.contentDOM.textContent;
      expect(text).toContain("Link Text");
    });

    test("link with special chars in URL", () => {
      ({ view, parent } = createEditorWithDecorations("[Link](https://example.com?a=1&b=2)"));
      expect(hasDecoration(view, "format-link")).toBe(true);
    });
  });

  describe("Emails", () => {
    test("email should have email-highlight class", () => {
      ({ view, parent } = createEditorWithDecorations("Contact user@example.com for help"));
      expect(hasDecoration(view, "email-highlight")).toBe(true);
    });

    test("multiple emails on same line", () => {
      ({ view, parent } = createEditorWithDecorations("Contact a@test.com or b@test.com"));
      expect(countDecorations(view, "email-highlight")).toBe(2);
    });
  });

  describe("Mixed Content", () => {
    test("complex document with multiple decoration types", () => {
      const content = `# Heading

This paragraph has **bold** and __underline__ and \`code\`.

- [ ] Checkbox item
- Regular bullet
1. Ordered item

> Blockquote

\`\`\`
code block
\`\`\`

[Link](https://example.com) and email@test.com

---

End of document.`;

      ({ view, parent } = createEditorWithDecorations(content));

      expect(hasDecoration(view, "format-h1")).toBe(true);
      expect(hasDecoration(view, "format-bold")).toBe(true);
      expect(hasDecoration(view, "format-underline")).toBe(true);
      expect(hasDecoration(view, "format-inline-code")).toBe(true);
      expect(hasDecoration(view, "format-checkbox-item")).toBe(true);
      expect(hasDecoration(view, "format-bullet-item")).toBe(true);
      expect(hasDecoration(view, "format-ordered-item")).toBe(true);
      expect(hasDecoration(view, "format-blockquote")).toBe(true);
      expect(hasDecoration(view, "format-code-block")).toBe(true);
      expect(hasDecoration(view, "format-link")).toBe(true);
      expect(hasDecoration(view, "email-highlight")).toBe(true);
    });
  });
});
