/**
 * LinkModal page-autocomplete tests.
 *
 * The modal calls `/api/pages/autocomplete/` as the user types. The backend
 * preserves cross-org results when `org_id` is absent (for token-based
 * scripts), so the SPA must pass `org_id` from `getCurrentOrgId()` to keep
 * the workspace boundary intact.
 */

import { describe, test, expect, vi, beforeEach, afterEach } from "vitest";

vi.mock("../../csrf.js", () => ({
  csrfFetch: vi.fn(),
}));

import { mount, unmount } from "svelte";
import { csrfFetch } from "../../csrf.js";
import { setCurrentOrgId } from "../../lib/orgContext.js";
import LinkModal from "../../lib/components/LinkModal.svelte";

const DEBOUNCE_MS = 150;

async function flushDebounce() {
  await vi.advanceTimersByTimeAsync(DEBOUNCE_MS + 10);
}

function findUrlInput(target) {
  const input = target.querySelector("#link-url");
  if (!input) throw new Error("URL input not found in mounted LinkModal");
  return input;
}

describe("LinkModal page autocomplete", () => {
  let target;
  let component;

  beforeEach(() => {
    vi.useFakeTimers();
    csrfFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ pages: [{ external_id: "p1", title: "Page One" }] }),
    });
    target = document.createElement("div");
    document.body.appendChild(target);
  });

  afterEach(() => {
    if (component) {
      unmount(component);
      component = null;
    }
    target.remove();
    setCurrentOrgId(null);
    vi.clearAllMocks();
    vi.useRealTimers();
  });

  test("appends org_id from getCurrentOrgId when the modal queries autocomplete", async () => {
    setCurrentOrgId("org-abc");

    component = mount(LinkModal, {
      target,
      props: { open: true },
    });

    const input = findUrlInput(target);
    input.value = "foo";
    input.dispatchEvent(new Event("input", { bubbles: true }));

    await flushDebounce();

    expect(csrfFetch).toHaveBeenCalledTimes(1);
    const calledUrl = csrfFetch.mock.calls[0][0];
    expect(calledUrl).toContain("/api/pages/autocomplete/");
    expect(calledUrl).toContain("q=foo");
    expect(calledUrl).toContain("org_id=org-abc");
  });

  test("omits org_id when no current org is set", async () => {
    // Empty bucket — current org could be null on a non-page route or in
    // tests; the modal must not invent a value.
    setCurrentOrgId(null);

    component = mount(LinkModal, {
      target,
      props: { open: true },
    });

    const input = findUrlInput(target);
    input.value = "bar";
    input.dispatchEvent(new Event("input", { bubbles: true }));

    await flushDebounce();

    expect(csrfFetch).toHaveBeenCalledTimes(1);
    const calledUrl = csrfFetch.mock.calls[0][0];
    expect(calledUrl).toContain("q=bar");
    expect(calledUrl).not.toContain("org_id=");
  });

  test("does not call the autocomplete endpoint for absolute URLs", async () => {
    setCurrentOrgId("org-abc");

    component = mount(LinkModal, {
      target,
      props: { open: true },
    });

    const input = findUrlInput(target);
    input.value = "https://example.com/page";
    input.dispatchEvent(new Event("input", { bubbles: true }));

    await flushDebounce();

    // Absolute URLs short-circuit before the debounced autocomplete fetch.
    // Any csrfFetch call here would indicate a cross-org leak via a stray
    // search query.
    const autocompleteCalls = csrfFetch.mock.calls.filter((args) =>
      String(args[0]).includes("/api/pages/autocomplete/")
    );
    expect(autocompleteCalls).toHaveLength(0);
  });
});
