/**
 * Regression: synced + empty-ytext while REST content exists.
 *
 * The earlier fix for "blank a page when the server seed fails" added a
 * `hold_rest_seed_missing` guard that held the REST-rendered view when
 * the WS handshake reported `synced=true` but `ytext.length === 0`. In
 * practice that guard also fired whenever `details.content` was stale
 * (e.g. the page was edited down to empty before the disconnect
 * reconcile shipped), which silently broke real-time sync — peers
 * could connect but never see each other's edits until a reload.
 *
 * The guard has been removed. `decideAfterSync` now takes only the
 * sync result and treats synced as authoritative regardless of ytext
 * length. The server is the single writer for the seed (advisory lock
 * around `_seed_ydoc_from_page`), and the consumer reconciles
 * `details.content` to `""` when the room actually nets to empty
 * (see `_reconcile_empty_page_content` in `backend/collab/consumers.py`).
 */
import { describe, test, expect } from "vitest";

import { decideAfterSync } from "../collaboration.js";

describe("decideAfterSync — synced + empty ytext is authoritative", () => {
  test("upgrades to collab when synced (ytext length is irrelevant)", () => {
    expect(decideAfterSync({ synced: true, accessDenied: false })).toBe("upgrade_to_collab");
  });

  test("returns denied when access denied", () => {
    expect(decideAfterSync({ synced: true, accessDenied: true })).toBe("denied");
  });

  test("returns hold_rest_timeout when sync did not complete", () => {
    expect(decideAfterSync({ synced: false })).toBe("hold_rest_timeout");
    expect(decideAfterSync(null)).toBe("hold_rest_timeout");
    expect(decideAfterSync(undefined)).toBe("hold_rest_timeout");
  });
});
