/**
 * Regression: client-side seed race in setupCollaborationAsync.
 *
 * Originally pinned the content-doubling bug where two collaborators
 * opening the same page at the same time both passed an empty-ytext
 * gate in `setupCollaborationAsync` and both inserted the REST content
 * into ytext. Because each browser holds its own Yjs `clientID`, the
 * CRDT kept both inserts and produced `content1234content1234`.
 *
 * The frontend seed has been removed: the server owns hydration and
 * seeds the Yjs doc from `Page.details["content"]` under a per-room
 * advisory lock when the room is empty. The client awaits sync and
 * never inserts REST content into ytext.
 *
 * Pinned here: `decideAfterSync` is a pure function of the sync
 * result alone — it does not take or look at the local ytext, which
 * is what closed the doubling race at the call-site level. The
 * signature enforces this; the tests below pin every branch's return
 * value.
 *
 * The call-site invariant ("`setupCollaborationAsync` never calls
 * `ytext.insert` on the synced path") is pinned by
 * `setup-collaboration-async.test.js`, which spies on the planner
 * `decideAndPlanCollabActions` for every sync outcome. The backend's
 * `test_concurrent_passive_clients_get_server_seed_exactly_once`
 * provides the matching server-side guard via the "exactly one
 * y_updates row" assertion. The E2E
 * `frontend/tests/e2e/content-duplication.spec.js` is the
 * wider-window regression guard — it drives the rewind-restore
 * trigger that puts the room into the seeded-but-empty-Yjs state
 * and opens it from two browser contexts in parallel, catching
 * regressions that widen the race beyond what the unit tests can
 * see.
 */
import { describe, test, expect } from "vitest";

import { decideAfterSync } from "../collaboration.js";

describe("decideAfterSync (pure function)", () => {
  test("synced + not denied → upgrade_to_collab", () => {
    expect(decideAfterSync({ synced: true, accessDenied: false })).toBe("upgrade_to_collab");
  });

  test("synced + accessDenied → denied", () => {
    expect(decideAfterSync({ synced: true, accessDenied: true })).toBe("denied");
  });

  test("not synced → hold_rest_timeout", () => {
    expect(decideAfterSync({ synced: false })).toBe("hold_rest_timeout");
  });

  test("null/undefined sync result → hold_rest_timeout", () => {
    expect(decideAfterSync(null)).toBe("hold_rest_timeout");
    expect(decideAfterSync(undefined)).toBe("hold_rest_timeout");
  });
});
