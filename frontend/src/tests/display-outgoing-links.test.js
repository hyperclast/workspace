import { describe, it, expect } from "vitest";

/**
 * Tests for the displayOutgoingLinks merge logic in LinksTab.svelte.
 *
 * This logic merges locally-parsed outgoing links (from the editor content)
 * with server-confirmed links (from the API). The display list is driven by
 * localOutgoingLinks, with a fallback to serverOutgoingLinks when local data
 * is unavailable (e.g. editor not yet initialised after a page refresh).
 */

function computeDisplayOutgoingLinks(localOutgoingLinks, serverOutgoingLinks) {
  if (localOutgoingLinks.length === 0 && serverOutgoingLinks.length > 0) {
    return serverOutgoingLinks.map((link) => ({ ...link, serverConfirmed: true }));
  }
  const serverMap = new Map();
  for (const link of serverOutgoingLinks) {
    serverMap.set(link.external_id, link);
  }
  return localOutgoingLinks.map((local) => {
    const serverLink = serverMap.get(local.external_id);
    if (serverLink) {
      return {
        ...local,
        title: serverLink.title || local.title,
        serverConfirmed: true,
      };
    }
    return { ...local, serverConfirmed: false };
  });
}

describe("displayOutgoingLinks merge logic", () => {
  it("falls back to server links when local links are empty (page refresh bug fix)", () => {
    const local = [];
    const server = [
      { external_id: "abc", title: "Page A", link_text: "Page A" },
      { external_id: "def", title: "Page B", link_text: "Page B" },
    ];

    const result = computeDisplayOutgoingLinks(local, server);

    expect(result).toHaveLength(2);
    expect(result[0]).toEqual({ ...server[0], serverConfirmed: true });
    expect(result[1]).toEqual({ ...server[1], serverConfirmed: true });
  });

  it("returns empty array when both local and server are empty", () => {
    const result = computeDisplayOutgoingLinks([], []);
    expect(result).toHaveLength(0);
  });

  it("merges local links with server confirmation", () => {
    const local = [{ external_id: "abc", title: "Local Title", link_text: "Local Title" }];
    const server = [{ external_id: "abc", title: "Server Title", link_text: "Server Title" }];

    const result = computeDisplayOutgoingLinks(local, server);

    expect(result).toHaveLength(1);
    expect(result[0].serverConfirmed).toBe(true);
    expect(result[0].title).toBe("Server Title");
  });

  it("marks local-only links as not server confirmed", () => {
    const local = [{ external_id: "new1", title: "Just Typed", link_text: "Just Typed" }];
    const server = [];

    const result = computeDisplayOutgoingLinks(local, server);

    expect(result).toHaveLength(1);
    expect(result[0].serverConfirmed).toBe(false);
    expect(result[0].title).toBe("Just Typed");
  });

  it("uses server title when available, keeps local title otherwise", () => {
    const local = [
      { external_id: "abc", title: "Local A", link_text: "Local A" },
      { external_id: "xyz", title: "Local Only", link_text: "Local Only" },
    ];
    const server = [{ external_id: "abc", title: "Server A", link_text: "Server A" }];

    const result = computeDisplayOutgoingLinks(local, server);

    expect(result).toHaveLength(2);
    expect(result[0].title).toBe("Server A");
    expect(result[0].serverConfirmed).toBe(true);
    expect(result[1].title).toBe("Local Only");
    expect(result[1].serverConfirmed).toBe(false);
  });

  it("preserves local title when server title is empty", () => {
    const local = [{ external_id: "abc", title: "Good Title", link_text: "Good Title" }];
    const server = [{ external_id: "abc", title: "", link_text: "" }];

    const result = computeDisplayOutgoingLinks(local, server);

    expect(result).toHaveLength(1);
    expect(result[0].title).toBe("Good Title");
    expect(result[0].serverConfirmed).toBe(true);
  });
});
