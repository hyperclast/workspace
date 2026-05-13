/**
 * Regression: client-side seed reintroduction in setupCollaborationAsync.
 *
 * The original content-doubling bug shipped because two collaborators
 * opening the same page each ran an inline seed in
 * `setupCollaborationAsync` — `collabObjects.ytext.insert(0, restContent)`
 * — under a guard that two browsers could pass at once. The fix moved
 * the seed to the server (advisory-locked write inside
 * `_seed_ydoc_from_page`) and removed the inline insert.
 *
 * `setupCollaborationAsync`'s post-sync branch is now driven by the
 * pure planner `decideAndPlanCollabActions({collabObjects, syncResult,
 * filetype})`. The planner returns one of:
 *
 *   { kind: "deny" }                      // sync resolved with accessDenied
 *   { kind: "hold" }                      // sync timed out / null
 *   { kind: "upgrade", filetype }         // server is authoritative
 *
 * It MUST NOT touch `collabObjects.ytext` for any sync outcome. That
 * is the property under test here: a spy on `ytext.insert` that fires
 * for any matrix cell would catch a future contributor reintroducing
 * the inline seed.
 *
 * The `collabObjects` parameter on the planner is intentionally
 * accepted-but-unused so this spy can be attached. Removing it from
 * the signature would silently weaken the canary.
 *
 * Path β refactor rationale: the alternative ("mock everything inside
 * setupCollaborationAsync — `metrics.startSpan`, `upgradeEditor...`,
 * `setupPresenceUI`, `updateCollabStatus`, plus `WebsocketProvider`")
 * would pin the same invariant via a much larger mock surface that
 * drifts every time those collaborators change. Pinning the planner
 * directly lets the wiring layer evolve without breaking the canary.
 */
import { describe, test, expect, beforeEach, vi } from "vitest";
import * as Y from "yjs";

import { decideAndPlanCollabActions } from "../collaboration.js";

function makeCollabObjects() {
  const ydoc = new Y.Doc();
  const ytext = ydoc.getText("codemirror");
  return {
    ydoc,
    ytext,
    provider: { synced: false },
    awareness: null,
  };
}

describe("decideAndPlanCollabActions — action shapes", () => {
  test("synced + not denied → upgrade with filetype", () => {
    const collabObjects = makeCollabObjects();
    const action = decideAndPlanCollabActions({
      collabObjects,
      syncResult: { synced: true, accessDenied: false },
      filetype: "markdown",
    });
    expect(action).toEqual({ kind: "upgrade", filetype: "markdown" });
  });

  test("synced + accessDenied → deny", () => {
    const collabObjects = makeCollabObjects();
    const action = decideAndPlanCollabActions({
      collabObjects,
      syncResult: { synced: true, accessDenied: true },
      filetype: "markdown",
    });
    expect(action).toEqual({ kind: "deny" });
  });

  test("not synced → hold", () => {
    const collabObjects = makeCollabObjects();
    const action = decideAndPlanCollabActions({
      collabObjects,
      syncResult: { synced: false },
      filetype: "markdown",
    });
    expect(action).toEqual({ kind: "hold" });
  });

  test("null sync result → hold", () => {
    const collabObjects = makeCollabObjects();
    expect(
      decideAndPlanCollabActions({
        collabObjects,
        syncResult: null,
        filetype: "markdown",
      })
    ).toEqual({ kind: "hold" });
  });

  test("undefined sync result → hold", () => {
    const collabObjects = makeCollabObjects();
    expect(
      decideAndPlanCollabActions({
        collabObjects,
        syncResult: undefined,
        filetype: "markdown",
      })
    ).toEqual({ kind: "hold" });
  });

  test("preserves filetype on upgrade (not hard-coded)", () => {
    const collabObjects = makeCollabObjects();
    const action = decideAndPlanCollabActions({
      collabObjects,
      syncResult: { synced: true, accessDenied: false },
      filetype: "pdf",
    });
    expect(action).toEqual({ kind: "upgrade", filetype: "pdf" });
  });
});

describe("decideAndPlanCollabActions — never writes to ytext", () => {
  let collabObjects;
  let insertSpy;

  beforeEach(() => {
    collabObjects = makeCollabObjects();
    insertSpy = vi.spyOn(collabObjects.ytext, "insert");
  });

  test.each([
    ["synced + not denied", { synced: true, accessDenied: false }],
    ["synced + accessDenied", { synced: true, accessDenied: true }],
    ["not synced (timeout)", { synced: false }],
    ["null sync result", null],
    ["undefined sync result", undefined],
  ])("does not call ytext.insert for %s", (_label, syncResult) => {
    decideAndPlanCollabActions({
      collabObjects,
      syncResult,
      filetype: "markdown",
    });
    expect(insertSpy).not.toHaveBeenCalled();
    expect(collabObjects.ytext.toString()).toBe("");
  });
});
