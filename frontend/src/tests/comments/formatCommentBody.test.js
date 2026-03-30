import { describe, test, expect } from "vitest";
import { formatCommentBody } from "../../lib/utils/formatComment.js";

const link = (url, text) =>
  `<a class="comment-link" target="_blank" rel="noopener noreferrer" href="${url}">${
    text ?? url
  }</a>`;

// ---------------------------------------------------------------------------
// Bare URL detection
// ---------------------------------------------------------------------------
describe("bare URL detection", () => {
  test("plain URL mid-sentence", () => {
    expect(formatCommentBody("check https://example.com for info")).toBe(
      `check ${link("https://example.com")} for info`
    );
  });

  test("URL at start of text", () => {
    expect(formatCommentBody("https://example.com is cool")).toBe(
      `${link("https://example.com")} is cool`
    );
  });

  test("URL at end of text", () => {
    expect(formatCommentBody("see https://example.com")).toBe(`see ${link("https://example.com")}`);
  });

  test("URL is the entire text", () => {
    expect(formatCommentBody("https://example.com")).toBe(link("https://example.com"));
  });

  test("multiple URLs", () => {
    const input = "see https://a.com and https://b.com ok";
    expect(formatCommentBody(input)).toBe(
      `see ${link("https://a.com")} and ${link("https://b.com")} ok`
    );
  });

  test("URL with path, query params, and fragment", () => {
    const input = "https://example.com/path?q=1&r=2#frag";
    // & is HTML-escaped to &amp; by escapeHtml
    const escaped = "https://example.com/path?q=1&amp;r=2#frag";
    expect(formatCommentBody(input)).toBe(link(escaped));
  });

  test("http (not https) is detected", () => {
    expect(formatCommentBody("go to http://example.com now")).toBe(
      `go to ${link("http://example.com")} now`
    );
  });

  test("URL on second line", () => {
    expect(formatCommentBody("line one\nhttps://example.com")).toBe(
      `line one<br>${link("https://example.com")}`
    );
  });
});

// ---------------------------------------------------------------------------
// Trailing punctuation
// ---------------------------------------------------------------------------
describe("trailing punctuation is stripped from URLs", () => {
  test.each([
    ["period", "see https://example.com.", `see ${link("https://example.com")}.`],
    ["comma", "see https://example.com, ok", `see ${link("https://example.com")}, ok`],
    ["semicolon", "see https://example.com; ok", `see ${link("https://example.com")}; ok`],
    ["colon", "see https://example.com: ok", `see ${link("https://example.com")}: ok`],
    ["exclamation", "see https://example.com!", `see ${link("https://example.com")}!`],
    ["question mark", "see https://example.com?", `see ${link("https://example.com")}?`],
    ["double quote", `see https://example.com"`, `see ${link("https://example.com")}"`],
  ])("%s", (_label, input, expected) => {
    expect(formatCommentBody(input)).toBe(expected);
  });

  test("trailing period after path is stripped", () => {
    expect(formatCommentBody("see https://example.com/page.")).toBe(
      `see ${link("https://example.com/page")}.`
    );
  });
});

// ---------------------------------------------------------------------------
// Parentheses handling (Wikipedia URLs)
// ---------------------------------------------------------------------------
describe("parentheses handling", () => {
  test("Wikipedia URL with balanced parens is kept intact", () => {
    const url = "https://en.wikipedia.org/wiki/Rust_(programming_language)";
    expect(formatCommentBody(`see ${url}`)).toBe(`see ${link(url)}`);
  });

  test("URL wrapped in user parens — outer paren not included", () => {
    expect(formatCommentBody("(https://example.com)")).toBe(`(${link("https://example.com")})`);
  });

  test("Wikipedia URL wrapped in user parens", () => {
    const url = "https://en.wikipedia.org/wiki/Rust_(programming_language)";
    expect(formatCommentBody(`(${url})`)).toBe(`(${link(url)})`);
  });

  test("URL with multiple balanced paren groups", () => {
    const url = "https://example.com/a_(b)/c_(d)";
    expect(formatCommentBody(url)).toBe(link(url));
  });

  test("URL with unbalanced extra closing parens", () => {
    // Two closing parens but only one opening — strip the trailing one
    expect(formatCommentBody("https://example.com/a_(b))")).toBe(
      `${link("https://example.com/a_(b)")})`
    );
  });
});

// ---------------------------------------------------------------------------
// Markdown links
// ---------------------------------------------------------------------------
describe("markdown links", () => {
  test("basic markdown link", () => {
    expect(formatCommentBody("[click](https://example.com)")).toBe(
      link("https://example.com", "click")
    );
  });

  test("markdown link with Wikipedia URL (parens in URL)", () => {
    const url = "https://en.wikipedia.org/wiki/Rust_(programming_language)";
    expect(formatCommentBody(`[Rust](${url})`)).toBe(link(url, "Rust"));
  });

  test("markdown link URL is not double-linked as bare URL", () => {
    const result = formatCommentBody("[site](https://example.com)");
    // Should contain exactly one <a> tag
    const matches = result.match(/<a /g);
    expect(matches).toHaveLength(1);
  });

  test("markdown link followed by bare URL", () => {
    const input = "[a](https://a.com) and https://b.com";
    expect(formatCommentBody(input)).toBe(
      `${link("https://a.com", "a")} and ${link("https://b.com")}`
    );
  });
});

// ---------------------------------------------------------------------------
// Inline code — URLs inside backticks should NOT be linked
// ---------------------------------------------------------------------------
describe("inline code", () => {
  test("URL inside backticks is not linked", () => {
    const result = formatCommentBody("`https://example.com`");
    expect(result).toBe("<code>https://example.com</code>");
    expect(result).not.toContain("<a ");
  });

  test("backtick code alongside a bare URL", () => {
    const result = formatCommentBody("`code` and https://example.com");
    expect(result).toBe(`<code>code</code> and ${link("https://example.com")}`);
  });

  test("URL inside backticks with surrounding text", () => {
    const result = formatCommentBody("run `curl https://api.example.com/v1` to test");
    expect(result).toContain("<code>");
    // The URL inside code should not become a link
    expect(result).not.toContain('href="https://api.example.com');
  });
});

// ---------------------------------------------------------------------------
// Bold
// ---------------------------------------------------------------------------
describe("bold", () => {
  test("bold text renders strong tag", () => {
    expect(formatCommentBody("this is **bold** text")).toBe("this is <strong>bold</strong> text");
  });
});

// ---------------------------------------------------------------------------
// Newlines
// ---------------------------------------------------------------------------
describe("newlines", () => {
  test("newlines become <br>", () => {
    expect(formatCommentBody("line1\nline2\nline3")).toBe("line1<br>line2<br>line3");
  });
});

// ---------------------------------------------------------------------------
// HTML escaping / XSS prevention
// ---------------------------------------------------------------------------
describe("XSS prevention", () => {
  test("HTML tags are escaped", () => {
    const result = formatCommentBody("<script>alert('xss')</script>");
    expect(result).not.toContain("<script>");
    expect(result).toContain("&lt;script&gt;");
  });

  test("HTML in markdown link text is escaped", () => {
    const result = formatCommentBody("[<b>bad</b>](https://example.com)");
    expect(result).not.toContain("<b>bad</b>");
    expect(result).toContain("&lt;b&gt;");
  });
});

// ---------------------------------------------------------------------------
// Combined formatting
// ---------------------------------------------------------------------------
describe("combined formatting", () => {
  test("bold + bare URL + newline", () => {
    const input = "**Note:** see https://example.com\nfor details";
    const result = formatCommentBody(input);
    expect(result).toContain("<strong>Note:</strong>");
    expect(result).toContain(link("https://example.com"));
    expect(result).toContain("<br>");
  });

  test("inline code + markdown link", () => {
    const input = "use `fetch` then see [docs](https://docs.example.com)";
    const result = formatCommentBody(input);
    expect(result).toContain("<code>fetch</code>");
    expect(result).toContain(link("https://docs.example.com", "docs"));
  });
});
