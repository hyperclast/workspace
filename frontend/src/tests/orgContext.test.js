/**
 * Unit tests for `lib/orgContext.js`.
 *
 * `setAvailableOrgs` must NOT clobber `currentOrgId` — the open page is
 * canonical and an external collaborator's page-derived org can legitimately
 * sit outside their membership list. We pin that invariant directly here
 * because the regression is invisible at the e2e level (the user just sees
 * the wrong org name in the trigger).
 */

import { describe, test, expect, beforeEach, vi } from "vitest";

async function freshModule(seedCurrentOrgId = null) {
  // Re-import the module with a fresh `window._userState` each time so
  // module-init state is deterministic.
  vi.resetModules();
  if (typeof window !== "undefined") {
    window._userState = { currentOrgId: seedCurrentOrgId, lastPagePerOrg: {} };
  }
  return import("../lib/orgContext.js");
}

describe("orgContext", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  test("loads currentOrgId from window._userState on init", async () => {
    const mod = await freshModule("org-from-page");
    expect(mod.getCurrentOrgId()).toBe("org-from-page");
  });

  test("setAvailableOrgs does not change currentOrgId even when the open-page org is outside membership", async () => {
    const mod = await freshModule("external-collab-org");
    let changed = null;
    mod.setOrgChangedHandler((id) => {
      changed = id;
    });

    mod.setAvailableOrgs([
      { external_id: "member-org-a", name: "A" },
      { external_id: "member-org-b", name: "B" },
    ]);

    expect(mod.getCurrentOrgId()).toBe("external-collab-org");
    expect(changed).toBeNull();
  });

  test("setAvailableOrgs leaves currentOrgId alone when it IS in the membership list", async () => {
    const mod = await freshModule("member-org-a");
    let changed = null;
    mod.setOrgChangedHandler((id) => {
      changed = id;
    });

    mod.setAvailableOrgs([
      { external_id: "member-org-a", name: "A" },
      { external_id: "member-org-b", name: "B" },
    ]);

    expect(mod.getCurrentOrgId()).toBe("member-org-a");
    expect(changed).toBeNull();
  });

  test("setAvailableOrgs([]) does not null out currentOrgId", async () => {
    // Even if the orgs-fetch returns empty (transient backend hiccup,
    // race), we must not blow away the page-derived rune. The page is
    // still open with a real org context.
    const mod = await freshModule("page-org");
    let changed = null;
    mod.setOrgChangedHandler((id) => {
      changed = id;
    });

    mod.setAvailableOrgs([]);

    expect(mod.getCurrentOrgId()).toBe("page-org");
    expect(changed).toBeNull();
  });

  test("setCurrentOrgId triggers the handler exactly once on change", async () => {
    const mod = await freshModule("org-a");
    const calls = [];
    mod.setOrgChangedHandler((id) => calls.push(id));

    mod.setCurrentOrgId("org-b");
    mod.setCurrentOrgId("org-b"); // no-op (same value)
    mod.setCurrentOrgId("org-c");

    expect(calls).toEqual(["org-b", "org-c"]);
  });

  test("setCurrentOrgId dispatches hyperclast:current-org-changed with the new orgId", async () => {
    // The DOM event is the passive fan-out channel that lets the
    // OrgSwitcher trigger label re-read the value after a loadPage()
    // upgrade flips the current org. The registered onOrgChanged
    // callback already covers the imperative pipeline (refetch
    // projects, render sidenav, navigate); the event is purely for
    // UI consumers that just need to re-read state.
    const mod = await freshModule("org-a");
    const events = [];
    const listener = (e) => events.push(e.detail);
    window.addEventListener("hyperclast:current-org-changed", listener);

    try {
      mod.setCurrentOrgId("org-b");
      mod.setCurrentOrgId("org-b"); // no-op — same value, no event
      mod.setCurrentOrgId("org-c");
    } finally {
      window.removeEventListener("hyperclast:current-org-changed", listener);
    }

    expect(events).toEqual([{ orgId: "org-b" }, { orgId: "org-c" }]);
  });
});
