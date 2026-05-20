/**
 * Unit test for the server → localStorage merge logic that seeds the
 * per-org last-viewed-page map on SPA load.
 *
 * **DRIFT RISK**: the function under test lives in
 * `lib/stores/sidenav.svelte.js` as the exported `mergeServerLastPageMap`.
 * We mirror it here because Svelte 5 `$state` runes don't load under
 * vitest (same constraint that drives the mirror approach in
 * `sidenav-folder-state.test.js`). If the production version changes,
 * this mirror must change in lockstep — otherwise the test continues
 * to pass against the wrong logic. A future improvement would be to
 * extract `mergeServerLastPageMap` into a separate plain-JS module
 * that vitest can import directly; until then, treat the production
 * function's comment as the authoritative spec and keep the mirror
 * byte-identical.
 */

import { describe, test, expect } from "vitest";

// MIRROR: must match `mergeServerLastPageMap` in
// `frontend/src/lib/stores/sidenav.svelte.js` exactly.
function mergeServerLastPageMap(fromServer, existing) {
  const okFromServer =
    fromServer && typeof fromServer === "object" && !Array.isArray(fromServer) ? fromServer : {};
  const okExisting =
    existing && typeof existing === "object" && !Array.isArray(existing) ? existing : {};
  return { ...okFromServer, ...okExisting };
}

describe("last-page-per-org seed merge", () => {
  test("localStorage values WIN over server values when both reference the same org", () => {
    // Server snapshot is a moment-old view; localStorage reflects what
    // this tab just did. Tab-local must not be overwritten on rehydrate.
    const fromServer = { "org-a": "page-server" };
    const existing = { "org-a": "page-just-saved-locally" };

    expect(mergeServerLastPageMap(fromServer, existing)).toEqual({
      "org-a": "page-just-saved-locally",
    });
  });

  test("server values fill in orgs the local cache hasn't seen", () => {
    const fromServer = { "org-a": "page-1", "org-b": "page-2" };
    const existing = { "org-a": "page-1-local" };

    expect(mergeServerLastPageMap(fromServer, existing)).toEqual({
      "org-a": "page-1-local",
      "org-b": "page-2",
    });
  });

  test("missing local cache uses server values verbatim", () => {
    const fromServer = { "org-a": "p1", "org-b": "p2" };

    expect(mergeServerLastPageMap(fromServer, null)).toEqual(fromServer);
    expect(mergeServerLastPageMap(fromServer, undefined)).toEqual(fromServer);
    expect(mergeServerLastPageMap(fromServer, {})).toEqual(fromServer);
  });

  test("missing server snapshot keeps the local cache", () => {
    const existing = { "org-a": "p1" };

    expect(mergeServerLastPageMap(null, existing)).toEqual(existing);
    expect(mergeServerLastPageMap(undefined, existing)).toEqual(existing);
    expect(mergeServerLastPageMap({}, existing)).toEqual(existing);
  });

  test("rejects non-object inputs (e.g. arrays, primitives)", () => {
    // Defensive: if something weird ends up in window._userState the
    // merge shouldn't synthesize a bogus map shape.
    expect(mergeServerLastPageMap(["a", "b"], { "org-a": "p" })).toEqual({ "org-a": "p" });
    expect(mergeServerLastPageMap({ "org-a": "p" }, ["bad"])).toEqual({ "org-a": "p" });
    expect(mergeServerLastPageMap("not an object", { "org-a": "p" })).toEqual({ "org-a": "p" });
  });

  test("empty server and empty local produce empty merged map", () => {
    expect(mergeServerLastPageMap({}, {})).toEqual({});
  });
});

// MIRROR: must match the production IIFE in
// `frontend/src/lib/stores/sidenav.svelte.js` (line ~416) byte-for-byte.
// The IIFE clears `window._userState.lastPagePerOrg` after merging so a
// second run on the same module bails at the early return — that's
// the idempotency guarantee under test.
function runSeedIife(STORAGE_KEY) {
  try {
    const fromServer = window._userState?.lastPagePerOrg;
    if (!fromServer || typeof fromServer !== "object" || Object.keys(fromServer).length === 0) {
      return;
    }
    let existing = {};
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed && typeof parsed === "object") existing = parsed;
      }
    } catch {}
    const merged = mergeServerLastPageMap(fromServer, existing);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(merged));
    } catch {}
    try {
      window._userState.lastPagePerOrg = {};
    } catch {}
  } catch {}
}

describe("last-page-per-org seed IIFE — idempotency", () => {
  const STORAGE_KEY = "last-page-per-org";

  test("re-running the seed after the first run is a no-op", () => {
    // The IIFE runs once at module load. If a hot-reload, dev-mode
    // double-import, or a future refactor invokes it a second time, the
    // empty `lastPagePerOrg` left behind by the first run must short-
    // circuit at the early return — otherwise the second pass would
    // re-merge a stale `existing` over fresh in-tab writes.
    window._userState = { lastPagePerOrg: { "org-a": "page-server" } };
    localStorage.removeItem(STORAGE_KEY);

    runSeedIife(STORAGE_KEY);
    const afterFirst = localStorage.getItem(STORAGE_KEY);
    expect(JSON.parse(afterFirst)).toEqual({ "org-a": "page-server" });
    expect(window._userState.lastPagePerOrg).toEqual({});

    // Simulate a tab-local write *between* the two IIFE runs. The
    // second run must NOT overwrite this — it should bail because the
    // server snapshot is now empty.
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ "org-a": "page-just-saved" }));
    runSeedIife(STORAGE_KEY);

    expect(JSON.parse(localStorage.getItem(STORAGE_KEY))).toEqual({
      "org-a": "page-just-saved",
    });
  });

  test("seed bails out cleanly when window._userState is missing", () => {
    // Defensive: server-rendered routes that don't inject the SPA
    // template (404s, login pages) can leave `window._userState` unset
    // entirely. The IIFE must not throw — it just no-ops.
    delete window._userState;
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ "org-a": "existing" }));

    expect(() => runSeedIife(STORAGE_KEY)).not.toThrow();
    // Pre-existing local state is left intact.
    expect(JSON.parse(localStorage.getItem(STORAGE_KEY))).toEqual({ "org-a": "existing" });
  });
});
