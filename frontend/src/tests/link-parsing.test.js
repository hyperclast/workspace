import { describe, it, expect } from "vitest";

const INTERNAL_LINK_REGEX = /\[([^\]]+)\]\(\/pages\/([a-zA-Z0-9]+)\/?[^)]*\)/g;

function extractInternalLinksFromContent(content, currentPageId = null) {
  const linksList = [];
  const regex = new RegExp(INTERNAL_LINK_REGEX.source, 'g');
  let match;
  while ((match = regex.exec(content)) !== null) {
    const linkText = match[1];
    const pageId = match[2];
    if (pageId !== currentPageId) {
      linksList.push({
        external_id: pageId,
        title: linkText,
        link_text: linkText,
        isLocal: true,
      });
    }
  }
  const seen = new Set();
  return linksList.filter((link) => {
    const key = `${link.external_id}-${link.link_text}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

describe("Internal Link Parsing", () => {
  it("extracts a simple internal link", () => {
    const content = "Check out [My Page](/pages/abc123/)";
    const links = extractInternalLinksFromContent(content);

    expect(links).toHaveLength(1);
    expect(links[0].external_id).toBe("abc123");
    expect(links[0].title).toBe("My Page");
    expect(links[0].link_text).toBe("My Page");
    expect(links[0].isLocal).toBe(true);
  });

  it("returns empty array for empty content (select-all + delete scenario)", () => {
    const links = extractInternalLinksFromContent("");
    expect(links).toHaveLength(0);
  });

  it("returns empty array for whitespace-only content", () => {
    const links = extractInternalLinksFromContent("   \n\n   \t  ");
    expect(links).toHaveLength(0);
  });

  it("extracts multiple internal links", () => {
    const content = `
      See [First Page](/pages/page1/) and [Second Page](/pages/page2/)
      Also check [Third](/pages/page3/)
    `;
    const links = extractInternalLinksFromContent(content);

    expect(links).toHaveLength(3);
    expect(links.map(l => l.external_id)).toEqual(["page1", "page2", "page3"]);
  });

  it("handles links without trailing slash", () => {
    const content = "[No Slash](/pages/abc123)";
    const links = extractInternalLinksFromContent(content);

    expect(links).toHaveLength(1);
    expect(links[0].external_id).toBe("abc123");
  });

  it("excludes self-links when currentPageId is provided", () => {
    const content = "[Self Link](/pages/currentPage/) and [Other](/pages/otherPage/)";
    const links = extractInternalLinksFromContent(content, "currentPage");

    expect(links).toHaveLength(1);
    expect(links[0].external_id).toBe("otherPage");
  });

  it("deduplicates identical links", () => {
    const content = "[Same Page](/pages/abc/) and [Same Page](/pages/abc/)";
    const links = extractInternalLinksFromContent(content);

    expect(links).toHaveLength(1);
  });

  it("keeps links with same page but different link text", () => {
    const content = "[First Text](/pages/abc/) and [Second Text](/pages/abc/)";
    const links = extractInternalLinksFromContent(content);

    expect(links).toHaveLength(2);
    expect(links[0].link_text).toBe("First Text");
    expect(links[1].link_text).toBe("Second Text");
  });

  it("ignores external links", () => {
    const content = "[External](https://example.com) and [Internal](/pages/abc/)";
    const links = extractInternalLinksFromContent(content);

    expect(links).toHaveLength(1);
    expect(links[0].external_id).toBe("abc");
  });

  it("handles alphanumeric page IDs", () => {
    const content = "[Page](/pages/AbC123xYz/)";
    const links = extractInternalLinksFromContent(content);

    expect(links).toHaveLength(1);
    expect(links[0].external_id).toBe("AbC123xYz");
  });

  it("returns empty array for content with no links", () => {
    const content = "Just plain text without any links";
    const links = extractInternalLinksFromContent(content);

    expect(links).toHaveLength(0);
  });

  it("handles link text with special characters", () => {
    const content = "[My Notes & Ideas (2024)](/pages/abc123/)";
    const links = extractInternalLinksFromContent(content);

    expect(links).toHaveLength(1);
    expect(links[0].title).toBe("My Notes & Ideas (2024)");
  });
});
