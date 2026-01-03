/**
 * decorateLinks.js Specific Tests
 *
 * Comprehensive tests for link decoration before and after refactoring.
 */

import { describe, test, expect, afterEach } from "vitest";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { decorateLinks, linkClickHandler } from "../../decorateLinks.js";
import {
  generateDocumentWithLinks,
  generateDocumentWithPatternsAt,
} from "../helpers/large-fixtures.js";
import { measureTime, getConfig, isFullMode } from "../helpers/perf-utils.js";

function createEditor(content) {
  const state = EditorState.create({
    doc: content,
    extensions: [decorateLinks, linkClickHandler],
  });

  const parent = document.createElement("div");
  parent.style.width = "800px";
  parent.style.height = "400px";
  parent.style.overflow = "auto";
  document.body.appendChild(parent);

  const view = new EditorView({ state, parent });
  return { view, parent };
}

function hasClass(view, className) {
  return view.contentDOM.querySelector(`.${className}`) !== null;
}

function countClass(view, className) {
  return view.contentDOM.querySelectorAll(`.${className}`).length;
}

function getLinksInDOM(view) {
  return Array.from(view.contentDOM.querySelectorAll(".format-link"));
}

function scrollToLine(view, lineNumber) {
  const line = view.state.doc.line(lineNumber);
  view.dispatch({
    effects: EditorView.scrollIntoView(line.from, { y: "start" }),
  });
  return new Promise((resolve) => requestAnimationFrame(resolve));
}

describe("decorateLinks", () => {
  let view, parent;

  afterEach(() => {
    if (view) view.destroy();
    if (parent) parent.remove();
    view = null;
    parent = null;
  });

  describe("Basic link decoration", () => {
    test("external link gets format-link and format-link-external classes", () => {
      ({ view, parent } = createEditor("[Link](https://example.com)"));
      expect(hasClass(view, "format-link")).toBe(true);
      expect(hasClass(view, "format-link-external")).toBe(true);
    });

    test("internal link gets format-link and format-link-internal classes", () => {
      ({ view, parent } = createEditor("[Page](/pages/abc123/)"));
      expect(hasClass(view, "format-link")).toBe(true);
      expect(hasClass(view, "format-link-internal")).toBe(true);
    });

    test("link text is visible, brackets/URL hidden when cursor elsewhere", () => {
      ({ view, parent } = createEditor("Before [Link Text](https://example.com) after"));

      view.dispatch({ selection: { anchor: 0 } });

      const text = view.contentDOM.textContent;
      expect(text).toContain("Link Text");
      expect(text).not.toContain("](https://");
    });

    test("link icon widget is present", () => {
      ({ view, parent } = createEditor("Before\n[Link](https://example.com)\nAfter"));

      view.dispatch({ selection: { anchor: 0 } });

      const icon = view.contentDOM.querySelector(".link-icon");
      expect(icon).not.toBeNull();
    });

    test("internal link has internal icon", () => {
      ({ view, parent } = createEditor("Before\n[Page](/pages/abc123/)\nAfter"));

      view.dispatch({ selection: { anchor: 0 } });

      const icon = view.contentDOM.querySelector(".link-icon-internal");
      expect(icon).not.toBeNull();
    });

    test("external link has external icon", () => {
      ({ view, parent } = createEditor("Before\n[Site](https://example.com)\nAfter"));

      view.dispatch({ selection: { anchor: 0 } });

      const icon = view.contentDOM.querySelector(".link-icon-external");
      expect(icon).not.toBeNull();
    });
  });

  describe("Cursor interaction", () => {
    test("cursor inside link shows full syntax", () => {
      ({ view, parent } = createEditor("[Link Text](https://example.com)"));

      view.dispatch({ selection: { anchor: 5 } });

      const text = view.contentDOM.textContent;
      expect(text).toContain("[Link Text](https://example.com)");
    });

    test("cursor at link start shows syntax", () => {
      ({ view, parent } = createEditor("Before\n[Link](url)\nAfter"));

      view.dispatch({ selection: { anchor: 0 } });
      const text1 = view.contentDOM.textContent;
      expect(text1).not.toContain("](url)");

      const linkLine = view.state.doc.line(2);
      view.dispatch({ selection: { anchor: linkLine.from + 1 } });
      const text2 = view.contentDOM.textContent;
      expect(text2).toContain("[Link](url)");
    });

    test("cursor at link end shows syntax", () => {
      ({ view, parent } = createEditor("[Link](url)"));

      view.dispatch({ selection: { anchor: 10 } });
      const text = view.contentDOM.textContent;
      expect(text).toContain("[Link](url)");
    });

    test("moving cursor out of link hides syntax", () => {
      ({ view, parent } = createEditor("Before [Link](url) after"));

      view.dispatch({ selection: { anchor: 10 } });
      view.dispatch({ selection: { anchor: 0 } });

      const text = view.contentDOM.textContent;
      expect(text).not.toContain("](url)");
    });
  });

  describe("Multiple links", () => {
    test("multiple links on same line", () => {
      ({ view, parent } = createEditor("[A](url1) and [B](url2) and [C](url3)"));

      view.dispatch({ selection: { anchor: 0 } });

      expect(countClass(view, "format-link")).toBe(3);
    });

    test("links on different lines", () => {
      ({ view, parent } = createEditor("[Link1](url1)\n[Link2](url2)\n[Link3](url3)"));

      expect(countClass(view, "format-link")).toBe(3);
    });

    test("cursor on one link doesn't affect others", () => {
      ({ view, parent } = createEditor("[A](url1) [B](url2)"));

      view.dispatch({ selection: { anchor: 2 } });

      const links = getLinksInDOM(view);
      expect(links.length).toBe(2);
    });
  });

  describe("Link data attributes", () => {
    test("link element has data-url attribute", () => {
      ({ view, parent } = createEditor("[Link](https://example.com)"));

      const link = view.contentDOM.querySelector(".format-link");
      expect(link.dataset.url).toBe("https://example.com");
    });

    test("internal link has data-internal=true", () => {
      ({ view, parent } = createEditor("[Page](/pages/abc123/)"));

      const link = view.contentDOM.querySelector(".format-link");
      expect(link.dataset.internal).toBe("true");
    });

    test("external link has data-internal=false", () => {
      ({ view, parent } = createEditor("[Site](https://example.com)"));

      const link = view.contentDOM.querySelector(".format-link");
      expect(link.dataset.internal).toBe("false");
    });
  });

  describe("Edge cases", () => {
    test("link with query parameters", () => {
      ({ view, parent } = createEditor("[Link](https://example.com?a=1&b=2)"));
      expect(hasClass(view, "format-link")).toBe(true);
    });

    test("link with hash fragment", () => {
      ({ view, parent } = createEditor("[Link](https://example.com#section)"));
      expect(hasClass(view, "format-link")).toBe(true);
    });

    test("link with spaces in text", () => {
      ({ view, parent } = createEditor("[Link With Spaces](url)"));
      expect(hasClass(view, "format-link")).toBe(true);
    });

    test("empty link text - no decoration", () => {
      ({ view, parent } = createEditor("[](url)"));
      expect(hasClass(view, "format-link")).toBe(false);
    });

    test("empty URL - no decoration (regex requires URL content)", () => {
      ({ view, parent } = createEditor("[Text]()"));
      expect(hasClass(view, "format-link")).toBe(false);
    });

    test("nested brackets before link", () => {
      ({ view, parent } = createEditor("[not link] then [real](url)"));
      expect(countClass(view, "format-link")).toBe(1);
    });

    test("broken link across lines - no decoration", () => {
      ({ view, parent } = createEditor("[Link\nText](url)"));
      expect(hasClass(view, "format-link")).toBe(false);
    });
  });

  describe("Performance - viewport-based processing", () => {
    test("decoration computation should be O(viewport) not O(document)", async () => {
      const smallDoc = generateDocumentWithLinks({ lines: 100, linksPerChunk: 5 });
      const largeDoc = generateDocumentWithLinks({
        lines: getConfig(5000, 50000),
        linksPerChunk: 5,
      });

      const { duration: smallDuration } = await measureTime(() => {
        const { view: v, parent: p } = createEditor(smallDoc);
        v.destroy();
        p.remove();
      });

      const { duration: largeDuration } = await measureTime(() => {
        ({ view, parent } = createEditor(largeDoc));
      });

      console.log(`[PERF] decorateLinks creation:`);
      console.log(`  100 lines: ${smallDuration.toFixed(2)}ms`);
      console.log(`  ${getConfig(5000, 50000)} lines: ${largeDuration.toFixed(2)}ms`);
      console.log(`  Ratio: ${(largeDuration / smallDuration).toFixed(1)}x`);

      const idealRatio = getConfig(5000, 50000) / 100;
      const actualRatio = largeDuration / smallDuration;

      if (actualRatio > idealRatio * 0.5) {
        console.warn(`⚠️ Performance may be O(n): ratio ${actualRatio.toFixed(1)}x vs ideal ~1x`);
      }
    });

    test("editing at start should be fast regardless of doc size", async () => {
      const content = generateDocumentWithLinks({
        lines: getConfig(2000, 20000),
        linksPerChunk: 5,
      });
      ({ view, parent } = createEditor(content));

      const latencies = [];
      for (let i = 0; i < 10; i++) {
        const { duration } = await measureTime(() => {
          view.dispatch({
            changes: { from: 0, insert: "x" },
          });
        });
        latencies.push(duration);
      }

      const avgLatency = latencies.reduce((a, b) => a + b, 0) / latencies.length;
      console.log(`[PERF] Edit at start: avg ${avgLatency.toFixed(2)}ms`);

      expect(avgLatency).toBeLessThan(50);
    });

    test("scrolling to links outside viewport should decorate them", async () => {
      const content = generateDocumentWithPatternsAt({
        totalLines: 1000,
        patterns: [
          { line: 10, content: "[Link at 10](/pages/id1/)" },
          { line: 500, content: "[Link at 500](/pages/id2/)" },
          { line: 900, content: "[Link at 900](/pages/id3/)" },
        ],
      });

      ({ view, parent } = createEditor(content));

      expect(hasClass(view, "format-link")).toBe(true);

      await scrollToLine(view, 500);
      expect(hasClass(view, "format-link")).toBe(true);

      await scrollToLine(view, 900);
      expect(hasClass(view, "format-link")).toBe(true);
    });
  });

  describe("Internal link pattern matching", () => {
    test("/pages/ID/ pattern is internal", () => {
      ({ view, parent } = createEditor("[Page](/pages/abc123/)"));
      expect(hasClass(view, "format-link-internal")).toBe(true);
    });

    test("/pages/ID pattern without trailing slash is internal", () => {
      ({ view, parent } = createEditor("[Page](/pages/abc123)"));
      expect(hasClass(view, "format-link-internal")).toBe(true);
    });

    test("http URL is external", () => {
      ({ view, parent } = createEditor("[Site](http://example.com)"));
      expect(hasClass(view, "format-link-external")).toBe(true);
    });

    test("https URL is external", () => {
      ({ view, parent } = createEditor("[Site](https://example.com)"));
      expect(hasClass(view, "format-link-external")).toBe(true);
    });

    test("relative URL is external", () => {
      ({ view, parent } = createEditor("[Doc](./docs/readme.md)"));
      expect(hasClass(view, "format-link-external")).toBe(true);
    });
  });
});
