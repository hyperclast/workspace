/**
 * Component test for `OrgSwitcher.svelte` reacting to a
 * loadPage()-driven org change.
 *
 * Covers gap §8.10: the switcher trigger label must update when the
 * current org is upgraded externally (e.g. opening a cross-org page
 * deep link), not just when the user clicks the dropdown. The wire
 * between `setCurrentOrgId` and the trigger goes through the
 * `hyperclast:current-org-changed` DOM CustomEvent — this test pins
 * that channel end-to-end through the mounted component.
 */

import { describe, test, expect, vi, beforeEach, afterEach } from "vitest";

vi.mock("../lib/orgSwitch.js", () => ({
  refreshAvailableOrgs: vi.fn().mockResolvedValue(undefined),
}));

import { mount, unmount, flushSync, tick } from "svelte";
import { setAvailableOrgs, setCurrentOrgId } from "../lib/orgContext.js";
import OrgSwitcher from "../lib/components/OrgSwitcher.svelte";

function getTriggerLabel(target) {
  const span = target.querySelector(".org-name");
  if (!span) throw new Error("Trigger label not found in mounted OrgSwitcher");
  return span.textContent;
}

describe("OrgSwitcher refresh on cross-org page open", () => {
  let target;
  let component;

  beforeEach(() => {
    // Seed module-init via the SPA-injected global so the component
    // starts on Org A, then hand it the membership list separately.
    window._userState = { currentOrgId: "org-a", currentOrgName: "Org A" };
    setCurrentOrgId("org-a");
    setAvailableOrgs([
      { external_id: "org-a", name: "Org A" },
      { external_id: "org-b", name: "Org B" },
    ]);
    target = document.createElement("div");
    document.body.appendChild(target);
  });

  afterEach(() => {
    if (component) {
      unmount(component);
      component = null;
    }
    target.remove();
    setAvailableOrgs([]);
    setCurrentOrgId(null);
    delete window._userState;
  });

  test("updates the trigger label when setCurrentOrgId fires the DOM event", async () => {
    component = mount(OrgSwitcher, { target });
    // onMount registers the window listener in a post-mount microtask,
    // so we have to yield before dispatching — otherwise the event
    // fires into the void and the test passes (or fails) for the
    // wrong reason.
    await tick();

    expect(getTriggerLabel(target)).toBe("Org A");

    // loadPage() upgrade path: the open page belongs to a different
    // org, so main.js calls setCurrentOrgId() with the new value.
    // The OrgSwitcher only sees this via the dispatched event.
    setCurrentOrgId("org-b");
    flushSync();

    expect(getTriggerLabel(target)).toBe("Org B");
  });
});
