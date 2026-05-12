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
 * Two things are pinned here:
 *
 * 1. `decideAfterSync` is a pure function of the sync result alone —
 *    it does not take or look at the local ytext, which is what
 *    closed the doubling race at the call-site level. The signature
 *    enforces this; the tests below pin every branch's return value.
 *
 * 2. When the server SyncStep2 carries the seed to two clients, the
 *    Yjs merge converges on a single copy. This part is really a Yjs
 *    contract — the test is here as a sanity check on the assumed
 *    behavior, not as a guard against `decideAfterSync` regressions.
 *
 * The call-site regression (someone reintroducing
 * `collabObjects.ytext.insert(0, restContent)` inside
 * `setupCollaborationAsync`) is not catchable here without mocking
 * the WebsocketProvider; the backend's
 * `test_concurrent_passive_clients_get_server_seed_exactly_once`
 * catches it via the "exactly one y_updates row" assertion.
 */
import { describe, test, expect, beforeEach } from "vitest";
import * as Y from "yjs";

import { decideAfterSync } from "../collaboration.js";

const REST_CONTENT = "content1234";

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

describe("Yjs convergence on the server seed (sanity)", () => {
  let docA, docB, textA, textB;

  beforeEach(() => {
    docA = new Y.Doc();
    docB = new Y.Doc();
    textA = docA.getText("codemirror");
    textB = docB.getText("codemirror");
  });

  test("two clients applying the same server seed converge on a single copy", () => {
    // The server seeded the room with REST_CONTENT exactly once via
    // its single advisory-locked write. SyncStep2 propagates those
    // bytes to both clients.
    const serverDoc = new Y.Doc();
    serverDoc.getText("codemirror").insert(0, REST_CONTENT);
    const serverState = Y.encodeStateAsUpdate(serverDoc);

    Y.applyUpdate(docA, serverState, "remote");
    Y.applyUpdate(docB, serverState, "remote");

    expect(textA.toString()).toBe(REST_CONTENT);
    expect(textB.toString()).toBe(REST_CONTENT);
    expect(textA.toString()).toBe(textB.toString());
  });

  test("sequential second client receives the persisted seed without doubling", () => {
    // Client A connects, server seeds, A receives the seed via
    // SyncStep2. B then connects and receives the already-persisted
    // seed bytes — not a fresh seed.
    const serverDoc = new Y.Doc();
    serverDoc.getText("codemirror").insert(0, REST_CONTENT);
    const serverState = Y.encodeStateAsUpdate(serverDoc);

    Y.applyUpdate(docA, serverState, "remote");
    expect(textA.toString()).toBe(REST_CONTENT);

    Y.applyUpdate(docB, serverState, "remote");
    expect(textB.toString()).toBe(REST_CONTENT);
  });
});
