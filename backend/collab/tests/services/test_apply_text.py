"""
Tests for collab.services.apply_text.

Covers hydration from ystore (empty / snapshot / incremental updates),
each apply mode (overwrite / append / prepend), no-op cases, persistence
of captured Yjs updates, permission re-check at execution time, and
channel-layer broadcast.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from pycrdt import Doc, Text

from collab.locks import SEED_LOCK_NAMESPACE, advisory_lock_key_for_room
from collab.models import YSnapshot, YUpdate
from collab.services.apply_text import ApplyResult, apply_text_to_room
from collab.tasks import apply_text_update_to_page

# Arbitrary user id for tests that mock out the permission check. Tests
# that exercise the real `can_edit_page` path use real User/Page fixtures.
TEST_USER_ID = 42


def _doc_with_text(content: str) -> bytes:
    """Return Yjs update bytes for a doc whose `codemirror` ytext == content."""
    doc = Doc()
    ytext = Text()
    doc["codemirror"] = ytext
    if content:
        ytext += content
    return doc.get_update()


def _replay_room(room_id: str) -> str:
    """Rebuild the CRDT state from the DB and return its text content."""
    doc = Doc()
    snapshot = YSnapshot.objects.filter(room_id=room_id).first()
    if snapshot is not None and len(bytes(snapshot.snapshot)) > 2:
        doc.apply_update(bytes(snapshot.snapshot))
        updates_qs = YUpdate.objects.filter(room_id=room_id, id__gt=snapshot.last_update_id).order_by("id")
    else:
        updates_qs = YUpdate.objects.filter(room_id=room_id).order_by("id")
    for update_bytes in updates_qs.values_list("yupdate", flat=True):
        doc.apply_update(bytes(update_bytes))
    ytext = doc.get("codemirror", type=Text)
    return str(ytext) if ytext else ""


@patch("collab.services.apply_text.can_edit_page", new_callable=lambda: AsyncMock(return_value=True))
@patch("collab.services.apply_text.get_channel_layer")
class TestApplyTextToRoomOverwrite(TestCase):
    def test_overwrite_empty_store(self, mocked_channel_layer, _mocked_can_edit):
        mocked_channel_layer.return_value = MagicMock()
        room_id = "page_abc"

        result = apply_text_to_room(room_id, "Hello", TEST_USER_ID, mode="overwrite")

        self.assertEqual(result, ApplyResult.APPLIED)
        self.assertEqual(_replay_room(room_id), "Hello")
        self.assertTrue(YUpdate.objects.filter(room_id=room_id).exists())

    def test_overwrite_replaces_snapshot_content(self, mocked_channel_layer, _mocked_can_edit):
        mocked_channel_layer.return_value = MagicMock()
        room_id = "page_abc"
        YSnapshot.objects.create(
            room_id=room_id,
            snapshot=_doc_with_text("original"),
            last_update_id=0,
        )

        result = apply_text_to_room(room_id, "replacement", TEST_USER_ID, mode="overwrite")

        self.assertEqual(result, ApplyResult.APPLIED)
        self.assertEqual(_replay_room(room_id), "replacement")

    def test_overwrite_replaces_update_only_content(self, mocked_channel_layer, _mocked_can_edit):
        """Hydrates from y_updates when no snapshot exists."""
        mocked_channel_layer.return_value = MagicMock()
        room_id = "page_abc"

        # Seed y_updates by running an overwrite first.
        apply_text_to_room(room_id, "seed", TEST_USER_ID, mode="overwrite")
        self.assertEqual(_replay_room(room_id), "seed")

        result = apply_text_to_room(room_id, "fresh", TEST_USER_ID, mode="overwrite")

        self.assertEqual(result, ApplyResult.APPLIED)
        self.assertEqual(_replay_room(room_id), "fresh")

    def test_overwrite_with_identical_content_is_noop(self, mocked_channel_layer, _mocked_can_edit):
        mocked_channel_layer.return_value = MagicMock()
        room_id = "page_abc"
        YSnapshot.objects.create(
            room_id=room_id,
            snapshot=_doc_with_text("same"),
            last_update_id=0,
        )

        result = apply_text_to_room(room_id, "same", TEST_USER_ID, mode="overwrite")

        self.assertEqual(result, ApplyResult.NOOP)
        self.assertFalse(YUpdate.objects.filter(room_id=room_id).exists())

    def test_overwrite_with_empty_clears_content(self, mocked_channel_layer, _mocked_can_edit):
        mocked_channel_layer.return_value = MagicMock()
        room_id = "page_abc"
        YSnapshot.objects.create(
            room_id=room_id,
            snapshot=_doc_with_text("to be cleared"),
            last_update_id=0,
        )

        result = apply_text_to_room(room_id, "", TEST_USER_ID, mode="overwrite")

        self.assertEqual(result, ApplyResult.APPLIED)
        self.assertEqual(_replay_room(room_id), "")


@patch("collab.services.apply_text.can_edit_page", new_callable=lambda: AsyncMock(return_value=True))
@patch("collab.services.apply_text.get_channel_layer")
class TestApplyTextToRoomAppendPrepend(TestCase):
    def test_append_extends_existing_content(self, mocked_channel_layer, _mocked_can_edit):
        mocked_channel_layer.return_value = MagicMock()
        room_id = "page_abc"
        YSnapshot.objects.create(
            room_id=room_id,
            snapshot=_doc_with_text("start"),
            last_update_id=0,
        )

        result = apply_text_to_room(room_id, " end", TEST_USER_ID, mode="append")

        self.assertEqual(result, ApplyResult.APPLIED)
        self.assertEqual(_replay_room(room_id), "start end")

    def test_prepend_adds_to_start(self, mocked_channel_layer, _mocked_can_edit):
        mocked_channel_layer.return_value = MagicMock()
        room_id = "page_abc"
        YSnapshot.objects.create(
            room_id=room_id,
            snapshot=_doc_with_text("end"),
            last_update_id=0,
        )

        result = apply_text_to_room(room_id, "start ", TEST_USER_ID, mode="prepend")

        self.assertEqual(result, ApplyResult.APPLIED)
        self.assertEqual(_replay_room(room_id), "start end")

    def test_append_empty_is_noop(self, mocked_channel_layer, _mocked_can_edit):
        mocked_channel_layer.return_value = MagicMock()
        room_id = "page_abc"
        YSnapshot.objects.create(
            room_id=room_id,
            snapshot=_doc_with_text("keep"),
            last_update_id=0,
        )

        result = apply_text_to_room(room_id, "", TEST_USER_ID, mode="append")

        self.assertEqual(result, ApplyResult.NOOP)
        self.assertFalse(YUpdate.objects.filter(room_id=room_id).exists())

    def test_prepend_empty_is_noop(self, mocked_channel_layer, _mocked_can_edit):
        mocked_channel_layer.return_value = MagicMock()
        room_id = "page_abc"
        YSnapshot.objects.create(
            room_id=room_id,
            snapshot=_doc_with_text("keep"),
            last_update_id=0,
        )

        result = apply_text_to_room(room_id, "", TEST_USER_ID, mode="prepend")

        self.assertEqual(result, ApplyResult.NOOP)
        self.assertFalse(YUpdate.objects.filter(room_id=room_id).exists())

    def test_invalid_mode_raises(self, mocked_channel_layer, _mocked_can_edit):
        mocked_channel_layer.return_value = MagicMock()
        with self.assertRaises(ValueError):
            apply_text_to_room("page_abc", "x", TEST_USER_ID, mode="bogus")


@patch("collab.services.apply_text.can_edit_page", new_callable=lambda: AsyncMock(return_value=True))
@patch("collab.services.apply_text.async_to_sync")
@patch("collab.services.apply_text.get_channel_layer")
class TestApplyTextToRoomBroadcast(TestCase):
    def test_broadcast_called_with_external_update_type(
        self, mocked_channel_layer, mocked_async_to_sync, _mocked_can_edit
    ):
        """Broadcast uses the external_update channel type (not send_message).

        The consumer's external_update handler applies to self.ydoc AND
        forwards to client; send_message would only forward, causing
        snapshot drift. See apply_text.py module docstring.
        """
        channel_layer = MagicMock()
        mocked_channel_layer.return_value = channel_layer
        group_send_wrapper = MagicMock()
        # `async_to_sync` is used for BOTH the permission check and the
        # group_send. Return the mock for group_send; the permission path
        # goes through the separately-patched `can_edit_page`.
        mocked_async_to_sync.return_value = group_send_wrapper

        room_id = "page_abc"
        with self.captureOnCommitCallbacks(execute=True):
            apply_text_to_room(room_id, "hi", TEST_USER_ID, mode="overwrite")

        self.assertTrue(group_send_wrapper.called)
        # Find the group_send call for the external_update (async_to_sync
        # is also called with can_edit_page, so we filter).
        external_update_calls = [
            call_args
            for call_args in group_send_wrapper.call_args_list
            if len(call_args.args) == 2
            and isinstance(call_args.args[1], dict)
            and call_args.args[1].get("type") == "external_update"
        ]
        self.assertEqual(len(external_update_calls), 1)
        sent_room_id, payload = external_update_calls[0].args
        self.assertEqual(sent_room_id, room_id)
        self.assertEqual(payload["type"], "external_update")
        self.assertIsInstance(payload["update"], bytes)

    def test_no_broadcast_on_noop(self, mocked_channel_layer, mocked_async_to_sync, _mocked_can_edit):
        channel_layer = MagicMock()
        mocked_channel_layer.return_value = channel_layer
        group_send_wrapper = MagicMock()
        mocked_async_to_sync.return_value = group_send_wrapper

        room_id = "page_abc"
        YSnapshot.objects.create(
            room_id=room_id,
            snapshot=_doc_with_text("same"),
            last_update_id=0,
        )

        with self.captureOnCommitCallbacks(execute=True):
            apply_text_to_room(room_id, "same", TEST_USER_ID, mode="overwrite")

        # group_send is wrapped via async_to_sync. The no-op path should not
        # have produced any call that looks like a group_send with a payload.
        external_update_calls = [
            call_args
            for call_args in group_send_wrapper.call_args_list
            if len(call_args.args) == 2
            and isinstance(call_args.args[1], dict)
            and call_args.args[1].get("type") == "external_update"
        ]
        self.assertEqual(len(external_update_calls), 0)

    def test_no_broadcast_when_channel_layer_missing(
        self, mocked_channel_layer, mocked_async_to_sync, _mocked_can_edit
    ):
        mocked_channel_layer.return_value = None
        group_send_wrapper = MagicMock()
        mocked_async_to_sync.return_value = group_send_wrapper

        with self.captureOnCommitCallbacks(execute=True):
            result = apply_text_to_room("page_abc", "hi", TEST_USER_ID, mode="overwrite")

        self.assertEqual(result, ApplyResult.APPLIED)
        external_update_calls = [
            call_args
            for call_args in group_send_wrapper.call_args_list
            if len(call_args.args) == 2
            and isinstance(call_args.args[1], dict)
            and call_args.args[1].get("type") == "external_update"
        ]
        self.assertEqual(len(external_update_calls), 0)

    def test_broadcast_fires_only_after_commit(self, mocked_channel_layer, mocked_async_to_sync, _mocked_can_edit):
        """Regression guard: broadcast must not fire before DB commit.

        If the broadcast fires before the y_updates row is visible to
        reconnecting peers, a peer that hydrates between broadcast and
        commit would miss the update.
        """
        channel_layer = MagicMock()
        mocked_channel_layer.return_value = channel_layer
        group_send_wrapper = MagicMock()
        mocked_async_to_sync.return_value = group_send_wrapper

        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            apply_text_to_room("page_abc", "hi", TEST_USER_ID, mode="overwrite")
            # Before running the callbacks, no external_update broadcast.
            external_update_calls = [
                call_args
                for call_args in group_send_wrapper.call_args_list
                if len(call_args.args) == 2
                and isinstance(call_args.args[1], dict)
                and call_args.args[1].get("type") == "external_update"
            ]
            self.assertEqual(len(external_update_calls), 0)

        # Callback was queued on_commit (so in prod it would run after commit).
        self.assertEqual(len(callbacks), 1)


@patch("collab.services.apply_text.get_channel_layer")
class TestApplyTextToRoomPermissionRecheck(TestCase):
    """Regression: permission is re-checked at execution time.

    Enqueue verified write access, but between enqueue and execute the
    user can lose access (revoked org membership, downgraded role,
    removed as editor). Without the execution-time re-check the write
    would still land.
    """

    @patch(
        "collab.services.apply_text.can_edit_page",
        new_callable=lambda: AsyncMock(return_value=False),
    )
    def test_denied_when_user_lost_edit_access(self, _mocked_can_edit, mocked_channel_layer):
        mocked_channel_layer.return_value = MagicMock()
        room_id = "page_abc"

        result = apply_text_to_room(room_id, "should not land", TEST_USER_ID, mode="overwrite")

        # DENIED is distinct from NOOP — the task wrapper logs them
        # separately so dashboards can chart revocation churn.
        self.assertEqual(result, ApplyResult.DENIED)
        self.assertFalse(YUpdate.objects.filter(room_id=room_id).exists())

    @patch(
        "collab.services.apply_text.can_edit_page",
        new_callable=lambda: AsyncMock(return_value=True),
    )
    def test_allowed_when_user_still_has_edit_access(self, _mocked_can_edit, mocked_channel_layer):
        mocked_channel_layer.return_value = MagicMock()
        room_id = "page_abc"

        result = apply_text_to_room(room_id, "lands", TEST_USER_ID, mode="overwrite")

        self.assertEqual(result, ApplyResult.APPLIED)
        self.assertTrue(YUpdate.objects.filter(room_id=room_id).exists())


@patch("collab.services.apply_text.can_edit_page", new_callable=lambda: AsyncMock(return_value=True))
@patch("collab.services.apply_text.get_channel_layer")
class TestApplyTextToRoomConcurrency(TestCase):
    """CRDT-merge sanity: concurrent typing + external write must not corrupt state.

    `apply_text_to_room` re-hydrates from the persisted store, not from a
    connected consumer's in-memory ydoc, so it can compute its mutation
    against a base that's already stale relative to a typing user. The
    CRDT property guarantees no corruption — both edits merge into a
    consistent final state — but ordering is unspecified. These tests
    prove the non-corrupting property end-to-end against the real
    persistence layer.
    """

    @staticmethod
    def _seed_room(room_id: str, content: str) -> bytes:
        """Persist a snapshot for `room_id` containing `content` and return its bytes."""
        seed_doc = Doc()
        seed_text = seed_doc.get("codemirror", type=Text)
        seed_text.insert(0, content)
        snapshot_bytes = seed_doc.get_update()
        YSnapshot.objects.create(
            room_id=room_id,
            snapshot=snapshot_bytes,
            last_update_id=0,
        )
        return snapshot_bytes

    @staticmethod
    def _capture_browser_typing(snapshot_bytes: bytes, position: int, text: str) -> list[bytes]:
        """Hydrate a fresh doc from `snapshot_bytes`, type, and return captured updates."""
        browser_doc = Doc()
        browser_doc.apply_update(snapshot_bytes)
        browser_text = browser_doc.get("codemirror", type=Text)
        captured: list[bytes] = []

        def _capture(event):
            update = getattr(event, "update", None)
            if update:
                captured.append(bytes(update))

        browser_doc.observe(_capture)
        browser_text.insert(position, text)
        return captured

    def test_browser_typing_then_external_append_merges_cleanly(self, mocked_channel_layer, _mocked_can_edit):
        """Browser persists a local edit before MCP fires.

        apply_text_to_room hydrates from snapshot + the browser's already-
        persisted update, sees the typed state, and appends after it.
        """
        mocked_channel_layer.return_value = MagicMock()
        room_id = "page_concurrent_a"
        snapshot_bytes = self._seed_room(room_id, "hello")

        browser_updates = self._capture_browser_typing(snapshot_bytes, len("hello"), " typed")
        YUpdate.objects.bulk_create([YUpdate(room_id=room_id, yupdate=u) for u in browser_updates])

        result = apply_text_to_room(room_id, " from MCP", TEST_USER_ID, mode="append")

        self.assertEqual(result, ApplyResult.APPLIED)
        final = _replay_room(room_id)
        self.assertEqual(final, "hello typed from MCP")

    def test_external_append_against_stale_base_then_browser_typing_preserves_both(
        self, mocked_channel_layer, _mocked_can_edit
    ):
        """Two writers operate against the same stale base.

        Models the timing window the design accepts: MCP reads the
        store while the browser has unpersisted edits. The CRDT must
        preserve both edits without corruption when both updates land
        in y_updates.
        """
        mocked_channel_layer.return_value = MagicMock()
        room_id = "page_concurrent_b"
        snapshot_bytes = self._seed_room(room_id, "hello")

        # Browser hydrates and types, but its update has not been persisted yet.
        browser_updates = self._capture_browser_typing(snapshot_bytes, len("hello"), " typed")

        # MCP fires NOW, against the same "hello" base — its update is
        # computed before the browser's update reaches y_updates.
        result = apply_text_to_room(room_id, " from MCP", TEST_USER_ID, mode="append")
        self.assertEqual(result, ApplyResult.APPLIED)

        # Browser's edit is then persisted, after MCP's row is already in.
        YUpdate.objects.bulk_create([YUpdate(room_id=room_id, yupdate=u) for u in browser_updates])

        # Final replay must contain both edits. The CRDT may interleave the
        # two insertions in either order; assert non-corruption + presence.
        final = _replay_room(room_id)
        self.assertIn("hello", final)
        self.assertIn("typed", final)
        self.assertIn("from MCP", final)
        self.assertEqual(
            len(final),
            len("hello") + len(" typed") + len(" from MCP"),
            f"Final length must match sum of all inserted text — corruption detected: {final!r}",
        )

    def test_concurrent_external_appends_both_land(self, mocked_channel_layer, _mocked_can_edit):
        """Two MCP appends against the same base both land without loss.

        Each apply_text_to_room call independently hydrates from the store,
        computes its mutation, and persists. The store has no per-room
        mutex, so two concurrent calls compute against the same base; the
        CRDT must still preserve both writes.
        """
        mocked_channel_layer.return_value = MagicMock()
        room_id = "page_concurrent_c"
        self._seed_room(room_id, "base")

        first = apply_text_to_room(room_id, " A", TEST_USER_ID, mode="append")
        # Second call hydrates from snapshot + the first call's row,
        # so it sees "base A" — but the assertion below holds regardless
        # of ordering because we only check presence and non-corruption.
        second = apply_text_to_room(room_id, " B", TEST_USER_ID, mode="append")

        self.assertEqual(first, ApplyResult.APPLIED)
        self.assertEqual(second, ApplyResult.APPLIED)
        final = _replay_room(room_id)
        self.assertIn("base", final)
        self.assertIn("A", final)
        self.assertIn("B", final)
        self.assertEqual(
            len(final),
            len("base") + len(" A") + len(" B"),
            f"Final length must match sum of all inserted text — corruption detected: {final!r}",
        )


@patch("collab.services.apply_text.can_edit_page", new_callable=lambda: AsyncMock(return_value=True))
@patch("collab.services.apply_text.get_channel_layer")
class TestApplyTextToRoomLocking(TestCase):
    """Regression: apply_text_to_room must serialize with the WS seed path.

    Without the per-room advisory lock, a REST/MCP write racing a fresh
    WebSocket connection on an empty room can each insert the same content
    with different Yjs clientIDs, producing doubled text after CRDT merge.
    The lock collapses the race to a clean winner/loser ordering.
    """

    def test_advisory_lock_sql_is_executed(self, mocked_channel_layer, _mocked_can_edit):
        mocked_channel_layer.return_value = MagicMock()
        room_id = "page_lock_sql"

        with CaptureQueriesContext(connection) as ctx:
            apply_text_to_room(room_id, "hello", TEST_USER_ID, mode="overwrite")

        lock_queries = [q["sql"] for q in ctx.captured_queries if "pg_advisory_xact_lock" in q["sql"]]
        self.assertEqual(
            len(lock_queries),
            1,
            f"Expected exactly one pg_advisory_xact_lock call, got: {lock_queries}",
        )

    def test_lock_is_acquired_before_hydration_read(self, mocked_channel_layer, _mocked_can_edit):
        """The lock must precede the y_updates read; otherwise the loser's
        in-lock recheck would see stale state."""
        mocked_channel_layer.return_value = MagicMock()
        room_id = "page_lock_order"

        with CaptureQueriesContext(connection) as ctx:
            apply_text_to_room(room_id, "hello", TEST_USER_ID, mode="overwrite")

        lock_index = next(
            (i for i, q in enumerate(ctx.captured_queries) if "pg_advisory_xact_lock" in q["sql"]),
            None,
        )
        y_updates_read_index = next(
            (
                i
                for i, q in enumerate(ctx.captured_queries)
                if "y_updates" in q["sql"] and q["sql"].lstrip().upper().startswith("SELECT")
            ),
            None,
        )
        self.assertIsNotNone(lock_index, "advisory lock query was not issued")
        self.assertIsNotNone(y_updates_read_index, "no SELECT against y_updates was issued")
        self.assertLess(
            lock_index,
            y_updates_read_index,
            "Advisory lock must be acquired before reading y_updates",
        )

    @patch("collab.services.apply_text.advisory_lock_key_for_room")
    def test_lock_key_is_derived_from_room_id(self, mocked_key_helper, mocked_channel_layer, _mocked_can_edit):
        """The same room_id must produce the same lock key as the seed
        path, otherwise the two writers would not actually serialize."""
        mocked_channel_layer.return_value = MagicMock()
        # Returning a stable int proves the helper output is the lock key.
        mocked_key_helper.return_value = 123456789
        room_id = "page_lock_key"

        apply_text_to_room(room_id, "hello", TEST_USER_ID, mode="overwrite")

        mocked_key_helper.assert_called_with(room_id)

    def test_lock_key_matches_seed_path_for_same_room(self, mocked_channel_layer, _mocked_can_edit):
        """End-to-end check: the SQL parameter passed to pg_advisory_xact_lock
        equals advisory_lock_key_for_room(room_id) (and SEED_LOCK_NAMESPACE).
        Drift here would re-open the race that this lock exists to close.
        """
        mocked_channel_layer.return_value = MagicMock()
        room_id = "page_lock_match"
        expected_key = advisory_lock_key_for_room(room_id)

        with CaptureQueriesContext(connection) as ctx:
            apply_text_to_room(room_id, "hello", TEST_USER_ID, mode="overwrite")

        lock_queries = [q["sql"] for q in ctx.captured_queries if "pg_advisory_xact_lock" in q["sql"]]
        self.assertEqual(len(lock_queries), 1)
        sql = lock_queries[0]
        # Django's CaptureQueriesContext substitutes parameters into the SQL
        # string, so both values appear inline. We assert on substring presence
        # rather than exact form to stay resilient to driver formatting.
        self.assertIn(str(SEED_LOCK_NAMESPACE), sql)
        self.assertIn(str(expected_key), sql)

    def test_lock_acquired_and_released_on_noop(self, mocked_channel_layer, _mocked_can_edit):
        """Even on the no-op path the lock must be acquired (otherwise the
        in-lock recheck of current content is racy) and the surrounding
        transaction must commit so the lock auto-releases.
        """
        mocked_channel_layer.return_value = MagicMock()
        room_id = "page_lock_noop"
        YSnapshot.objects.create(
            room_id=room_id,
            snapshot=_doc_with_text("same"),
            last_update_id=0,
        )

        with CaptureQueriesContext(connection) as ctx:
            result = apply_text_to_room(room_id, "same", TEST_USER_ID, mode="overwrite")

        self.assertEqual(result, ApplyResult.NOOP)
        lock_queries = [q["sql"] for q in ctx.captured_queries if "pg_advisory_xact_lock" in q["sql"]]
        self.assertEqual(len(lock_queries), 1)


class TestApplyTextUpdateToPageTask(TestCase):
    @patch("collab.tasks.apply_text_to_room")
    def test_task_routes_to_apply_text_to_room(self, mocked_apply):
        mocked_apply.return_value = ApplyResult.APPLIED

        apply_text_update_to_page("abc123", "new content", user_id=TEST_USER_ID, mode="overwrite")

        mocked_apply.assert_called_once_with("page_abc123", "new content", TEST_USER_ID, "overwrite")

    @patch("collab.tasks.apply_text_to_room")
    def test_task_propagates_exceptions(self, mocked_apply):
        """The task must NOT swallow exceptions — RQ relies on them to mark
        the job failed for retry / dead-letter handling. A swallowed error
        means recurring failures are invisible in queue dashboards.
        """
        mocked_apply.side_effect = RuntimeError("boom")

        with self.assertRaises(RuntimeError):
            apply_text_update_to_page("abc123", "new content", user_id=TEST_USER_ID, mode="append")

        mocked_apply.assert_called_once()

    @patch("collab.tasks.log_info")
    @patch("collab.tasks.apply_text_to_room")
    def test_task_logs_applied_result(self, mocked_apply, mocked_log):
        mocked_apply.return_value = ApplyResult.APPLIED

        apply_text_update_to_page("abc123", "new content", user_id=TEST_USER_ID, mode="overwrite")

        log_messages = [c.args[0] for c in mocked_log.call_args_list]
        self.assertTrue(
            any("mcp_text_update result=applied" in msg for msg in log_messages),
            f"Expected applied log line, got: {log_messages}",
        )

    @patch("collab.tasks.log_info")
    @patch("collab.tasks.apply_text_to_room")
    def test_task_logs_noop_result(self, mocked_apply, mocked_log):
        mocked_apply.return_value = ApplyResult.NOOP

        apply_text_update_to_page("abc123", "same", user_id=TEST_USER_ID, mode="overwrite")

        log_messages = [c.args[0] for c in mocked_log.call_args_list]
        self.assertTrue(
            any("mcp_text_update result=noop" in msg for msg in log_messages),
            f"Expected noop log line, got: {log_messages}",
        )

    @patch("collab.tasks.log_info")
    @patch("collab.tasks.apply_text_to_room")
    def test_task_logs_denied_result(self, mocked_apply, mocked_log):
        """Denial is logged distinctly from no-op so dashboards can split
        revocation churn (DENIED) from steady-state idempotent calls (NOOP).
        """
        mocked_apply.return_value = ApplyResult.DENIED

        apply_text_update_to_page("abc123", "denied content", user_id=TEST_USER_ID, mode="append")

        log_messages = [c.args[0] for c in mocked_log.call_args_list]
        self.assertTrue(
            any("mcp_text_update result=denied" in msg for msg in log_messages),
            f"Expected denied log line, got: {log_messages}",
        )
