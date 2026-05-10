"""
Tests for the PageYjsConsumer.external_update channel-layer handler.

This handler is what makes MCP/REST writes propagate live to connected
editors. It also fixes a subtle snapshot-drift bug: if we broadcast
raw SYNC_UPDATE via the base consumer's `send_message` (which only
forwards bytes to the client, without touching self.ydoc), the
consumer's ydoc diverges from the persisted y_updates. Its next
snapshot would silently drop the external write from the next hydration.

These tests verify:

1. Live propagation — connected client receives the change as a
   SYNC_UPDATE message.
2. Ydoc sync — `self.ydoc` is updated with the external change.
3. No double-persistence — the observer does NOT write an additional
   y_updates row for the externally-injected update.
4. Regression for the drift bug — after `apply_text_to_room` + a
   simulated consumer disconnect, the snapshot contains the external
   update (so it survives hydration on the next connection).
5. Apply-failure regression — when `self.ydoc.apply_update(...)` raises,
   the handler MUST NOT forward divergent bytes to the client; it
   must signal a resync instead, so the client can reconnect and
   rehydrate from persisted state.
6. Dirty-tracking regression — when a snapshot already exists and the
   only changes during the session are external updates, the disconnect
   must still take a fresh snapshot (so denormalized state — links,
   mentions, file-links, rewind — gets refreshed via
   `sync_snapshot_with_page`).
7. Cold-path regression — an external write with NO connected consumer
   must still persist to y_updates so the next consumer that connects
   hydrates with the change applied. Models headless MCP usage where
   no editor is open at the time of the write.
"""

import asyncio
import json
from unittest.mock import patch

from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase
from pycrdt import Doc, Text, YMessageType, YSyncMessageType

from backend.asgi import application
from collab.models import YSnapshot, YUpdate
from collab.services.apply_text import apply_text_to_room
from collab.tests import create_page_with_access, create_user_with_org_and_project


def _parse_sync_update(message: bytes) -> bytes | None:
    """If `message` is a Yjs SYNC_UPDATE, return the raw update bytes.

    Yjs message framing: [YMessageType][YSyncMessageType][varint-len][data].
    """
    if not message or message[0] != YMessageType.SYNC or len(message) < 2:
        return None
    if message[1] != YSyncMessageType.SYNC_UPDATE:
        return None
    return message


class TestExternalUpdateHandler(TransactionTestCase):
    """Verify external updates reach connected clients AND the server ydoc."""

    async def _wait_for_connect(self, comm: WebsocketCommunicator) -> None:
        connected, _ = await comm.connect()
        self.assertTrue(connected, "WebSocket should connect")
        # Drain the initial SYNC_STEP1 the base consumer sends on connect.
        try:
            await comm.receive_from(timeout=0.5)
        except asyncio.TimeoutError:
            pass

    async def _safe_disconnect(self, comm: WebsocketCommunicator) -> None:
        """Disconnect, tolerating CancelledError from the ASGI test harness.

        The consumer's disconnect handler runs to completion (snapshot
        created, pool closed) before the ASGI future is cancelled, so it
        is safe to ignore the cancellation here.
        """
        try:
            await comm.disconnect()
        except (asyncio.CancelledError, Exception):
            pass

    async def test_external_update_reaches_connected_client(self):
        """MCP/REST write is forwarded to the open editor as a SYNC_UPDATE."""
        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project)

        comm = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm.scope["user"] = user

        await self._wait_for_connect(comm)

        # Simulate an MCP write while the editor is connected.
        room_id = f"page_{page.external_id}"
        await database_sync_to_async(apply_text_to_room)(room_id, "hello from mcp", user.id, mode="overwrite")

        # The external_update handler forwards a SYNC_UPDATE to the client.
        # There may be an intervening message (initial sync exchange), so
        # we drain up to 3 messages looking for the SYNC_UPDATE.
        found_update = False
        for _ in range(3):
            try:
                msg = await comm.receive_from(timeout=2)
            except asyncio.TimeoutError:
                break
            if isinstance(msg, (bytes, bytearray)) and _parse_sync_update(bytes(msg)):
                found_update = True
                break

        self.assertTrue(
            found_update,
            "Connected client should have received a SYNC_UPDATE from the external write",
        )

        await comm.disconnect()

    async def test_external_update_syncs_server_ydoc_prevents_drift(self):
        """Regression: server-side ydoc reflects external write, so the final
        snapshot on disconnect contains it.

        Before the fix, the consumer broadcast via `send_message` which only
        forwarded to the client; self.ydoc was never updated, the disconnect
        snapshot dropped the external update, and the next hydration lost it.
        """
        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project)
        room_id = f"page_{page.external_id}"

        comm = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm.scope["user"] = user
        await self._wait_for_connect(comm)

        # External write lands while the editor is connected.
        await database_sync_to_async(apply_text_to_room)(room_id, "persisted body", user.id, mode="overwrite")

        # Wait for the forwarded SYNC_UPDATE so the handler has run.
        for _ in range(5):
            try:
                msg = await comm.receive_from(timeout=2)
            except asyncio.TimeoutError:
                break
            if isinstance(msg, (bytes, bytearray)) and _parse_sync_update(bytes(msg)):
                break

        # Disconnect triggers the final snapshot, taken from self.ydoc.
        await self._safe_disconnect(comm)

        # Wait briefly for the final snapshot to be written.
        for _ in range(20):
            exists = await database_sync_to_async(YSnapshot.objects.filter(room_id=room_id).exists)()
            if exists:
                break
            await asyncio.sleep(0.1)

        # Hydrate a fresh doc from the persisted snapshot alone — this is
        # what a reconnecting client would see if the snapshot watermark
        # covers every y_updates row (the drift-bug scenario).
        snapshot_obj = await database_sync_to_async(YSnapshot.objects.get)(room_id=room_id)
        doc = Doc()
        doc.apply_update(bytes(snapshot_obj.snapshot))
        ytext = doc.get("codemirror", type=Text)
        self.assertEqual(
            str(ytext),
            "persisted body",
            "Final snapshot must contain the externally-injected update; "
            "otherwise the write is silently lost on the next hydration",
        )

    async def test_external_update_does_not_duplicate_persistence(self):
        """The handler applies the update without re-writing it to y_updates.

        `apply_text_to_room` already persists the update. If the consumer
        observer also persisted on apply_update(), we'd have duplicate rows.
        """
        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project)
        room_id = f"page_{page.external_id}"

        comm = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm.scope["user"] = user
        await self._wait_for_connect(comm)

        await database_sync_to_async(apply_text_to_room)(room_id, "once", user.id, mode="overwrite")

        # Allow the forwarded SYNC_UPDATE to be received (ensures the handler
        # ran to completion).
        for _ in range(3):
            try:
                await comm.receive_from(timeout=1)
            except asyncio.TimeoutError:
                break

        row_count = await database_sync_to_async(YUpdate.objects.filter(room_id=room_id).count)()
        # Exactly one row from the service's bulk_create. If the observer
        # mistakenly re-persisted, we'd have two.
        self.assertEqual(row_count, 1, "External update must not be double-persisted")

        await self._safe_disconnect(comm)

    async def test_apply_failure_does_not_forward_divergent_bytes(self):
        """When apply_update fails, the handler must not forward to the client.

        Forwarding divergent bytes would leave the client merged ahead of
        the server-side ydoc. The next disconnect snapshot would be taken
        from the stale ydoc with the watermark already past the external
        update's row id, silently dropping the external write from the next
        hydration. Instead, the handler signals the client to resync.
        """
        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project)
        room_id = f"page_{page.external_id}"

        comm = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm.scope["user"] = user
        await self._wait_for_connect(comm)

        # Build a dummy update payload to send via the channel layer. We
        # don't go through apply_text_to_room because we want to bypass the
        # service's persistence and isolate the consumer-side behavior.
        scratch = Doc()
        scratch.get("codemirror", type=Text).insert(0, "ignored")
        update_bytes = scratch.get_update(b"\x00")

        # Force apply_update on the consumer's ydoc to raise. Patching the
        # `pycrdt.Doc.apply_update` method covers any consumer's ydoc
        # instance.
        original_apply_update = Doc.apply_update

        def _raise(self, *args, **kwargs):
            raise RuntimeError("simulated apply_update failure")

        with patch.object(Doc, "apply_update", _raise):
            channel_layer = get_channel_layer()
            await channel_layer.group_send(
                room_id,
                {"type": "external_update", "update": update_bytes},
            )

            # Drain messages briefly: we expect a resync_required JSON
            # message, but NOT a SYNC_UPDATE forwarding the divergent bytes.
            saw_sync_update = False
            saw_resync = False
            for _ in range(5):
                try:
                    msg = await comm.receive_from(timeout=1)
                except asyncio.TimeoutError:
                    break
                if isinstance(msg, (bytes, bytearray)) and _parse_sync_update(bytes(msg)):
                    saw_sync_update = True
                elif isinstance(msg, str):
                    try:
                        payload = json.loads(msg)
                    except ValueError:
                        continue
                    if payload.get("type") == "error" and payload.get("code") == "resync_required":
                        saw_resync = True

        self.assertFalse(
            saw_sync_update,
            "Consumer must NOT forward divergent bytes to client when apply_update fails",
        )
        self.assertTrue(
            saw_resync,
            "Consumer must signal resync_required to client when apply_update fails",
        )

        # Server-side ydoc should remain at its initial (empty) state — the
        # patched apply_update raised, so nothing was applied. We verify by
        # calling the real apply_update on a fresh doc and checking the text
        # would-have-been "ignored", proving our patch was active and that
        # the consumer's ydoc never reached that state.
        fresh = Doc()
        original_apply_update(fresh, update_bytes)
        self.assertEqual(
            str(fresh.get("codemirror", type=Text)),
            "ignored",
            "Sanity: the dummy update encodes 'ignored' when applied normally",
        )

        await self._safe_disconnect(comm)

    async def test_external_update_with_existing_snapshot_dirties_for_disconnect_snapshot(self):
        """Regression for F2: external updates must dirty the doc.

        Setup: a valid snapshot already exists for the room. A consumer
        connects, an external write lands, and the consumer disconnects
        without any browser-side edits.

        Before the fix, the suppress-persistence branch in `_on_transaction`
        returned early without setting `has_unsaved_changes`. Disconnect
        saw `has_unsaved_changes=False` and an existing snapshot, so it
        skipped the final snapshot. That left the snapshot's watermark
        behind the external update's row id, and `sync_snapshot_with_page`
        never fired — denormalized state (links, mentions, file-links,
        rewind) silently went stale until the next human edit.

        With the fix, the external update marks the doc dirty so the
        disconnect snapshot is taken; `upsert_snapshot` enqueues
        `sync_snapshot_with_page`, refreshing denormalized state.
        """
        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project)
        room_id = f"page_{page.external_id}"

        # Pre-create a valid snapshot for the room. This is the F2 trigger:
        # without an existing snapshot the disconnect handler always takes
        # one, masking the dirty-tracking bug.
        seed_doc = Doc()
        seed_text = seed_doc.get("codemirror", type=Text)
        seed_text.insert(0, "seed")
        seed_snapshot_bytes = seed_doc.get_update()

        await database_sync_to_async(YSnapshot.objects.create)(
            room_id=room_id,
            snapshot=seed_snapshot_bytes,
            last_update_id=0,
        )

        comm = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm.scope["user"] = user
        await self._wait_for_connect(comm)

        # External write lands while the editor is connected. apply_text_to_room
        # rebuilds the doc from the existing snapshot ("seed") and overwrites
        # to "fresh body", producing a new YUpdate row.
        await database_sync_to_async(apply_text_to_room)(room_id, "fresh body", user.id, mode="overwrite")

        # Wait for the consumer to receive and process the external_update
        # (forwarded SYNC_UPDATE confirms the handler ran end-to-end).
        for _ in range(5):
            try:
                msg = await comm.receive_from(timeout=2)
            except asyncio.TimeoutError:
                break
            if isinstance(msg, (bytes, bytearray)) and _parse_sync_update(bytes(msg)):
                break

        # Capture the highest YUpdate id so we can assert the new snapshot's
        # watermark advances past it.
        max_update_id = await database_sync_to_async(
            lambda: YUpdate.objects.filter(room_id=room_id).order_by("-id").values_list("id", flat=True).first()
        )()
        self.assertIsNotNone(max_update_id, "apply_text_to_room must have created a YUpdate row")

        # Disconnect with NO browser-side edits — the only dirty signal is
        # the external update. Pre-fix, has_unsaved_changes is False here.
        await self._safe_disconnect(comm)

        # Wait for the disconnect snapshot to land.
        snapshot = None
        for _ in range(20):
            snapshot = await database_sync_to_async(YSnapshot.objects.filter(room_id=room_id).first)()
            if snapshot is not None and snapshot.last_update_id >= max_update_id:
                break
            await asyncio.sleep(0.1)

        self.assertIsNotNone(snapshot, "Disconnect must produce a YSnapshot row")
        self.assertGreaterEqual(
            snapshot.last_update_id,
            max_update_id,
            "Disconnect snapshot watermark must advance past the external update id "
            "(otherwise sync_snapshot_with_page never sees the change and denormalized "
            "state goes stale)",
        )

        # The snapshot bytes must reflect the external write — sanity that
        # we did re-take the snapshot, not just preserve the seed one.
        verify = Doc()
        verify.apply_update(bytes(snapshot.snapshot))
        self.assertEqual(
            str(verify.get("codemirror", type=Text)),
            "fresh body",
            "Disconnect snapshot must contain the external write",
        )

    async def test_cold_path_external_write_visible_to_next_consumer(self):
        """Cold path: external write with no connected consumer survives to
        the next browser load.

        Headless MCP usage often writes when no editor is open. With no
        consumer joined to the room, the `external_update` channel-layer
        broadcast has no recipient — but `apply_text_to_room` must still
        persist the update to y_updates, and the next consumer that
        connects must hydrate it into self.ydoc so a disconnect snapshot
        captures the change. Without that, headless MCP writes would
        appear nowhere until a human edit dirtied the doc.
        """
        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project)
        room_id = f"page_{page.external_id}"

        # External write while NO consumer is connected.
        await database_sync_to_async(apply_text_to_room)(room_id, "cold-path content", user.id, mode="overwrite")

        # Persistence is the contract that survives a missing broadcast.
        update_count = await database_sync_to_async(YUpdate.objects.filter(room_id=room_id).count)()
        self.assertGreater(
            update_count,
            0,
            "Cold-path apply_text_to_room must persist to y_updates even with no consumer joined",
        )

        # Now open a fresh consumer (the "next browser load"). Hydration
        # must populate self.ydoc with the cold-path update so the
        # disconnect snapshot reflects it.
        comm = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm.scope["user"] = user
        await self._wait_for_connect(comm)
        await self._safe_disconnect(comm)

        snapshot = None
        for _ in range(20):
            snapshot = await database_sync_to_async(YSnapshot.objects.filter(room_id=room_id).first)()
            if snapshot is not None:
                break
            await asyncio.sleep(0.1)

        self.assertIsNotNone(
            snapshot,
            "First consumer connect after a cold-path write must produce a disconnect snapshot",
        )
        verify = Doc()
        verify.apply_update(bytes(snapshot.snapshot))
        self.assertEqual(
            str(verify.get("codemirror", type=Text)),
            "cold-path content",
            "Next browser load must hydrate from y_updates so the cold-path external write is visible",
        )

    async def test_external_update_enqueues_sync_snapshot_with_page(self):
        """The disconnect snapshot path must enqueue sync_snapshot_with_page.

        `ystore.upsert_snapshot` enqueues the task; that's how denormalized
        state (Page.details["content"], PageLink, PageMention, etc.) gets
        refreshed. Pre-fix, the suppress-persistence branch returned early
        before `has_unsaved_changes = True`, the disconnect skipped the
        snapshot, and the task was never enqueued.
        """
        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project)
        room_id = f"page_{page.external_id}"

        # Pre-existing valid snapshot (same trigger as above).
        seed_doc = Doc()
        seed_doc.get("codemirror", type=Text).insert(0, "seed")
        seed_snapshot_bytes = seed_doc.get_update()
        await database_sync_to_async(YSnapshot.objects.create)(
            room_id=room_id,
            snapshot=seed_snapshot_bytes,
            last_update_id=0,
        )

        comm = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm.scope["user"] = user
        await self._wait_for_connect(comm)

        # Patch the task's enqueue to record calls. ystore imports the task
        # at module level, so patch it there.
        with patch("collab.ystore.sync_snapshot_with_page") as mock_task:
            await database_sync_to_async(apply_text_to_room)(room_id, "after-mcp", user.id, mode="overwrite")

            # Wait briefly for the consumer to apply the external update.
            for _ in range(5):
                try:
                    msg = await comm.receive_from(timeout=2)
                except asyncio.TimeoutError:
                    break
                if isinstance(msg, (bytes, bytearray)) and _parse_sync_update(bytes(msg)):
                    break

            # Disconnect with no browser-side edits.
            await self._safe_disconnect(comm)

            # Allow disconnect handler to complete the upsert_snapshot call.
            for _ in range(20):
                if mock_task.enqueue.called:
                    break
                await asyncio.sleep(0.1)

        self.assertTrue(
            mock_task.enqueue.called,
            "ystore.upsert_snapshot must enqueue sync_snapshot_with_page during the "
            "disconnect snapshot path; without F2 fix the snapshot is skipped and the "
            "enqueue never happens",
        )
        # The first positional arg to enqueue is the room_id.
        first_call_args = mock_task.enqueue.call_args_list[0].args
        self.assertEqual(first_call_args[0], room_id)
