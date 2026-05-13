"""
Tests for content duplication scenarios.

The duplication issue was a multi-client seed race: when two clients
connected at the same time to a page whose Yjs room was empty but
whose `Page.details["content"]` was non-empty, each frontend would
independently insert the REST content into its local ytext with its
own Yjs `clientID`. The CRDT kept both inserts and the page text
doubled.

The fix is on the server: `PageYjsConsumer._seed_ydoc_from_page`
seeds the doc from `Page.details["content"]` under a per-room
Postgres advisory transaction lock. The first consumer wins the lock
and writes the single seed row to `y_updates`; the loser re-reads
the existing row and applies it locally without writing again. The
frontend no longer inserts REST content into ytext at all.

These tests cover three layers of the contract:

- The original sequential cases below verify backend CRDT behavior
  generally — that identical content from the same logical source
  does not duplicate, that multiple read-only clients don't corrupt
  content, etc.
- `TestConcurrentSeedDoubling` covers the concurrent-loader race
  directly. The class runs two `WebsocketCommunicator`s in parallel
  via `asyncio.gather`. The load-bearing test is
  `test_concurrent_passive_clients_get_server_seed_exactly_once`,
  which drives the post-fix passive client (no local seed) and
  asserts the server writes exactly one row to `y_updates` across
  two concurrent connects. The two `_seed_like_frontend` tests
  attempt to replay the legacy buggy dance but, in practice, their
  competing-insert branch does not fire post-fix (see the helper's
  docstring); they remain useful as a passive safety net against a
  future regression in `make_ydoc()`.

Scope this file does NOT cover:

- A frontend regression that reintroduces an inline
  `ytext.insert(0, restContent)` inside or near
  `setupCollaborationAsync`. The passive clients here send no
  SYNC_UPDATE bytes by definition, so a re-introduced inline write
  on the browser side would slip past the "exactly one row"
  assertion in any timing where the writes serialize. That class of
  regression is pinned by
  `frontend/src/tests/setup-collaboration-async.test.js`
  (call-site canary on the pure planner) and by
  `frontend/tests/e2e/content-duplication.spec.js` (wider-window
  Playwright regression guard).
"""

import asyncio
from unittest.mock import patch

from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase
from pycrdt import (
    Doc,
    Text,
    YMessageType,
    create_sync_message,
    create_update_message,
    handle_sync_message,
)

from backend.asgi import application
from collab.consumers import PageYjsConsumer
from collab.models import YSnapshot, YUpdate
from collab.tasks import sync_snapshot_with_page
from collab.tests import create_page_with_access, create_user_with_org_and_project
from core.helpers import hashify
from pages.models import Page


class TestContentDuplication(TransactionTestCase):
    """Test scenarios that could cause content duplication."""

    async def test_client_sending_same_content_as_server_does_not_duplicate(self):
        """
        Test that when server has content and client sends the SAME content
        (created from the same Yjs operations), it doesn't duplicate.

        This simulates the scenario where:
        1. Server has Yjs state with "Hello World"
        2. A client connects and receives that state
        3. Client sends back the same state (no changes)
        4. Content should NOT be duplicated
        """
        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project)
        room_name = f"page_{page.external_id}"

        original_content = "Hello World\n\nThis is a test."

        # Create server-side Yjs state with content
        server_doc = Doc()
        server_text = server_doc.get("codemirror", type=Text)
        server_text.insert(0, original_content)
        server_update = server_doc.get_update()

        await sync_to_async(YUpdate.objects.create)(
            room_id=room_name,
            yupdate=server_update,
        )

        await sync_to_async(YSnapshot.objects.create)(
            room_id=room_name,
            snapshot=server_update,
            last_update_id=1,
        )

        # Client creates a doc with the SAME content but DIFFERENT operation IDs
        # This simulates what happens when frontend inserts REST content locally
        client_doc = Doc()
        client_text = client_doc.get("codemirror", type=Text)
        client_text.insert(0, original_content)
        client_update = client_doc.get_update()

        # Client connects
        comm = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm.scope["user"] = user

        await comm.connect()
        await asyncio.sleep(0.5)

        # Client sends its local state
        await comm.send_to(bytes_data=client_update)
        await asyncio.sleep(1.0)

        await comm.disconnect()
        await asyncio.sleep(1.0)

        # Check final state
        snapshot = await sync_to_async(YSnapshot.objects.get)(room_id=room_name)
        final_content = snapshot.content

        # PAGE: In a pure CRDT, identical text from different sources WOULD duplicate
        # because they have different operation IDs. However, the y-websocket protocol
        # may handle this differently. This test documents the actual behavior.
        #
        # If this test fails with duplicated content, it confirms the CRDT behavior
        # and validates that the frontend fix (not inserting locally) is necessary.
        self.assertEqual(
            final_content,
            original_content,
            f"Content should not be duplicated.\n"
            f"Expected: {repr(original_content)}\n"
            f"Got: {repr(final_content)}\n"
            f"Length expected: {len(original_content)}, got: {len(final_content)}",
        )

    async def test_multiple_clients_with_local_state_dont_compound_duplication(self):
        """
        Test that multiple clients each sending local state don't cause
        compounding duplication.

        If duplication occurred, after 3 reconnects with "Hi":
        - After 1st: "HiHi"
        - After 2nd: "HiHiHiHi"
        - After 3rd: "HiHiHiHiHiHiHiHi"

        This test verifies the actual behavior.
        """
        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project)
        room_name = f"page_{page.external_id}"

        original = "Hi"

        # Create initial server state
        server_doc = Doc()
        server_text = server_doc.get("codemirror", type=Text)
        server_text.insert(0, original)

        await sync_to_async(YUpdate.objects.create)(
            room_id=room_name,
            yupdate=server_doc.get_update(),
        )

        await sync_to_async(YSnapshot.objects.create)(
            room_id=room_name,
            snapshot=server_doc.get_update(),
            last_update_id=1,
        )

        # Simulate 3 clients, each with their own local state
        for i in range(3):
            client_doc = Doc()
            client_text = client_doc.get("codemirror", type=Text)
            client_text.insert(0, original)

            comm = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
            comm.scope["user"] = user

            await comm.connect()
            await asyncio.sleep(0.3)

            await comm.send_to(bytes_data=client_doc.get_update())

            await asyncio.sleep(0.3)
            await comm.disconnect()
            await asyncio.sleep(0.5)

        # Check final state
        final_snapshot = await sync_to_async(YSnapshot.objects.get)(room_id=room_name)
        final_content = final_snapshot.content

        self.assertEqual(
            final_content,
            original,
            f"Content should not compound after multiple clients.\n"
            f"Expected: {repr(original)} (length {len(original)})\n"
            f"Got: {repr(final_content)} (length {len(final_content)})",
        )

    async def test_read_only_clients_dont_corrupt_content(self):
        """
        Test that multiple clients connecting and disconnecting
        without making edits doesn't corrupt the content.
        """
        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project)
        room_name = f"page_{page.external_id}"

        original = "Original content that should not change"

        # Setup initial server state
        server_doc = Doc()
        server_text = server_doc.get("codemirror", type=Text)
        server_text.insert(0, original)

        await sync_to_async(YUpdate.objects.create)(
            room_id=room_name,
            yupdate=server_doc.get_update(),
        )

        await sync_to_async(YSnapshot.objects.create)(
            room_id=room_name,
            snapshot=server_doc.get_update(),
            last_update_id=1,
        )

        # Multiple clients connect and disconnect WITHOUT sending local state
        for i in range(5):
            comm = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
            comm.scope["user"] = user

            await comm.connect()
            await asyncio.sleep(0.2)
            await comm.disconnect()
            await asyncio.sleep(0.2)

        # Content should be unchanged
        final_snapshot = await sync_to_async(YSnapshot.objects.get)(room_id=room_name)
        self.assertEqual(
            final_snapshot.content, original, "Content should not change after multiple read-only connections"
        )

    async def test_snapshot_content_extraction_works(self):
        """
        Test that the YSnapshot.content property correctly extracts
        text from the Yjs document.
        """
        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project)
        room_name = f"page_{page.external_id}"

        # Create document with specific content
        doc = Doc()
        text = doc.get("codemirror", type=Text)
        text.insert(0, "Line 1\n")
        text.insert(7, "Line 2\n")
        text.insert(14, "Line 3")

        await sync_to_async(YSnapshot.objects.create)(
            room_id=room_name,
            snapshot=doc.get_update(),
            last_update_id=0,
        )

        snapshot = await sync_to_async(YSnapshot.objects.get)(room_id=room_name)
        self.assertEqual(snapshot.content, "Line 1\nLine 2\nLine 3")

    async def test_server_preserves_content_after_client_connects(self):
        """
        Test that server content is preserved when a client connects,
        receives the state, and disconnects without making changes.
        """
        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project)
        room_name = f"page_{page.external_id}"

        original_content = "Server content"

        # Create server state
        server_doc = Doc()
        server_text = server_doc.get("codemirror", type=Text)
        server_text.insert(0, original_content)
        server_update = server_doc.get_update()

        await sync_to_async(YUpdate.objects.create)(
            room_id=room_name,
            yupdate=server_update,
        )

        await sync_to_async(YSnapshot.objects.create)(
            room_id=room_name,
            snapshot=server_update,
            last_update_id=1,
        )

        # Verify initial state
        snapshot_before = await sync_to_async(YSnapshot.objects.get)(room_id=room_name)
        self.assertEqual(snapshot_before.content, original_content)

        # Client connects and disconnects without sending anything
        comm = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm.scope["user"] = user

        await comm.connect()
        await asyncio.sleep(0.5)
        await comm.disconnect()
        await asyncio.sleep(0.5)

        # Server state should be unchanged
        snapshot_after = await sync_to_async(YSnapshot.objects.get)(room_id=room_name)
        self.assertEqual(
            snapshot_after.content,
            original_content,
            "Server content should be preserved after client connects/disconnects",
        )


class TestConcurrentSeedDoubling(TransactionTestCase):
    """Regression tests for the concurrent-loader seed race.

    Two clients simultaneously hydrate from a room whose Yjs storage is
    empty but whose `Page.details["content"]` is non-empty (PDF imports,
    daily notes from a template, rewind-restored pages, REST/CLI/MCP
    writes, etc.). Pre-fix, each client's frontend gate
    (`frontend/src/main.js:setupCollaborationAsync`) saw `ytext.length
    === 0` and inserted the REST content into the local ytext with its
    own Yjs `clientID`; the CRDT kept both, doubling the page.

    Post-fix, the server seeds the empty room from
    `Page.details["content"]` under a per-room advisory transaction
    lock (`PageYjsConsumer._seed_ydoc_from_page`), and the frontend
    no longer inserts REST content.

    The load-bearing post-fix signal is
    `test_concurrent_passive_clients_get_server_seed_exactly_once`:
    it drives the *post-fix actual* client (no local seed), asserts
    both clients receive the seed via SYNC_STEP2, and asserts
    `y_updates` ends up with exactly one row across two concurrent
    connects. That single-row assertion is what proves the per-room
    advisory lock is doing its job — without the lock, two consumers
    would each call `_seed_ydoc_from_page` and produce two rows
    racing into a CRDT merge.

    `test_concurrent_clients_do_not_double_seeded_content` and
    `test_concurrent_clients_after_rewind_do_not_double` use the
    `_seed_like_frontend` helper, which *attempts* to replay the
    legacy buggy dance. Post-fix that branch does not fire because
    the server seed reaches the client via SYNC_STEP2 before the
    "if empty" check; see `_seed_like_frontend`'s docstring. Those
    two tests therefore primarily pin the disconnect-snapshot path
    against doubling for two concurrent connects (the same room
    state but different exercise) rather than a true legacy-client
    race. They are kept around because the legacy branch is a
    passive safety net: if `make_ydoc()` ever regresses to handing
    back an empty doc on the synced path, those tests would catch
    the doubling.
    """

    SEED_CONTENT = "content1234"

    async def _drain_and_apply(self, comm, local_doc, *, iterations=6, timeout=0.4):
        """Drain pending WS messages and merge any SYNC frames into `local_doc`.

        Mimics y-websocket's behavior on the client: incoming SYNC_STEP1
        prompts us to reply with SYNC_STEP2; incoming SYNC_STEP2 or
        SYNC_UPDATE bytes get applied to the local doc. Awareness frames
        and JSON status messages are ignored — we just need the doc to
        converge with whatever the server has sent so far.
        """
        replies = []
        for _ in range(iterations):
            try:
                msg = await comm.receive_from(timeout=timeout)
            except asyncio.TimeoutError:
                break
            if not isinstance(msg, (bytes, bytearray)) or len(msg) < 2:
                continue
            raw = bytes(msg)
            if raw[0] != YMessageType.SYNC:
                continue
            try:
                reply = handle_sync_message(raw[1:], local_doc)
            except Exception:
                continue
            if reply is not None:
                replies.append(reply)
        for reply in replies:
            await comm.send_to(bytes_data=reply)

    async def _safe_disconnect(self, comm):
        """Disconnect, tolerating CancelledError from the ASGI test harness.

        The consumer's disconnect handler runs to completion (final
        snapshot, ystore pool close) before the ASGI future is cancelled,
        so swallowing the cancellation is safe.
        """
        try:
            await comm.disconnect()
        except (asyncio.CancelledError, Exception):
            pass

    async def _seed_like_frontend(self, comm):
        """Replay the *legacy* (pre-fix) client seed dance.

        Important: in the post-fix world the competing-insert branch
        in step 3 below does NOT actually fire. The server seeds the
        room under a per-room advisory lock during `make_ydoc()` and
        the seed reaches the client via SYNC_STEP2, so by the time
        the `if len(str(local_text)) == 0` check runs, `local_text`
        already contains the seed and the branch is skipped.

        That means the two tests that use this helper
        (`test_concurrent_clients_do_not_double_seeded_content` and
        `test_concurrent_clients_after_rewind_do_not_double`) are
        effectively running the *passive* client dance plus a
        post-merge echo. They still pin a meaningful invariant —
        that the disconnect-snapshot path does not introduce
        doubling after two concurrent connects — but they do NOT,
        in practice, exercise a true legacy client competing with
        the server seed. The load-bearing post-fix coverage for the
        single-writer steady state lives in
        `test_concurrent_passive_clients_get_server_seed_exactly_once`,
        which asserts `y_updates` contains exactly one row across
        two concurrent connects.

        The legacy seed step is left in place for two reasons: it
        documents the historical (pre-fix) frontend behavior in
        executable form, and it acts as a passive safety net — if a
        future change makes `make_ydoc()` regress to handing back an
        empty doc on the synced path, the legacy branch would start
        firing again and these tests would still catch the doubling.

        Steps:

        1. Send SYNC_STEP1 with the local (empty) state vector so the
           server replies with whatever it already has — post-fix
           this includes the server's single seed update.
        2. Drain incoming SYNC frames and merge them into the local
           doc.
        3. If local ytext is still empty, seed it with the REST
           content and broadcast as a SYNC_UPDATE. This is the
           historically racy step; see the note above for why it
           does not fire today.
        4. Drain the round trip; whatever the other client wrote
           shows up here.
        5. Echo the now-merged state back as a SYNC_UPDATE so the
           consumer's ydoc converges with what the client sees.
           Without this, each consumer's ydoc only ever knows about
           its own local view and the disconnect-snapshot path is
           one-sided.
        """
        local_doc = Doc()
        local_text = local_doc.get("codemirror", type=Text)

        await comm.send_to(bytes_data=create_sync_message(local_doc))
        await self._drain_and_apply(comm, local_doc)

        if len(str(local_text)) == 0:
            local_text.insert(0, self.SEED_CONTENT)
            await comm.send_to(bytes_data=create_update_message(local_doc.get_update()))

        await self._drain_and_apply(comm, local_doc)

        # Echo merged state so the server's ydoc converges with what the
        # client now sees. Without this, each consumer's ydoc only ever
        # knows about its own seed and the disconnect snapshot is
        # one-sided — masking the page-content doubling in the test.
        await comm.send_to(bytes_data=create_update_message(local_doc.get_update()))
        await self._drain_and_apply(comm, local_doc)

        return local_doc

    async def _replay_updates(self, room_name):
        """Replay every persisted YUpdate row for the room into a fresh doc.

        This is the strongest invariant: the *set* of persisted updates
        must, when applied in order, reproduce the original single copy.
        After the fix, only one row exists (the server-side seed); on
        `master`, two concurrent client seeds each produce a row and the
        replay yields doubled content.
        """
        rows = await sync_to_async(list)(
            YUpdate.objects.filter(room_id=room_name).order_by("id").values_list("yupdate", flat=True)
        )
        doc = Doc()
        for row in rows:
            doc.apply_update(bytes(row))
        return str(doc.get("codemirror", type=Text)), len(rows)

    async def test_concurrent_clients_do_not_double_seeded_content(self):
        """Two clients hydrating an empty room concurrently must not double the seed.

        Setup: `Page.details["content"] = "content1234"`, no YUpdate /
        YSnapshot rows for the room. This is the state produced by PDF
        imports, daily notes, REST/CLI/MCP writes, copy_from, and the
        rewind path — anything that writes through `Page.details` without
        touching the Yjs log.

        Runs both clients through `_seed_like_frontend`. Post-fix the
        helper's competing-insert branch does not fire — the server
        seed arrives via SYNC_STEP2 before the "if empty" check — so
        this test primarily pins the disconnect-snapshot path: two
        concurrent consumers, each taking its own final snapshot,
        must converge on the un-doubled content in both `y_updates`
        replay and `Page.details["content"]`. See
        `test_concurrent_passive_clients_get_server_seed_exactly_once`
        for the load-bearing "exactly one seed row across two
        concurrent connects" assertion.
        """
        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project, details={"content": self.SEED_CONTENT})
        room_name = f"page_{page.external_id}"

        self.assertEqual(
            await sync_to_async(YUpdate.objects.filter(room_id=room_name).count)(),
            0,
            "Precondition: no YUpdate rows for the room",
        )
        self.assertFalse(
            await sync_to_async(YSnapshot.objects.filter(room_id=room_name).exists)(),
            "Precondition: no YSnapshot row for the room",
        )

        comm_a = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm_b = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm_a.scope["user"] = user
        comm_b.scope["user"] = user

        # Concurrent connect: both hydrations enter `make_ydoc()` at
        # roughly the same time. Pre-fix, neither wrote a seed before
        # the other read, so both clients seeded locally and the CRDT
        # kept both inserts. Post-fix, one consumer wins the per-room
        # advisory lock, writes the single seed row, and the other
        # re-reads it without writing — pinned by the row-count
        # assertion in
        # `test_concurrent_passive_clients_get_server_seed_exactly_once`.
        connect_results = await asyncio.gather(comm_a.connect(), comm_b.connect())
        for connected, _ in connect_results:
            self.assertTrue(connected, "Both WebSocket connections must accept")

        # Run the frontend seed dance on both clients concurrently.
        await asyncio.gather(
            self._seed_like_frontend(comm_a),
            self._seed_like_frontend(comm_b),
        )

        # Disconnect concurrently so each consumer's disconnect snapshot
        # captures the merged state from its ydoc.
        await asyncio.gather(
            self._safe_disconnect(comm_a),
            self._safe_disconnect(comm_b),
        )

        # Let the disconnect snapshot path settle. `JOB_RUNNER=None` in
        # tests runs `sync_snapshot_with_page` synchronously inside
        # `upsert_snapshot`, but the disconnect handler awaits a few
        # async tasks first.
        await asyncio.sleep(0.5)

        # Assertion 1: Replaying every persisted update row must produce
        # the original single copy. Pre-fix, two rows existed (one per
        # consumer's observer) and replay yielded doubled content;
        # post-fix the legacy branch in `_seed_like_frontend` does not
        # fire (the server seed arrives via SYNC_STEP2 first), so this
        # assertion mainly pins that the per-consumer disconnect
        # snapshot path does not introduce doubling.
        replayed_text, row_count = await self._replay_updates(room_name)
        self.assertEqual(
            replayed_text,
            self.SEED_CONTENT,
            f"y_updates replay must produce un-doubled content; "
            f"got {row_count} rows replaying to {replayed_text!r}",
        )

        # Assertion 2: `Page.details["content"]` must reflect the
        # un-doubled content. The disconnect snapshot path writes the
        # snapshot and enqueues `sync_snapshot_with_page`, which copies
        # the snapshot text back into `Page.details`. We call it directly
        # in case the inline enqueue raced with the assertion above.
        await sync_to_async(sync_snapshot_with_page)(room_name)
        refreshed = await sync_to_async(Page.objects.get)(external_id=page.external_id)
        self.assertEqual(
            refreshed.details["content"],
            self.SEED_CONTENT,
            f"Page.details['content'] must not be doubled; " f"got {refreshed.details['content']!r}",
        )

    async def test_concurrent_clients_after_rewind_do_not_double(self):
        """Rewind wipes Yjs storage; the next two concurrent loaders must not double.

        `backend/pages/api/rewind.py` deletes every `YUpdate` and
        `YSnapshot` row for the room and rewrites
        `Page.details["content"]` from the chosen rewind snapshot. The
        room is then in the same empty-Yjs / non-empty-details state as
        the import / daily-note flows, so the same concurrent-loader
        race applies. This test seeds the page through a normal editor
        path first, then simulates the rewind wipe before running the
        concurrent seed dance.

        Same coverage caveat as
        `test_concurrent_clients_do_not_double_seeded_content`: the
        legacy branch in `_seed_like_frontend` does not fire
        post-fix. The load-bearing single-row-of-y_updates assertion
        for the rewind state lives implicitly under
        `test_concurrent_passive_clients_get_server_seed_exactly_once`'s
        contract, which exercises the same code path
        (`_seed_ydoc_from_page`) regardless of how the room got to
        the empty-Yjs / non-empty-details state.
        """
        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project)
        room_name = f"page_{page.external_id}"

        # Phase 1: seed prior editor activity. We don't go through a WS
        # consumer here — directly creating YUpdate + YSnapshot rows is
        # enough to model "the page used to be a normal editor page."
        prior_doc = Doc()
        prior_doc.get("codemirror", type=Text).insert(0, "older editor content")
        prior_update = prior_doc.get_update()
        prior_row = await sync_to_async(YUpdate.objects.create)(
            room_id=room_name,
            yupdate=prior_update,
        )
        await sync_to_async(YSnapshot.objects.create)(
            room_id=room_name,
            snapshot=prior_update,
            last_update_id=prior_row.id,
        )

        # Phase 2: simulate rewind restore — delete CRDT state and
        # rewrite Page.details. Mirrors
        # `backend/pages/api/rewind.py:restore_rewind`.
        await sync_to_async(YUpdate.objects.filter(room_id=room_name).delete)()
        await sync_to_async(YSnapshot.objects.filter(room_id=room_name).delete)()
        page.details["content"] = self.SEED_CONTENT
        await sync_to_async(page.save)(update_fields=["details", "modified"])

        self.assertEqual(
            await sync_to_async(YUpdate.objects.filter(room_id=room_name).count)(),
            0,
            "Rewind must leave the room with no YUpdate rows",
        )
        self.assertFalse(
            await sync_to_async(YSnapshot.objects.filter(room_id=room_name).exists)(),
            "Rewind must leave the room with no YSnapshot row",
        )

        # Phase 3: concurrent reconnect — same dance as the first test.
        comm_a = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm_b = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm_a.scope["user"] = user
        comm_b.scope["user"] = user

        connect_results = await asyncio.gather(comm_a.connect(), comm_b.connect())
        for connected, _ in connect_results:
            self.assertTrue(connected, "Both WebSocket connections must accept")

        await asyncio.gather(
            self._seed_like_frontend(comm_a),
            self._seed_like_frontend(comm_b),
        )

        await asyncio.gather(
            self._safe_disconnect(comm_a),
            self._safe_disconnect(comm_b),
        )
        await asyncio.sleep(0.5)

        replayed_text, row_count = await self._replay_updates(room_name)
        self.assertEqual(
            replayed_text,
            self.SEED_CONTENT,
            f"After rewind, y_updates replay must produce un-doubled content; "
            f"got {row_count} rows replaying to {replayed_text!r}",
        )

        await sync_to_async(sync_snapshot_with_page)(room_name)
        refreshed = await sync_to_async(Page.objects.get)(external_id=page.external_id)
        self.assertEqual(
            refreshed.details["content"],
            self.SEED_CONTENT,
            f"After rewind, Page.details['content'] must not be doubled; " f"got {refreshed.details['content']!r}",
        )

    async def _passive_client_sync(self, comm):
        """Replay the *post-fix* client handshake — sync only, no local seed.

        Mirrors the current `frontend/src/main.js::setupCollaborationAsync`:
        send SYNC_STEP1, accept whatever the server sends, never insert
        REST content locally. The server is the only writer of the seed.
        Returns the local doc so the caller can assert its contents.
        """
        local_doc = Doc()
        await comm.send_to(bytes_data=create_sync_message(local_doc))
        await self._drain_and_apply(comm, local_doc)
        return local_doc

    async def test_concurrent_passive_clients_get_server_seed_exactly_once(self):
        """Two post-fix clients connecting concurrently to an empty room
        must each see the server's single seed, and `y_updates` must
        end up with exactly one row.

        This pins the architecture after Step 4: the frontend never
        inserts REST content into ytext, so the only way the seed
        reaches the client is via SYNC_STEP2 carrying the server's
        advisory-locked write. With two concurrent connects, exactly
        one consumer wins the lock and writes the row; the other
        re-reads it inside the same lock and serves it to its client.
        """
        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project, details={"content": self.SEED_CONTENT})
        room_name = f"page_{page.external_id}"

        self.assertEqual(
            await sync_to_async(YUpdate.objects.filter(room_id=room_name).count)(),
            0,
            "Precondition: no YUpdate rows for the room",
        )

        comm_a = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm_b = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm_a.scope["user"] = user
        comm_b.scope["user"] = user

        connect_results = await asyncio.gather(comm_a.connect(), comm_b.connect())
        for connected, _ in connect_results:
            self.assertTrue(connected, "Both WebSocket connections must accept")

        doc_a, doc_b = await asyncio.gather(
            self._passive_client_sync(comm_a),
            self._passive_client_sync(comm_b),
        )

        # Both clients must see the seed content delivered by the server.
        self.assertEqual(str(doc_a.get("codemirror", type=Text)), self.SEED_CONTENT)
        self.assertEqual(str(doc_b.get("codemirror", type=Text)), self.SEED_CONTENT)

        await asyncio.gather(
            self._safe_disconnect(comm_a),
            self._safe_disconnect(comm_b),
        )
        await asyncio.sleep(0.5)

        # The server-side seed runs under a per-room advisory lock and
        # writes exactly once. Without a passive-client write echo,
        # this assertion is the strongest signal that the seed is
        # single-writer in the steady-state post-fix flow.
        row_count = await sync_to_async(YUpdate.objects.filter(room_id=room_name).count)()
        self.assertEqual(
            row_count,
            1,
            f"Server seed must be written exactly once across two concurrent connects; got {row_count} rows",
        )

        replayed_text, _ = await self._replay_updates(room_name)
        self.assertEqual(replayed_text, self.SEED_CONTENT)

        await sync_to_async(sync_snapshot_with_page)(room_name)
        refreshed = await sync_to_async(Page.objects.get)(external_id=page.external_id)
        self.assertEqual(refreshed.details["content"], self.SEED_CONTENT)


class TestStaleContentReconciliation(TransactionTestCase):
    """Regression tests for the stale-`details.content` bug.

    When users collaboratively delete a page back to empty, the
    consumer's `_take_snapshot` skips writing the resulting ≤2-byte
    snapshot (it would crash y-websocket clients). The snapshot
    upsert is the only enqueuer of `sync_snapshot_with_page`, so
    `Page.details["content"]` keeps whatever value the previous
    non-empty snapshot wrote. The next visitor's REST page payload
    then carries that stale content, the editor briefly renders it
    before the WS sync wipes it back out, and any tooling that reads
    `details.content` directly (Ask, search, exports) sees the wrong
    text until someone re-edits the page.

    The server-side fix lives in
    `PageYjsConsumer._reconcile_empty_page_content`: when the
    captured doc serializes empty AND the room already has
    `y_updates` rows (proving the empty state was reached through
    edits, not seed failure), `Page.details["content"]` is cleared
    to `""`.

    The `y_updates`-exists gate is load-bearing for data safety:
    the `_seed_ydoc_from_page` helper is fail-open (a transient DB
    error returns False and the consumer accepts the connection
    with an empty doc). Without the gate, a transient seed failure
    would erase `Page.details["content"]` entirely. The tests below
    pin both branches.
    """

    STALE_CONTENT = "stale content the previous session left behind"

    async def _build_empty_net_updates(self):
        """Capture y_updates whose net effect is an empty ytext.

        Uses an observer on a single doc to record the insert and
        the matching delete as separate update bytes — replaying
        both reconstructs the same empty-net state the user-driven
        delete path produces in production.
        """
        captured: list[bytes] = []

        doc = Doc()
        text = doc.get("codemirror", type=Text)

        def _on_txn(event):
            update = getattr(event, "update", None)
            if update:
                captured.append(bytes(update))

        doc.observe(_on_txn)
        text.insert(0, "x")
        del text[0:1]
        return captured

    async def _drain_after_sync(self, comm, *, iterations=6, timeout=0.4):
        """Drain incoming WS messages so hydration completes before disconnect.

        Reads `comm.output_queue` directly instead of going through
        `comm.receive_from`. asgiref's `receive_output` cancels the
        ASGI future on TimeoutError, which would tear down the
        consumer task — fine for single-client tests but fatal for the
        two-client peer test below where B's consumer must stay alive
        to receive A's broadcast. `asyncio.wait_for` here only cancels
        the inner `output_queue.get()` waiter, not the consumer.
        """
        for _ in range(iterations):
            try:
                await asyncio.wait_for(comm.output_queue.get(), timeout=timeout)
            except asyncio.TimeoutError:
                break

    async def test_disconnect_with_empty_doc_and_prior_updates_reconciles_details(self):
        """Stale `details.content` + `y_updates` netting to empty → reconciled to "".

        Pre-fix: the disconnect snapshot path skipped the empty-doc
        snapshot, `sync_snapshot_with_page` was never enqueued, and
        `Page.details["content"]` stayed `STALE_CONTENT`. The next
        REST page load returned that stale body even though the CRDT
        was empty, and downstream readers (Ask, search, exports) saw
        the wrong text until someone re-edited the page.

        Post-fix: the reconcile helper fires from the empty-doc skip
        branch (and again from disconnect for passive sessions) and
        rewrites `details.content` to `""`, matching the CRDT state.
        """
        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project, details={"content": self.STALE_CONTENT})
        room_name = f"page_{page.external_id}"

        # Persist y_updates whose replay produces an empty ytext. Two
        # rows is enough to model "the page was edited and then
        # deleted back to empty" without going through a WS dance.
        empty_net_updates = await self._build_empty_net_updates()
        self.assertEqual(
            len(empty_net_updates),
            2,
            "Test precondition: insert + delete must capture two update rows",
        )
        for u in empty_net_updates:
            await sync_to_async(YUpdate.objects.create)(room_id=room_name, yupdate=u)

        # Sanity-check: replaying the rows yields an empty doc.
        replay_doc = Doc()
        for u in empty_net_updates:
            replay_doc.apply_update(u)
        self.assertEqual(str(replay_doc.get("codemirror", type=Text)), "")

        comm = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm.scope["user"] = user
        connected, _ = await comm.connect()
        self.assertTrue(connected, "WebSocket connection must accept")

        # Send SYNC_STEP1 so the consumer finishes hydration; we are
        # the passive client (no local seed).
        await comm.send_to(bytes_data=create_sync_message(Doc()))
        await self._drain_after_sync(comm)

        try:
            await comm.disconnect()
        except (asyncio.CancelledError, Exception):
            pass
        await asyncio.sleep(0.5)

        refreshed = await sync_to_async(Page.objects.get)(external_id=page.external_id)
        self.assertEqual(
            refreshed.details["content"],
            "",
            f"Reconcile must clear stale details.content; got " f"{refreshed.details['content']!r}",
        )
        self.assertEqual(
            refreshed.details.get("content_hash"),
            hashify(""),
            "Reconcile must refresh content_hash to match the cleared content",
        )

    async def test_disconnect_with_empty_doc_and_no_prior_updates_preserves_details(self):
        """Empty doc + zero `y_updates` rows → reconcile MUST NOT touch `details.content`.

        This is the seed-failure case: `_seed_ydoc_from_page` is
        fail-open by design (transient DB error returns False and
        the consumer accepts the connection with an empty doc).
        Reconciling in that state would erase the user's content
        outright. The `y_updates`-exists gate keeps `details.content`
        intact so the next opener retries the seed.
        """
        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project, details={"content": self.STALE_CONTENT})
        room_name = f"page_{page.external_id}"

        # Force the seed to fail-open without writing a row. The
        # production helper catches its own exceptions and returns
        # False; mock the same shape directly. The first arg is `self`
        # because `patch.object` replaces the unbound method on the
        # class, so the descriptor protocol still binds the instance.
        async def _no_op_seed(self, _doc):
            return False

        with patch.object(PageYjsConsumer, "_seed_ydoc_from_page", new=_no_op_seed):
            comm = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
            comm.scope["user"] = user
            connected, _ = await comm.connect()
            self.assertTrue(connected, "WebSocket connection must accept")

            await comm.send_to(bytes_data=create_sync_message(Doc()))
            await self._drain_after_sync(comm)

            try:
                await comm.disconnect()
            except (asyncio.CancelledError, Exception):
                pass
            await asyncio.sleep(0.5)

        self.assertEqual(
            await sync_to_async(YUpdate.objects.filter(room_id=room_name).count)(),
            0,
            "Precondition: seed must have fail-opened without writing a row",
        )
        refreshed = await sync_to_async(Page.objects.get)(external_id=page.external_id)
        self.assertEqual(
            refreshed.details["content"],
            self.STALE_CONTENT,
            "Seed-failure case must not clobber details.content",
        )

    async def test_two_clients_can_exchange_edits_against_stale_state(self):
        """Two clients arriving at the stale-state page must still sync edits.

        Pre-fix the consumer's broadcast path was already correct —
        this test pins the backend contract that an empty-ytext /
        non-empty-`details.content` room is reachable, broadcast
        still works between live consumers, and the next snapshot
        path correctly persists the new content to
        `Page.details["content"]` (not the stale value).

        Post-fix the same flow also exercises the reconcile path:
        after both disconnect with the doc holding "hello", the
        snapshot is non-empty so reconcile does NOT fire and
        `sync_snapshot_with_page` writes "hello" through normally.
        """
        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project, details={"content": self.STALE_CONTENT})
        room_name = f"page_{page.external_id}"

        empty_net_updates = await self._build_empty_net_updates()
        for u in empty_net_updates:
            await sync_to_async(YUpdate.objects.create)(room_id=room_name, yupdate=u)

        comm_a = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm_b = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm_a.scope["user"] = user
        comm_b.scope["user"] = user

        connect_results = await asyncio.gather(comm_a.connect(), comm_b.connect())
        for connected, _ in connect_results:
            self.assertTrue(connected, "Both WebSocket connections must accept")

        # Both clients send SYNC_STEP1 with their (empty) state. The
        # server replies with whatever it has (which is empty here,
        # because the y_updates rows net to nothing).
        doc_a = Doc()
        doc_b = Doc()
        await asyncio.gather(
            comm_a.send_to(bytes_data=create_sync_message(doc_a)),
            comm_b.send_to(bytes_data=create_sync_message(doc_b)),
        )
        await asyncio.gather(
            self._drain_after_sync(comm_a),
            self._drain_after_sync(comm_b),
        )

        # Client A inserts "hello" and broadcasts as a SYNC_UPDATE.
        text_a = doc_a.get("codemirror", type=Text)
        captured_a: list[bytes] = []

        def _on_a(event):
            update = getattr(event, "update", None)
            if update:
                captured_a.append(bytes(update))

        doc_a.observe(_on_a)
        text_a.insert(0, "hello")
        for u in captured_a:
            await comm_a.send_to(bytes_data=create_update_message(u))

        # Let the channel layer propagate and apply on B's consumer.
        await asyncio.sleep(0.5)

        # Drain B's incoming SYNC_UPDATE so its local doc converges.
        received_any = False
        for _ in range(8):
            try:
                msg = await comm_b.receive_from(timeout=0.4)
            except asyncio.TimeoutError:
                break
            if not isinstance(msg, (bytes, bytearray)) or len(msg) < 2:
                continue
            raw = bytes(msg)
            if raw[0] != YMessageType.SYNC:
                continue
            try:
                handle_sync_message(raw[1:], doc_b)
                received_any = True
            except Exception:
                continue

        self.assertTrue(
            received_any,
            "Client B must receive at least one SYNC frame after A's insert",
        )
        self.assertEqual(
            str(doc_b.get("codemirror", type=Text)),
            "hello",
            "Client B's local doc must converge on the content A inserted",
        )

        await asyncio.gather(
            self._safe_disconnect(comm_a),
            self._safe_disconnect(comm_b),
        )
        await asyncio.sleep(0.5)

        await sync_to_async(sync_snapshot_with_page)(room_name)
        refreshed = await sync_to_async(Page.objects.get)(external_id=page.external_id)
        self.assertEqual(
            refreshed.details["content"],
            "hello",
            f"After the live edit, details.content must reflect the new content "
            f"(not the stale value); got {refreshed.details['content']!r}",
        )

    async def _safe_disconnect(self, comm):
        """Disconnect, tolerating CancelledError from the ASGI test harness."""
        try:
            await comm.disconnect()
        except (asyncio.CancelledError, Exception):
            pass
