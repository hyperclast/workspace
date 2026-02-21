/**
 * decorateImagePreviews.js Tests
 *
 * Tests for image preview regex patterns and decoration behavior.
 * These tests verify:
 * 1. IMAGE_SYNTAX_REGEX - matches markdown image syntax ![alt](url)
 * 2. INTERNAL_FILE_PATTERN - matches internal file URLs /files/{project}/{file}/{token}/
 */

import { describe, test, expect, afterEach } from "vitest";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { decorateImagePreviews, imageClickHandler } from "../../decorateImagePreviews.js";

// Re-create the regex patterns from decorateImagePreviews.js for direct testing
// These should match the patterns defined in the source file
const IMAGE_SYNTAX_REGEX = /!\[([^\]]*)\]\(([^)]+)\)/g;
const INTERNAL_FILE_PATTERN =
  /^(https?:\/\/[^/]+)?\/files\/[a-zA-Z0-9]+\/[a-zA-Z0-9-]+\/[a-zA-Z0-9_-]+\/?$/;

function createEditor(content) {
  const state = EditorState.create({
    doc: content,
    extensions: [decorateImagePreviews, imageClickHandler],
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

describe("decorateImagePreviews", () => {
  let view, parent;

  afterEach(() => {
    if (view) view.destroy();
    if (parent) parent.remove();
    view = null;
    parent = null;
  });

  describe("IMAGE_SYNTAX_REGEX - markdown image syntax matching", () => {
    function matchImage(text) {
      const regex = new RegExp(IMAGE_SYNTAX_REGEX.source, "g");
      const match = regex.exec(text);
      return match ? { full: match[0], alt: match[1], url: match[2] } : null;
    }

    function matchAllImages(text) {
      const regex = new RegExp(IMAGE_SYNTAX_REGEX.source, "g");
      const matches = [];
      let match;
      while ((match = regex.exec(text)) !== null) {
        matches.push({ full: match[0], alt: match[1], url: match[2] });
      }
      return matches;
    }

    test("matches basic image syntax", () => {
      const result = matchImage("![alt text](https://example.com/image.png)");
      expect(result).not.toBeNull();
      expect(result.alt).toBe("alt text");
      expect(result.url).toBe("https://example.com/image.png");
    });

    test("matches image with empty alt text", () => {
      const result = matchImage("![](https://example.com/image.png)");
      expect(result).not.toBeNull();
      expect(result.alt).toBe("");
      expect(result.url).toBe("https://example.com/image.png");
    });

    test("matches image with relative URL", () => {
      const result = matchImage("![photo](/files/abc123/def456/token123/)");
      expect(result).not.toBeNull();
      expect(result.alt).toBe("photo");
      expect(result.url).toBe("/files/abc123/def456/token123/");
    });

    test("matches image with special characters in alt text", () => {
      const result = matchImage("![Photo: sunset & sunrise!](https://example.com/img.jpg)");
      expect(result).not.toBeNull();
      expect(result.alt).toBe("Photo: sunset & sunrise!");
    });

    test("does not match regular link (no exclamation mark)", () => {
      const result = matchImage("[Link text](https://example.com)");
      expect(result).toBeNull();
    });

    test("does not match malformed syntax - missing closing bracket", () => {
      const result = matchImage("![alt text(https://example.com/image.png)");
      expect(result).toBeNull();
    });

    test("does not match malformed syntax - missing closing paren", () => {
      const result = matchImage("![alt text](https://example.com/image.png");
      expect(result).toBeNull();
    });

    test("matches multiple images in same line", () => {
      const text = "![one](url1) some text ![two](url2)";
      const matches = matchAllImages(text);
      expect(matches).toHaveLength(2);
      expect(matches[0].alt).toBe("one");
      expect(matches[1].alt).toBe("two");
    });

    test("matches image at start of line", () => {
      const result = matchImage("![image](url) trailing text");
      expect(result).not.toBeNull();
      expect(result.alt).toBe("image");
    });

    test("matches image at end of line", () => {
      const result = matchImage("leading text ![image](url)");
      expect(result).not.toBeNull();
      expect(result.alt).toBe("image");
    });

    test("does not match text inside code backticks conceptually", () => {
      // Note: The regex itself doesn't handle code blocks - that's the decorator's job
      // This test documents the regex behavior
      const result = matchImage("`![code](url)`");
      expect(result).not.toBeNull(); // Regex matches, but decorator should skip
    });
  });

  describe("INTERNAL_FILE_PATTERN - internal file URL matching", () => {
    test("matches relative internal file URL", () => {
      expect(INTERNAL_FILE_PATTERN.test("/files/abc123/def456/token789/")).toBe(true);
    });

    test("matches relative URL without trailing slash", () => {
      expect(INTERNAL_FILE_PATTERN.test("/files/abc123/def456/token789")).toBe(true);
    });

    test("matches absolute URL with http", () => {
      expect(
        INTERNAL_FILE_PATTERN.test("http://localhost:8000/files/abc123/def456/token789/")
      ).toBe(true);
    });

    test("matches absolute URL with https", () => {
      expect(
        INTERNAL_FILE_PATTERN.test("https://app.example.com/files/abc123/def456/token789/")
      ).toBe(true);
    });

    test("matches file ID with hyphens (UUID format)", () => {
      // This was the bug fixed in commit #223
      expect(
        INTERNAL_FILE_PATTERN.test("/files/abc123/9ddb7185-cb5c-46c5-89db-bc59f602b0e2/token/")
      ).toBe(true);
    });

    test("matches access token with underscores (base64url format)", () => {
      // secrets.token_urlsafe() produces base64url characters
      expect(INTERNAL_FILE_PATTERN.test("/files/abc123/fileid/abc_def-ghi123/")).toBe(true);
    });

    test("matches access token with hyphens", () => {
      expect(INTERNAL_FILE_PATTERN.test("/files/abc123/fileid/abc-def-ghi/")).toBe(true);
    });

    test("does not match external URLs", () => {
      expect(INTERNAL_FILE_PATTERN.test("https://example.com/image.png")).toBe(false);
    });

    test("does not match other internal paths", () => {
      expect(INTERNAL_FILE_PATTERN.test("/pages/abc123/")).toBe(false);
      expect(INTERNAL_FILE_PATTERN.test("/api/files/abc123/")).toBe(false);
    });

    test("does not match with missing segments", () => {
      expect(INTERNAL_FILE_PATTERN.test("/files/abc123/")).toBe(false);
      expect(INTERNAL_FILE_PATTERN.test("/files/abc123/def456/")).toBe(false);
    });

    test("does not match with extra segments", () => {
      expect(INTERNAL_FILE_PATTERN.test("/files/abc123/def456/token/extra/")).toBe(false);
    });

    test("does not match project ID with hyphens (project IDs are alphanumeric only)", () => {
      // Project IDs from generate_random_string() are alphanumeric only
      expect(INTERNAL_FILE_PATTERN.test("/files/abc-123/def456/token/")).toBe(false);
    });

    test("does not match with special characters in segments", () => {
      expect(INTERNAL_FILE_PATTERN.test("/files/abc@123/def456/token/")).toBe(false);
      expect(INTERNAL_FILE_PATTERN.test("/files/abc123/def$456/token/")).toBe(false);
    });

    test("does not match ftp protocol", () => {
      expect(INTERNAL_FILE_PATTERN.test("ftp://example.com/files/abc123/def456/token/")).toBe(
        false
      );
    });
  });

  describe("Editor decoration behavior", () => {
    test("internal file image gets image-preview-container class", () => {
      // Add text before image so cursor at 0 is outside the image syntax
      ({ view, parent } = createEditor("x ![alt](/files/abc123/def456/token789/)"));
      // Move cursor to start, before the image
      view.dispatch({ selection: { anchor: 0 } });
      expect(hasClass(view, "image-preview-container")).toBe(true);
    });

    test("external image URL does not get preview decoration", () => {
      ({ view, parent } = createEditor("![alt](https://example.com/image.png)"));
      view.dispatch({ selection: { anchor: 0 } });
      expect(hasClass(view, "image-preview-container")).toBe(false);
    });

    test("shows raw syntax when cursor is inside image", () => {
      ({ view, parent } = createEditor("![alt](/files/abc123/def456/token789/)"));
      // Position cursor inside the image syntax
      view.dispatch({ selection: { anchor: 5 } }); // Inside "alt"
      expect(hasClass(view, "image-syntax-raw")).toBe(true);
      expect(hasClass(view, "image-preview-container")).toBe(false);
    });

    test("shows preview when cursor is outside image", () => {
      ({ view, parent } = createEditor("text ![alt](/files/abc123/def456/token789/) more"));
      // Position cursor in "text" before image
      view.dispatch({ selection: { anchor: 2 } });
      expect(hasClass(view, "image-preview-container")).toBe(true);
      expect(hasClass(view, "image-syntax-raw")).toBe(false);
    });

    test("decorates multiple images on same line", () => {
      // Add text before so cursor at 0 is outside both images
      const content = "x ![a](/files/p1/f1/t1/) ![b](/files/p2/f2/t2/)";
      ({ view, parent } = createEditor(content));
      view.dispatch({ selection: { anchor: 0 } });
      expect(countClass(view, "image-preview-container")).toBe(2);
    });

    test("does not decorate regular links that look like images", () => {
      // Regular link without ! prefix
      ({ view, parent } = createEditor("[Link](/files/abc123/def456/token789/)"));
      view.dispatch({ selection: { anchor: 0 } });
      expect(hasClass(view, "image-preview-container")).toBe(false);
    });

    test("handles image with UUID file ID (commit #223 bugfix)", () => {
      // Add text before so cursor at 0 is outside the image syntax
      const content = "x ![photo](/files/abc123/9ddb7185-cb5c-46c5-89db-bc59f602b0e2/token123/)";
      ({ view, parent } = createEditor(content));
      view.dispatch({ selection: { anchor: 0 } });
      expect(hasClass(view, "image-preview-container")).toBe(true);
    });
  });

  describe("XSS prevention in image error handler", () => {
    /**
     * Helper: create an editor with a malicious alt text in an internal file URL,
     * find the rendered image widget, and trigger its onerror handler to simulate
     * a failed image load. Returns the container element after error.
     */
    function triggerImageError(altText) {
      const content = `x ![${altText}](/files/abc123/def456/token789/)`;
      ({ view, parent } = createEditor(content));
      view.dispatch({ selection: { anchor: 0 } });

      const container = view.contentDOM.querySelector(".image-preview-container");
      expect(container).not.toBeNull();

      const img = container.querySelector("img");
      expect(img).not.toBeNull();

      // Trigger the onerror handler to simulate failed image load
      img.onerror();

      return container;
    }

    test("script tag in alt text is not rendered as HTML in error message", () => {
      const container = triggerImageError("<script>alert('xss')</script>");

      // The script tag must not appear as an actual element
      expect(container.querySelector("script")).toBeNull();
      // The error message should display the literal text
      const errorDiv = container.querySelector(".image-preview-error");
      expect(errorDiv).not.toBeNull();
      expect(errorDiv.textContent).toContain("<script>");
    });

    test("img onerror payload in alt text is not rendered as HTML", () => {
      const container = triggerImageError("<img src=x onerror=\"alert('xss')\">");

      // Should not create an actual img element from the alt text
      // (the only img should be gone after onerror cleared the container)
      expect(container.querySelector("img")).toBeNull();
      const errorDiv = container.querySelector(".image-preview-error");
      expect(errorDiv).not.toBeNull();
      expect(errorDiv.textContent).toContain("<img");
    });

    test("event handler attribute in alt text is not rendered as HTML", () => {
      const container = triggerImageError('<div onmouseover="alert(1)">hover</div>');

      const errorDiv = container.querySelector(".image-preview-error");
      expect(errorDiv).not.toBeNull();
      // Should not have any element with an event handler
      const allElements = errorDiv.querySelectorAll("*");
      allElements.forEach((el) => {
        expect(el.getAttribute("onmouseover")).toBeNull();
      });
    });

    test("safe alt text is displayed correctly in error message", () => {
      const container = triggerImageError("My Photo");

      const errorDiv = container.querySelector(".image-preview-error");
      expect(errorDiv).not.toBeNull();
      expect(errorDiv.textContent).toContain("Failed to load:");
      expect(errorDiv.textContent).toContain("My Photo");
    });

    test("empty alt text shows 'image' fallback in error message", () => {
      const content = "x ![](/files/abc123/def456/token789/)";
      ({ view, parent } = createEditor(content));
      view.dispatch({ selection: { anchor: 0 } });

      const container = view.contentDOM.querySelector(".image-preview-container");
      const img = container.querySelector("img");
      img.onerror();

      const errorDiv = container.querySelector(".image-preview-error");
      expect(errorDiv).not.toBeNull();
      expect(errorDiv.textContent).toContain("image");
    });
  });
});
