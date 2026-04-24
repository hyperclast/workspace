/**
 * Unit tests for the table widget's inline cell renderer and URL sanitizer.
 *
 * Covers:
 *   - renderCellInline: each inline format, nesting, and malformed input
 *   - sanitizeCellLinkHref: safe/unsafe URL schemes
 *   - Adversarial cases: HTML/script injection attempts, dangerous URLs,
 *     pathological unclosed markers
 *
 * The renderer MUST:
 *   - Never emit raw HTML (all text goes through textContent)
 *   - Block javascript:/data:/vbscript:/etc. on link hrefs
 *   - Terminate on any input (no infinite loops on malformed markdown)
 */

import { describe, test, expect, beforeEach } from "vitest";
import { renderCellInline, sanitizeCellLinkHref } from "../../markdownTable.js";

// Happy-dom is configured globally in vitest.config.js; `document` is available.
let doc;

beforeEach(() => {
  doc = document;
});

/** Render a cell into a throwaway wrapper and return it for assertions. */
function render(content) {
  const wrapper = doc.createElement("div");
  wrapper.appendChild(renderCellInline(content, doc));
  return wrapper;
}

// ============================================================================
// sanitizeCellLinkHref
// ============================================================================

describe("sanitizeCellLinkHref", () => {
  test("allows http and https", () => {
    expect(sanitizeCellLinkHref("http://example.com")).toBe("http://example.com");
    expect(sanitizeCellLinkHref("https://example.com/path?q=1")).toBe(
      "https://example.com/path?q=1"
    );
  });

  test("allows mailto and tel", () => {
    expect(sanitizeCellLinkHref("mailto:a@b.com")).toBe("mailto:a@b.com");
    expect(sanitizeCellLinkHref("tel:+15555551234")).toBe("tel:+15555551234");
  });

  test("allows relative and anchor URLs (no scheme)", () => {
    expect(sanitizeCellLinkHref("/pages/abc/")).toBe("/pages/abc/");
    expect(sanitizeCellLinkHref("./foo")).toBe("./foo");
    expect(sanitizeCellLinkHref("foo/bar")).toBe("foo/bar");
    expect(sanitizeCellLinkHref("#section")).toBe("#section");
    expect(sanitizeCellLinkHref("?q=1")).toBe("?q=1");
  });

  test("blocks javascript: scheme in all casings", () => {
    expect(sanitizeCellLinkHref("javascript:alert(1)")).toBe("#");
    expect(sanitizeCellLinkHref("JAVASCRIPT:alert(1)")).toBe("#");
    expect(sanitizeCellLinkHref("JaVaScRiPt:alert(1)")).toBe("#");
    expect(sanitizeCellLinkHref("  javascript:alert(1)  ")).toBe("#");
  });

  test("blocks other dangerous schemes", () => {
    expect(sanitizeCellLinkHref("data:text/html,<script>alert(1)</script>")).toBe("#");
    expect(sanitizeCellLinkHref("vbscript:msgbox(1)")).toBe("#");
    expect(sanitizeCellLinkHref("file:///etc/passwd")).toBe("#");
    // ftp, ws, chrome-extension, etc. are also blocked by allowlist
    expect(sanitizeCellLinkHref("ftp://example.com")).toBe("#");
    expect(sanitizeCellLinkHref("chrome-extension://foo/bar")).toBe("#");
  });

  test("handles empty, whitespace, and null-ish input", () => {
    expect(sanitizeCellLinkHref("")).toBe("#");
    expect(sanitizeCellLinkHref("   ")).toBe("#");
    expect(sanitizeCellLinkHref(undefined)).toBe("#");
    expect(sanitizeCellLinkHref(null)).toBe("#");
  });

  test("handles URLs with leading whitespace (trimmed)", () => {
    expect(sanitizeCellLinkHref("  https://example.com  ")).toBe("https://example.com");
  });

  test("does not be fooled by scheme-like text that isn't a URL", () => {
    // "foo:bar" — `foo` is a scheme, not in allowlist → blocked.
    // This is the conservative/safe choice.
    expect(sanitizeCellLinkHref("foo:bar")).toBe("#");
  });

  test("handles URLs with characters that look like schemes but aren't", () => {
    // no colon → no scheme → passes through
    expect(sanitizeCellLinkHref("/javascript")).toBe("/javascript");
    expect(sanitizeCellLinkHref("./data:foo")).toBe("./data:foo");
  });
});

// ============================================================================
// renderCellInline — plain text
// ============================================================================

describe("renderCellInline — plain text", () => {
  test("renders empty string", () => {
    const el = render("");
    expect(el.textContent).toBe("");
    expect(el.childNodes.length).toBe(0);
  });

  test("renders plain text", () => {
    const el = render("hello world");
    expect(el.textContent).toBe("hello world");
    expect(el.querySelectorAll("*").length).toBe(0);
  });

  test("renders unicode and emoji", () => {
    const el = render("héllo 🎉 世界");
    expect(el.textContent).toBe("héllo 🎉 世界");
  });

  test("does not interpret HTML tags", () => {
    const el = render("<b>bold</b> <script>alert(1)</script>");
    // It's all text — no real tags created.
    expect(el.textContent).toBe("<b>bold</b> <script>alert(1)</script>");
    expect(el.querySelectorAll("b").length).toBe(0);
    expect(el.querySelectorAll("script").length).toBe(0);
  });

  test("preserves ampersands and quotes as text", () => {
    const el = render("a & b \"c\" 'd'");
    expect(el.textContent).toBe("a & b \"c\" 'd'");
  });
});

// ============================================================================
// renderCellInline — backtick code
// ============================================================================

describe("renderCellInline — code", () => {
  test("renders `code` as <code>", () => {
    const el = render("before `foo` after");
    const codes = el.querySelectorAll("code.cm-table-widget-code");
    expect(codes.length).toBe(1);
    expect(codes[0].textContent).toBe("foo");
    expect(el.textContent).toBe("before foo after");
  });

  test("renders multiple code chips in one cell", () => {
    const el = render("`a` and `b` and `c`");
    const codes = el.querySelectorAll("code");
    expect(codes.length).toBe(3);
    expect([...codes].map((c) => c.textContent)).toEqual(["a", "b", "c"]);
  });

  test("code never HTML-decodes its contents", () => {
    const el = render("`<script>alert(1)</script>`");
    const codes = el.querySelectorAll("code");
    expect(codes.length).toBe(1);
    expect(codes[0].textContent).toBe("<script>alert(1)</script>");
    expect(el.querySelectorAll("script").length).toBe(0);
  });

  test("unclosed backtick renders as literal text", () => {
    const el = render("unclosed `code here");
    expect(el.querySelectorAll("code").length).toBe(0);
    expect(el.textContent).toBe("unclosed `code here");
  });

  test("empty backticks render an empty <code>", () => {
    const el = render("a``b");
    const codes = el.querySelectorAll("code");
    expect(codes.length).toBe(1);
    expect(codes[0].textContent).toBe("");
    expect(el.textContent).toBe("ab");
  });
});

// ============================================================================
// renderCellInline — bold
// ============================================================================

describe("renderCellInline — bold", () => {
  test("renders **bold**", () => {
    const el = render("**strong**");
    const strongs = el.querySelectorAll("strong");
    expect(strongs.length).toBe(1);
    expect(strongs[0].textContent).toBe("strong");
  });

  test("unclosed ** falls back to literal", () => {
    const el = render("**unclosed");
    expect(el.querySelectorAll("strong").length).toBe(0);
    expect(el.textContent).toBe("**unclosed");
  });

  test("nested inline code inside bold", () => {
    const el = render("**has `code` inside**");
    const strong = el.querySelector("strong");
    expect(strong).not.toBeNull();
    const code = strong.querySelector("code");
    expect(code).not.toBeNull();
    expect(code.textContent).toBe("code");
  });
});

// ============================================================================
// renderCellInline — italic
// ============================================================================

describe("renderCellInline — italic", () => {
  test("renders *italic*", () => {
    const el = render("*emph*");
    const ems = el.querySelectorAll("em");
    expect(ems.length).toBe(1);
    expect(ems[0].textContent).toBe("emph");
  });

  test("does not confuse ** for single * in bold context", () => {
    // **bold** should be bold, not italic
    const el = render("**bold**");
    expect(el.querySelectorAll("strong").length).toBe(1);
    expect(el.querySelectorAll("em").length).toBe(0);
  });

  test("single * with no closer is literal", () => {
    const el = render("*unclosed text");
    expect(el.querySelectorAll("em").length).toBe(0);
    expect(el.textContent).toBe("*unclosed text");
  });

  test("*empty* pair does not produce an em", () => {
    // Parser requires j > i + 1 so ** at position 0 is treated as bold, not empty italic.
    const el = render("a**b");
    // This is "a" + unclosed ** + "b" — no strong, no em
    expect(el.querySelectorAll("strong").length).toBe(0);
    expect(el.querySelectorAll("em").length).toBe(0);
    expect(el.textContent).toBe("a**b");
  });

  test("nested code inside italic", () => {
    const el = render("*has `code` here*");
    const em = el.querySelector("em");
    expect(em).not.toBeNull();
    expect(em.querySelector("code").textContent).toBe("code");
  });
});

// ============================================================================
// renderCellInline — strikethrough
// ============================================================================

describe("renderCellInline — strike", () => {
  test("renders ~~strike~~", () => {
    const el = render("~~gone~~");
    const dels = el.querySelectorAll("del");
    expect(dels.length).toBe(1);
    expect(dels[0].textContent).toBe("gone");
  });

  test("unclosed ~~ is literal", () => {
    const el = render("~~unclosed");
    expect(el.querySelectorAll("del").length).toBe(0);
    expect(el.textContent).toBe("~~unclosed");
  });

  test("single ~ is literal", () => {
    const el = render("a ~ b");
    expect(el.querySelectorAll("del").length).toBe(0);
    expect(el.textContent).toBe("a ~ b");
  });
});

// ============================================================================
// renderCellInline — links
// ============================================================================

describe("renderCellInline — links", () => {
  test("renders [text](url)", () => {
    const el = render("[click me](https://example.com)");
    const a = el.querySelector("a");
    expect(a).not.toBeNull();
    expect(a.textContent).toBe("click me");
    expect(a.getAttribute("href")).toBe("https://example.com");
  });

  test("blocks javascript: URL — href becomes #", () => {
    const el = render("[click](javascript:alert(1))");
    const a = el.querySelector("a");
    expect(a).not.toBeNull();
    expect(a.getAttribute("href")).toBe("#");
    expect(a.textContent).toBe("click");
  });

  test("blocks data: URL", () => {
    const el = render("[click](data:text/html,<script>alert(1)</script>)");
    const a = el.querySelector("a");
    expect(a.getAttribute("href")).toBe("#");
  });

  test("link text is rendered through textContent", () => {
    const el = render("[<script>x</script>](https://example.com)");
    const a = el.querySelector("a");
    expect(a.textContent).toBe("<script>x</script>");
    expect(el.querySelectorAll("script").length).toBe(0);
  });

  test("link text can contain nested markdown", () => {
    const el = render("[**bold** text](https://example.com)");
    const a = el.querySelector("a");
    expect(a.querySelector("strong").textContent).toBe("bold");
    expect(a.textContent).toBe("bold text");
  });

  test("unclosed link syntax is literal", () => {
    const el = render("[click");
    expect(el.querySelectorAll("a").length).toBe(0);
    expect(el.textContent).toBe("[click");
  });

  test("link without parens is literal", () => {
    const el = render("[click]");
    expect(el.querySelectorAll("a").length).toBe(0);
    expect(el.textContent).toBe("[click]");
  });

  test("link with ] but no ( is literal", () => {
    const el = render("[click] text");
    expect(el.querySelectorAll("a").length).toBe(0);
    expect(el.textContent).toBe("[click] text");
  });

  test("link with unclosed paren is literal", () => {
    const el = render("[click](https://example.com");
    expect(el.querySelectorAll("a").length).toBe(0);
    expect(el.textContent).toBe("[click](https://example.com");
  });

  test("empty URL becomes #", () => {
    const el = render("[click]()");
    const a = el.querySelector("a");
    expect(a.getAttribute("href")).toBe("#");
  });

  test("relative URL is preserved", () => {
    const el = render("[page](/pages/abc/)");
    const a = el.querySelector("a");
    expect(a.getAttribute("href")).toBe("/pages/abc/");
  });
});

// ============================================================================
// renderCellInline — termination / robustness
// ============================================================================

describe("renderCellInline — robustness", () => {
  test("terminates on a large input of only asterisks", () => {
    // With 1000 `*` in a row the parser treats pairs as empty **bold** blocks.
    // The important property is that it returns (no infinite loop) and
    // produces no dangerous output — not what the visible text looks like.
    const input = "*".repeat(1000);
    const el = render(input);
    expect(el.querySelectorAll("script").length).toBe(0);
  });

  test("terminates on a large input of only backticks", () => {
    const input = "`".repeat(1000);
    const el = render(input);
    expect(el.querySelectorAll("script").length).toBe(0);
  });

  test("terminates on a large input of only brackets/parens", () => {
    const input = "[](".repeat(500);
    const el = render(input);
    expect(el.querySelectorAll("script").length).toBe(0);
    for (const a of el.querySelectorAll("a")) {
      expect((a.getAttribute("href") || "").startsWith("javascript:")).toBe(false);
    }
  });

  test("terminates on deeply nested bold+italic+code", () => {
    const input = "**a *b `c` d* e**";
    const el = render(input);
    expect(el.querySelector("strong")).not.toBeNull();
    expect(el.querySelector("em")).not.toBeNull();
    expect(el.querySelector("code")).not.toBeNull();
  });

  test("handles all formatting marks mixed in one cell", () => {
    const el = render("`a` **b** *c* ~~d~~ [e](https://e)");
    expect(el.querySelectorAll("code").length).toBe(1);
    expect(el.querySelectorAll("strong").length).toBe(1);
    expect(el.querySelectorAll("em").length).toBe(1);
    expect(el.querySelectorAll("del").length).toBe(1);
    expect(el.querySelectorAll("a").length).toBe(1);
  });

  test("never produces <script>, <iframe>, or <img> elements regardless of input", () => {
    const attacks = [
      "<script>alert(1)</script>",
      "<img src=x onerror=alert(1)>",
      "<iframe src=javascript:alert(1)></iframe>",
      "`<script>alert(1)</script>`",
      "**<script>alert(1)</script>**",
      "[<img src=x onerror=alert(1)>](https://example.com)",
      "[text](javascript:alert(1))",
      "[text](JAVASCRIPT:alert(1))",
      "[text](data:text/html,<script>alert(1)</script>)",
    ];
    for (const input of attacks) {
      const el = render(input);
      expect(el.querySelectorAll("script").length).toBe(0);
      expect(el.querySelectorAll("iframe").length).toBe(0);
      expect(el.querySelectorAll("img").length).toBe(0);
      // Every <a> must have a safe href.
      for (const a of el.querySelectorAll("a")) {
        const href = a.getAttribute("href") || "";
        expect(href.toLowerCase().startsWith("javascript:")).toBe(false);
        expect(href.toLowerCase().startsWith("data:")).toBe(false);
        expect(href.toLowerCase().startsWith("vbscript:")).toBe(false);
      }
    }
  });
});
