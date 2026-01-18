/**
 * decorateMentions.js Tests
 *
 * Tests for @mention decoration including highlighting and cursor interaction.
 */

import { describe, test, expect, afterEach, vi, beforeEach } from "vitest";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { decorateMentions } from "../../decorateMentions.js";

// Mock getUserInfo to control the current user
vi.mock("../../config.js", () => ({
  getUserInfo: vi.fn(() => ({
    user: { externalId: "currentuser123" },
  })),
}));

import { getUserInfo } from "../../config.js";

function createEditor(content) {
  const state = EditorState.create({
    doc: content,
    extensions: [decorateMentions],
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

function getMentionsInDOM(view) {
  return Array.from(view.contentDOM.querySelectorAll(".mention"));
}

describe("decorateMentions", () => {
  let view, parent;

  beforeEach(() => {
    // Reset mock to default
    getUserInfo.mockReturnValue({ user: { externalId: "currentuser123" } });
  });

  afterEach(() => {
    if (view) view.destroy();
    if (parent) parent.remove();
    view = null;
    parent = null;
  });

  describe("Basic mention decoration", () => {
    test("mention gets mention class", () => {
      ({ view, parent } = createEditor("Hello @[Alice](@abc123) there"));
      expect(hasClass(view, "mention")).toBe(true);
    });

    test("own mention gets mention-own class", () => {
      ({ view, parent } = createEditor("Check @[Bob](@currentuser123) out"));
      expect(hasClass(view, "mention-own")).toBe(true);
    });

    test("other user mention does not get mention-own class", () => {
      ({ view, parent } = createEditor("Hello @[Alice](@otheruser456)"));
      const mention = view.contentDOM.querySelector(".mention");
      expect(mention).not.toBeNull();
      expect(mention.classList.contains("mention-own")).toBe(false);
    });

    test("username text is visible when cursor elsewhere", () => {
      ({ view, parent } = createEditor("Before @[Alice](@abc123) after"));

      view.dispatch({ selection: { anchor: 0 } });

      const text = view.contentDOM.textContent;
      expect(text).toContain("Alice");
      // The raw syntax should be hidden
      expect(text).not.toContain("](abc123)");
    });

    test("@ is visible before username when cursor outside", () => {
      ({ view, parent } = createEditor("Hello @[Bob](@xyz789)"));

      view.dispatch({ selection: { anchor: 0 } });

      const text = view.contentDOM.textContent;
      // Should show @Bob (@ visible, [, ](@id) hidden)
      expect(text).toContain("@Bob");
      expect(text).not.toContain("](");
    });
  });

  describe("Cursor interaction", () => {
    test("cursor inside mention shows full syntax", () => {
      ({ view, parent } = createEditor("Hello @[Alice](@abc123) there"));

      // Position cursor inside the mention (after @)
      view.dispatch({ selection: { anchor: 8 } });

      const text = view.contentDOM.textContent;
      expect(text).toContain("@[Alice](@abc123)");
    });

    test("cursor at mention start shows syntax", () => {
      ({ view, parent } = createEditor("Hello @[Alice](@abc123) there"));

      // Position cursor at @
      view.dispatch({ selection: { anchor: 6 } });

      const text = view.contentDOM.textContent;
      expect(text).toContain("@[Alice](@abc123)");
    });

    test("cursor at mention end shows syntax", () => {
      ({ view, parent } = createEditor("@[Alice](@abc123)"));

      // Position cursor at end (just before the closing paren)
      view.dispatch({ selection: { anchor: 15 } });

      const text = view.contentDOM.textContent;
      expect(text).toContain("@[Alice](@abc123)");
    });

    test("moving cursor out of mention hides syntax", () => {
      ({ view, parent } = createEditor("Before @[Alice](@abc123) after"));

      // First position inside mention
      view.dispatch({ selection: { anchor: 10 } });
      // Then move out
      view.dispatch({ selection: { anchor: 0 } });

      const text = view.contentDOM.textContent;
      expect(text).toContain("Alice");
      expect(text).not.toContain("](abc123)");
    });
  });

  describe("Multiple mentions", () => {
    test("multiple mentions on same line", () => {
      ({ view, parent } = createEditor("@[Alice](@a1) and @[Bob](@b2) and @[Carol](@c3)"));

      view.dispatch({ selection: { anchor: 0 } });

      expect(countClass(view, "mention")).toBe(3);
    });

    test("mentions on different lines", () => {
      ({ view, parent } = createEditor("@[Alice](@a1)\n@[Bob](@b2)\n@[Carol](@c3)"));

      expect(countClass(view, "mention")).toBe(3);
    });

    test("cursor on one mention doesn't affect others", () => {
      ({ view, parent } = createEditor("@[Alice](@a1) @[Bob](@b2)"));

      // Position cursor in first mention
      view.dispatch({ selection: { anchor: 3 } });

      const mentions = getMentionsInDOM(view);
      expect(mentions.length).toBe(2);
    });
  });

  describe("Mention data attributes", () => {
    test("mention element has data-user-id attribute", () => {
      ({ view, parent } = createEditor("Hello @[Alice](@userxyz123)"));

      view.dispatch({ selection: { anchor: 0 } });

      const mention = view.contentDOM.querySelector(".mention");
      expect(mention.dataset.userId).toBe("userxyz123");
    });

    test("own mention has data-own=true", () => {
      ({ view, parent } = createEditor("Hello @[Me](@currentuser123)"));

      view.dispatch({ selection: { anchor: 0 } });

      const mention = view.contentDOM.querySelector(".mention");
      expect(mention.dataset.own).toBe("true");
    });

    test("other mention has data-own=false", () => {
      ({ view, parent } = createEditor("Hello @[Other](@otheruser)"));

      view.dispatch({ selection: { anchor: 0 } });

      const mention = view.contentDOM.querySelector(".mention");
      expect(mention.dataset.own).toBe("false");
    });
  });

  describe("Edge cases", () => {
    test("mention with underscore in username", () => {
      ({ view, parent } = createEditor("@[alice_smith](@user1)"));
      expect(hasClass(view, "mention")).toBe(true);
    });

    test("mention with numbers in username", () => {
      ({ view, parent } = createEditor("@[user123](@uid456)"));
      expect(hasClass(view, "mention")).toBe(true);
    });

    test("mention with spaces in username", () => {
      ({ view, parent } = createEditor("@[Alice Smith](@user1)"));
      expect(hasClass(view, "mention")).toBe(true);
    });

    test("empty username - no decoration", () => {
      ({ view, parent } = createEditor("@[](@userid)"));
      expect(hasClass(view, "mention")).toBe(false);
    });

    test("plain @ symbol without mention syntax - no decoration", () => {
      ({ view, parent } = createEditor("email@example.com"));
      expect(hasClass(view, "mention")).toBe(false);
    });

    test("@ without brackets - no decoration", () => {
      ({ view, parent } = createEditor("@alice is not a mention"));
      expect(hasClass(view, "mention")).toBe(false);
    });

    test("incomplete mention syntax - no decoration", () => {
      ({ view, parent } = createEditor("@[Alice]"));
      expect(hasClass(view, "mention")).toBe(false);
    });

    test("nested brackets don't confuse the parser", () => {
      ({ view, parent } = createEditor("[not mention] then @[real](@user1)"));
      expect(countClass(view, "mention")).toBe(1);
    });

    test("mention at very beginning of document", () => {
      ({ view, parent } = createEditor("@[Alice](@abc)"));
      expect(hasClass(view, "mention")).toBe(true);
    });

    test("mention at very end of document", () => {
      ({ view, parent } = createEditor("text @[Alice](@abc)"));
      expect(hasClass(view, "mention")).toBe(true);
    });

    test("back-to-back mentions", () => {
      ({ view, parent } = createEditor("@[A](@a1)@[B](@b2)"));
      expect(countClass(view, "mention")).toBe(2);
    });
  });

  describe("User not logged in", () => {
    test("no user info - mentions still render but none are own", () => {
      getUserInfo.mockReturnValue({ user: null });

      ({ view, parent } = createEditor("@[Alice](@abc123) @[Bob](@currentuser123)"));

      expect(hasClass(view, "mention")).toBe(true);
      // Without current user, no mention should be marked as own
      expect(hasClass(view, "mention-own")).toBe(false);
    });
  });
});
