"""
Tests for document hydration via make_ydoc().

The make_ydoc() function in consumers.py is responsible for building a Yjs Doc
and hydrating it from persisted storage. It has two hydration paths:

1. Snapshot + Incremental (Fast Path):
   - Load snapshot (single operation)
   - Apply only updates since the snapshot via read_since()
   - Expected speedup: 10-20x for documents with 100+ edits

2. Full Replay (Slow Path / Fallback):
   - Load ALL updates from the beginning via read()
   - Apply each update sequentially
   - Used when no snapshot exists or snapshot is invalid

These tests verify:
- Correct hydration path selection
- Invalid/empty snapshot handling (<=2 bytes triggers fallback)
- Proper application of incremental updates
- Document state after hydration
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase
from pycrdt import Doc, Text

from backend.asgi import application
from collab.models import YUpdate
from collab.tests import (
    create_page_with_access,
    create_user_with_org_and_project,
)


class AsyncIteratorMock:
    """Mock async iterator that yields no updates."""

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise StopAsyncIteration


class AsyncIteratorWithUpdates:
    """Mock async iterator that yields updates from a list."""

    def __init__(self, updates):
        self.updates = list(updates)
        self.index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index >= len(self.updates):
            raise StopAsyncIteration
        result = self.updates[self.index]
        self.index += 1
        return result


def create_doc_with_content(content: str) -> Doc:
    """Create a Yjs Doc with text content in the 'codemirror' key."""
    doc = Doc()
    text = doc.get("codemirror", type=Text)
    text.insert(0, content)
    return doc


def create_update_bytes(content: str) -> bytes:
    """Create update bytes for a document with the given content."""
    doc = create_doc_with_content(content)
    return doc.get_update()


def create_incremental_update(base_doc: Doc, additional_content: str) -> bytes:
    """
    Create an incremental update by adding content to a doc.
    Returns only the delta (new update bytes).
    """
    text = base_doc.get("codemirror", type=Text)
    # Get current state
    state_before = base_doc.get_state()
    # Add content
    text.insert(len(str(text)), additional_content)
    # Get only the new update
    return base_doc.get_update(state_before)


class FakeYStore:
    """
    Fake YStore for testing hydration paths.

    Supports configuring:
    - initial_updates: List of (update_bytes, meta, ts) for read()
    - snapshot_data: Tuple of (snapshot_bytes, last_update_id) for get_snapshot()
    - incremental_updates: List of (update_bytes, meta, ts, id) for read_since()
    """

    def __init__(
        self,
        initial_updates=None,
        snapshot_data=None,
        incremental_updates=None,
    ):
        self.initialize_pool = AsyncMock()
        self.write = AsyncMock()
        self.upsert_snapshot = AsyncMock()
        self.get_max_update_id = AsyncMock(return_value=0)
        self.close_pool = AsyncMock()
        self.delete_updates_before_snapshot = AsyncMock(return_value=0)

        self._initial_updates = initial_updates or []
        self._snapshot_data = snapshot_data
        self._incremental_updates = incremental_updates or []

        # Configure get_snapshot mock
        self.get_snapshot = AsyncMock(return_value=self._snapshot_data)

        # Track which path was used for assertions
        self.read_called = False
        self.read_since_called = False
        self.read_since_last_id = None

    def read(self, *args, **kwargs):
        """Return async iterator for all updates (full replay path)."""
        self.read_called = True
        if self._initial_updates:
            return AsyncIteratorWithUpdates(self._initial_updates)
        return AsyncIteratorMock()

    def read_since(self, last_inclusive_id: int):
        """Return async iterator for incremental updates (snapshot path)."""
        self.read_since_called = True
        self.read_since_last_id = last_inclusive_id
        if self._incremental_updates:
            return AsyncIteratorWithUpdates(self._incremental_updates)
        return AsyncIteratorMock()


class TestHydrationPathSelection(TransactionTestCase):
    """Tests for selecting the correct hydration path."""

    @patch("collab.consumers.PostgresYStore")
    async def test_uses_snapshot_path_when_valid_snapshot_exists(self, MockYStore):
        """
        When a valid snapshot exists (> 2 bytes), hydration should use
        the snapshot + read_since() path.
        """
        # Create a valid snapshot (more than 2 bytes)
        snapshot_bytes = create_update_bytes("Hello, World!")
        self.assertGreater(len(snapshot_bytes), 2, "Snapshot should be > 2 bytes")

        # Setup fake ystore with valid snapshot
        mock_ystore = FakeYStore(
            snapshot_data=(snapshot_bytes, 100),  # snapshot up to update ID 100
            incremental_updates=[],  # no incremental updates
        )
        MockYStore.return_value = mock_ystore

        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project)

        comm = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm.scope["user"] = user

        await comm.connect()
        await asyncio.sleep(0.3)
        await comm.disconnect()

        # Verify snapshot path was used
        self.assertTrue(
            mock_ystore.read_since_called,
            "read_since() should be called when valid snapshot exists",
        )
        self.assertFalse(
            mock_ystore.read_called,
            "read() should NOT be called when valid snapshot exists",
        )
        self.assertEqual(
            mock_ystore.read_since_last_id,
            100,
            "read_since() should be called with the snapshot's last_update_id",
        )

    @patch("collab.consumers.PostgresYStore")
    async def test_uses_full_replay_when_no_snapshot_exists(self, MockYStore):
        """
        When no snapshot exists, hydration should use the full replay
        path via read().
        """
        initial_update = create_update_bytes("Initial content")

        # Setup fake ystore with no snapshot
        mock_ystore = FakeYStore(
            initial_updates=[(initial_update, b"", 1234567890.0)],
            snapshot_data=None,  # No snapshot
        )
        MockYStore.return_value = mock_ystore

        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project)

        comm = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm.scope["user"] = user

        await comm.connect()
        await asyncio.sleep(0.3)
        await comm.disconnect()

        # Verify full replay path was used
        self.assertTrue(
            mock_ystore.read_called,
            "read() should be called when no snapshot exists",
        )
        self.assertFalse(
            mock_ystore.read_since_called,
            "read_since() should NOT be called when no snapshot exists",
        )


class TestInvalidSnapshotHandling(TransactionTestCase):
    """Tests for handling invalid/empty snapshots."""

    @patch("collab.consumers.PostgresYStore")
    async def test_falls_back_to_full_replay_for_empty_snapshot(self, MockYStore):
        """
        When snapshot is empty (0 bytes), hydration should fall back
        to full replay path.
        """
        initial_update = create_update_bytes("Fallback content")

        # Setup fake ystore with empty snapshot
        mock_ystore = FakeYStore(
            initial_updates=[(initial_update, b"", 1234567890.0)],
            snapshot_data=(b"", 50),  # Empty snapshot (0 bytes)
        )
        MockYStore.return_value = mock_ystore

        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project)

        comm = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm.scope["user"] = user

        await comm.connect()
        await asyncio.sleep(0.3)
        await comm.disconnect()

        # Verify fallback to full replay
        self.assertTrue(
            mock_ystore.read_called,
            "read() should be called when snapshot is empty",
        )
        self.assertFalse(
            mock_ystore.read_since_called,
            "read_since() should NOT be called when snapshot is empty",
        )

    @patch("collab.consumers.PostgresYStore")
    async def test_falls_back_to_full_replay_for_corrupted_2byte_snapshot(self, MockYStore):
        """
        When snapshot is exactly 2 bytes (0x0000 - corrupted empty doc),
        hydration should fall back to full replay path.

        This is a known bug prevention: empty Yjs docs produce 0x0000 (2 bytes)
        which causes client reconnection loops if loaded as a snapshot.
        """
        initial_update = create_update_bytes("Real content")

        # Setup fake ystore with corrupted 2-byte snapshot
        mock_ystore = FakeYStore(
            initial_updates=[(initial_update, b"", 1234567890.0)],
            snapshot_data=(b"\x00\x00", 50),  # Corrupted 2-byte snapshot
        )
        MockYStore.return_value = mock_ystore

        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project)

        comm = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm.scope["user"] = user

        await comm.connect()
        await asyncio.sleep(0.3)
        await comm.disconnect()

        # Verify fallback to full replay
        self.assertTrue(
            mock_ystore.read_called,
            "read() should be called when snapshot is corrupted (2 bytes)",
        )
        self.assertFalse(
            mock_ystore.read_since_called,
            "read_since() should NOT be called when snapshot is corrupted",
        )

    @patch("collab.consumers.PostgresYStore")
    async def test_falls_back_to_full_replay_for_1byte_snapshot(self, MockYStore):
        """
        When snapshot is 1 byte, hydration should fall back to full replay.
        """
        initial_update = create_update_bytes("Content after 1-byte snapshot")

        mock_ystore = FakeYStore(
            initial_updates=[(initial_update, b"", 1234567890.0)],
            snapshot_data=(b"\x00", 25),  # 1-byte invalid snapshot
        )
        MockYStore.return_value = mock_ystore

        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project)

        comm = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm.scope["user"] = user

        await comm.connect()
        await asyncio.sleep(0.3)
        await comm.disconnect()

        # Verify fallback to full replay
        self.assertTrue(
            mock_ystore.read_called,
            "read() should be called when snapshot is 1 byte",
        )


class TestSnapshotWithIncrementalUpdates(TransactionTestCase):
    """Tests for hydration using snapshot + incremental updates."""

    @patch("collab.consumers.PostgresYStore")
    async def test_applies_incremental_updates_after_snapshot(self, MockYStore):
        """
        After loading snapshot, hydration should apply incremental
        updates via read_since().
        """
        # Create base doc with initial content
        base_doc = create_doc_with_content("Initial snapshot content. ")
        snapshot_bytes = base_doc.get_update()

        # Create incremental update (adding more content)
        incremental_update = create_incremental_update(base_doc, "More content added later.")

        # Setup fake ystore
        mock_ystore = FakeYStore(
            snapshot_data=(snapshot_bytes, 100),
            incremental_updates=[
                (incremental_update, b"", 1234567890.0, 101),  # update ID 101 (> 100)
            ],
        )
        MockYStore.return_value = mock_ystore

        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project)

        comm = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm.scope["user"] = user

        await comm.connect()
        await asyncio.sleep(0.3)
        await comm.disconnect()

        # Verify snapshot path was used with incremental updates
        self.assertTrue(mock_ystore.read_since_called)
        self.assertEqual(mock_ystore.read_since_last_id, 100)
        self.assertFalse(mock_ystore.read_called)

    @patch("collab.consumers.PostgresYStore")
    async def test_applies_multiple_incremental_updates(self, MockYStore):
        """
        Hydration should apply all incremental updates after the snapshot.
        """
        # Create base doc
        base_doc = create_doc_with_content("Base. ")
        snapshot_bytes = base_doc.get_update()

        # Create multiple incremental updates
        update1 = create_incremental_update(base_doc, "First addition. ")
        update2 = create_incremental_update(base_doc, "Second addition. ")
        update3 = create_incremental_update(base_doc, "Third addition.")

        # Setup fake ystore with multiple incremental updates
        mock_ystore = FakeYStore(
            snapshot_data=(snapshot_bytes, 50),
            incremental_updates=[
                (update1, b"", 1234567891.0, 51),
                (update2, b"", 1234567892.0, 52),
                (update3, b"", 1234567893.0, 53),
            ],
        )
        MockYStore.return_value = mock_ystore

        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project)

        comm = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm.scope["user"] = user

        await comm.connect()
        await asyncio.sleep(0.3)
        await comm.disconnect()

        # Verify snapshot path was used
        self.assertTrue(mock_ystore.read_since_called)
        self.assertEqual(mock_ystore.read_since_last_id, 50)


class TestFullReplayPath(TransactionTestCase):
    """Tests for the full replay hydration path."""

    @patch("collab.consumers.PostgresYStore")
    async def test_applies_all_updates_in_order(self, MockYStore):
        """
        Full replay should apply all updates from the beginning in order.
        """
        # Create multiple updates
        doc = Doc()
        text = doc.get("codemirror", type=Text)

        updates = []
        for i, content in enumerate(["First. ", "Second. ", "Third."]):
            state_before = doc.get_state()
            text.insert(len(str(text)), content)
            update_bytes = doc.get_update(state_before)
            updates.append((update_bytes, b"", 1234567890.0 + i))

        # Setup fake ystore with no snapshot
        mock_ystore = FakeYStore(
            initial_updates=updates,
            snapshot_data=None,
        )
        MockYStore.return_value = mock_ystore

        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project)

        comm = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm.scope["user"] = user

        await comm.connect()
        await asyncio.sleep(0.3)
        await comm.disconnect()

        # Verify full replay path was used
        self.assertTrue(mock_ystore.read_called)
        self.assertFalse(mock_ystore.read_since_called)

    @patch("collab.consumers.PostgresYStore")
    async def test_handles_empty_update_list(self, MockYStore):
        """
        Full replay with no updates should result in an empty document.
        """
        # Setup fake ystore with no updates and no snapshot
        mock_ystore = FakeYStore(
            initial_updates=[],
            snapshot_data=None,
        )
        MockYStore.return_value = mock_ystore

        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project)

        comm = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm.scope["user"] = user

        await comm.connect()
        await asyncio.sleep(0.3)
        await comm.disconnect()

        # Should complete without errors
        self.assertTrue(mock_ystore.read_called)


class TestSnapshotOnlyPath(TransactionTestCase):
    """Tests for hydration with snapshot but no incremental updates."""

    @patch("collab.consumers.PostgresYStore")
    async def test_snapshot_only_no_incremental_updates(self, MockYStore):
        """
        When snapshot exists but no incremental updates exist,
        hydration should succeed with just the snapshot.
        """
        snapshot_bytes = create_update_bytes("Complete snapshot content")

        mock_ystore = FakeYStore(
            snapshot_data=(snapshot_bytes, 200),
            incremental_updates=[],  # No updates after snapshot
        )
        MockYStore.return_value = mock_ystore

        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project)

        comm = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm.scope["user"] = user

        await comm.connect()
        await asyncio.sleep(0.3)
        await comm.disconnect()

        # Verify snapshot path was used
        self.assertTrue(mock_ystore.read_since_called)
        self.assertEqual(mock_ystore.read_since_last_id, 200)
        self.assertFalse(mock_ystore.read_called)


class TestHydrationEdgeCases(TransactionTestCase):
    """Edge case tests for hydration."""

    @patch("collab.consumers.PostgresYStore")
    async def test_handles_large_snapshot(self, MockYStore):
        """
        Hydration should handle large snapshots (simulating a document
        with extensive content).
        """
        # Create a large document
        large_content = "x" * 100000  # 100KB of content
        snapshot_bytes = create_update_bytes(large_content)

        mock_ystore = FakeYStore(
            snapshot_data=(snapshot_bytes, 500),
            incremental_updates=[],
        )
        MockYStore.return_value = mock_ystore

        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project)

        comm = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm.scope["user"] = user

        await comm.connect()
        await asyncio.sleep(0.5)
        await comm.disconnect()

        # Should complete without errors
        self.assertTrue(mock_ystore.read_since_called)

    @patch("collab.consumers.PostgresYStore")
    async def test_handles_many_incremental_updates(self, MockYStore):
        """
        Hydration should handle many incremental updates after a snapshot.
        """
        base_doc = create_doc_with_content("Base content. ")
        snapshot_bytes = base_doc.get_update()

        # Create many incremental updates
        incremental_updates = []
        for i in range(100):
            update = create_incremental_update(base_doc, f"Update {i}. ")
            incremental_updates.append((update, b"", 1234567890.0 + i, 10 + i))

        mock_ystore = FakeYStore(
            snapshot_data=(snapshot_bytes, 10),
            incremental_updates=incremental_updates,
        )
        MockYStore.return_value = mock_ystore

        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project)

        comm = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm.scope["user"] = user

        await comm.connect()
        await asyncio.sleep(0.5)
        await comm.disconnect()

        # Should complete without errors
        self.assertTrue(mock_ystore.read_since_called)
        self.assertEqual(mock_ystore.read_since_last_id, 10)

    @patch("collab.consumers.PostgresYStore")
    async def test_snapshot_with_exactly_3_bytes_is_valid(self, MockYStore):
        """
        A snapshot with exactly 3 bytes should be considered valid
        (threshold is <= 2 bytes for invalid).
        """
        # 3-byte snapshot should be valid
        three_byte_snapshot = b"\x00\x00\x00"

        mock_ystore = FakeYStore(
            snapshot_data=(three_byte_snapshot, 5),
            incremental_updates=[],
        )
        MockYStore.return_value = mock_ystore

        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project)

        comm = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm.scope["user"] = user

        await comm.connect()
        await asyncio.sleep(0.3)
        await comm.disconnect()

        # 3-byte snapshot should use snapshot path (valid)
        self.assertTrue(
            mock_ystore.read_since_called,
            "3-byte snapshot should be considered valid",
        )
        self.assertFalse(mock_ystore.read_called)


class TestMakeYdocSeedWiring(TransactionTestCase):
    """Tests that `make_ydoc()` calls the seed helper exactly when the
    room has no usable Yjs state and the page row has seedable content.

    The helper itself is exercised in `test_seed_ydoc.py`; here we only
    verify the wiring inside `make_ydoc()` so the seed-once invariant
    holds end-to-end from a real WebSocket connect.

    Assertions look at the real `y_updates` table (not the mocked
    ystore). The seed path writes through the Django ORM under an
    advisory transaction lock, so the persisted row is observable via
    `YUpdate.objects.filter(...)` regardless of how `PostgresYStore` is
    mocked for the hydration read path.
    """

    SEED_CONTENT = "content1234"

    async def _yupdate_rows(self, room_id):
        rows = await sync_to_async(list)(
            YUpdate.objects.filter(room_id=room_id).order_by("id").values_list("yupdate", flat=True)
        )
        return [bytes(b) for b in rows]

    @patch("collab.consumers.PostgresYStore")
    async def test_seeds_when_no_snapshot_and_no_updates(self, MockYStore):
        """Empty store + non-empty Page.details["content"] → seed fires."""
        mock_ystore = FakeYStore(initial_updates=[], snapshot_data=None)
        MockYStore.return_value = mock_ystore

        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project, details={"content": self.SEED_CONTENT})

        comm = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm.scope["user"] = user

        await comm.connect()
        await asyncio.sleep(0.3)
        await comm.disconnect()

        self.assertTrue(mock_ystore.read_called)

        rows = await self._yupdate_rows(f"page_{page.external_id}")
        self.assertEqual(len(rows), 1, "seed must persist exactly one y_updates row")

        replay = Doc()
        replay.apply_update(rows[0])
        self.assertEqual(
            str(replay.get("codemirror", type=Text)),
            self.SEED_CONTENT,
            "persisted seed must round-trip back to the page content",
        )

    @patch("collab.consumers.PostgresYStore")
    async def test_seeds_when_corrupt_snapshot_and_no_updates(self, MockYStore):
        """A 2-byte snapshot falls through to full replay; with an empty
        update log, the seed branch must still fire."""
        mock_ystore = FakeYStore(
            initial_updates=[],
            snapshot_data=(b"\x00\x00", 50),
        )
        MockYStore.return_value = mock_ystore

        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project, details={"content": self.SEED_CONTENT})

        comm = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm.scope["user"] = user

        await comm.connect()
        await asyncio.sleep(0.3)
        await comm.disconnect()

        self.assertTrue(mock_ystore.read_called)

        rows = await self._yupdate_rows(f"page_{page.external_id}")
        self.assertEqual(len(rows), 1)

        replay = Doc()
        replay.apply_update(rows[0])
        self.assertEqual(str(replay.get("codemirror", type=Text)), self.SEED_CONTENT)

    @patch("collab.consumers.PostgresYStore")
    async def test_does_not_seed_when_content_empty(self, MockYStore):
        """Empty `details.content` is the precondition we must not seed under."""
        mock_ystore = FakeYStore(initial_updates=[], snapshot_data=None)
        MockYStore.return_value = mock_ystore

        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project, details={"content": ""})

        comm = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm.scope["user"] = user

        await comm.connect()
        await asyncio.sleep(0.3)
        await comm.disconnect()

        self.assertTrue(mock_ystore.read_called)
        rows = await self._yupdate_rows(f"page_{page.external_id}")
        self.assertEqual(rows, [])

    @patch("collab.consumers.PostgresYStore")
    async def test_does_not_seed_when_valid_snapshot_present(self, MockYStore):
        """A real snapshot is the source of truth — never seed over it,
        even when the page row still carries legacy `details.content`."""
        snapshot_bytes = create_update_bytes("snapshot is truth")
        self.assertGreater(len(snapshot_bytes), 2)

        mock_ystore = FakeYStore(
            snapshot_data=(snapshot_bytes, 100),
            incremental_updates=[],
        )
        MockYStore.return_value = mock_ystore

        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project, details={"content": self.SEED_CONTENT})

        comm = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm.scope["user"] = user

        await comm.connect()
        await asyncio.sleep(0.3)
        await comm.disconnect()

        self.assertTrue(mock_ystore.read_since_called)
        self.assertFalse(mock_ystore.read_called)
        rows = await self._yupdate_rows(f"page_{page.external_id}")
        self.assertEqual(rows, [])

    @patch("collab.consumers.PostgresYStore")
    async def test_does_not_seed_when_updates_exist(self, MockYStore):
        """If any y_updates row exists, hydration replays it; seeding would
        double the content (the same race the seed fixes)."""
        existing = create_update_bytes("already in y_updates")
        mock_ystore = FakeYStore(
            initial_updates=[(existing, b"", 1234567890.0)],
            snapshot_data=None,
        )
        MockYStore.return_value = mock_ystore

        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project, details={"content": self.SEED_CONTENT})

        comm = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm.scope["user"] = user

        await comm.connect()
        await asyncio.sleep(0.3)
        await comm.disconnect()

        self.assertTrue(mock_ystore.read_called)
        # The FakeYStore reports one update via `read()`, so make_ydoc
        # sees update_count == 1 and skips the seed branch entirely. No
        # real y_updates row should be written.
        rows = await self._yupdate_rows(f"page_{page.external_id}")
        self.assertEqual(rows, [])


class TestMakeYdocSeedFailureFailOpen(TransactionTestCase):
    """Pin the intentional fail-open behavior when `_seed_ydoc_from_page`
    returns False for a non-empty page.

    `_seed_ydoc_from_page` catches its own write/read errors and returns
    `False` so a transient DB hiccup does not break the WebSocket
    connect. The consumer must therefore accept the connection and hand
    the client an empty `Doc`. The user briefly sees the REST-rendered
    body before the WS sync resolves; once it does, the editor upgrades
    to a collaborative-but-empty doc — a regression from the user's
    point of view, but a *recoverable* one because no `y_updates` row
    was written. The next opener (or a reload by this user) re-enters
    `make_ydoc` with the room still empty and retries the seed cleanly.

    Erasing `details.content` here would turn that transient failure
    into permanent data loss, which is why the reconcile helper is
    `y_updates`-gated (see `_reconcile_empty_page_content`).

    This test pins both halves of the contract: the connection still
    succeeds, and no `y_updates` row is written.
    """

    SEED_CONTENT = "content1234"

    async def _yupdate_rows(self, room_id):
        rows = await sync_to_async(list)(
            YUpdate.objects.filter(room_id=room_id).order_by("id").values_list("yupdate", flat=True)
        )
        return [bytes(b) for b in rows]

    @patch(
        "collab.consumers.PageYjsConsumer._seed_ydoc_from_page",
        new_callable=AsyncMock,
        return_value=False,
    )
    @patch("collab.consumers.PostgresYStore")
    async def test_connection_accepted_when_seed_returns_false(self, MockYStore, mock_seed):
        """Seed helper returning False is the fail-open path: connection
        accepted, no y_updates row written, hydrated doc stays empty."""
        mock_ystore = FakeYStore(initial_updates=[], snapshot_data=None)
        MockYStore.return_value = mock_ystore

        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project, details={"content": self.SEED_CONTENT})

        comm = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm.scope["user"] = user

        connected, _ = await comm.connect()
        self.assertTrue(
            connected,
            "Consumer must still accept the WS connection when the seed helper fails",
        )

        await asyncio.sleep(0.3)
        await comm.disconnect()

        self.assertTrue(mock_seed.called, "make_ydoc must call the seed helper")
        rows = await self._yupdate_rows(f"page_{page.external_id}")
        self.assertEqual(
            rows,
            [],
            "Failed seed must not write a partial y_updates row — the next opener retries",
        )
