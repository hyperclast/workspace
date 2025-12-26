"""
Test for empty/corrupted CRDT snapshot bug that causes WebSocket reconnection loops.

EVIDENCE FROM PRODUCTION DATABASE (2025-12-23):
===============================================

Corrupted snapshots (all 0x0000 = 2 bytes):
- page_NBgpLtb6Io: snapshot=0x0000, size=2, last_update_id=0
- page_vqenUt6ojs: snapshot=0x0000, size=2, last_update_id=0
- page_FpYHqYLork: snapshot=0x0000, size=2, last_update_id=0
- page_GCzvbGNy3n: snapshot=0x0000, size=2, last_update_id=0

All corrupted pages have:
- details.content = "" (empty string)
- No y_updates records
- last_update_id = 0

Working snapshots for comparison:
- page_rVddbhrsSG: size=100 bytes (has content)
- page_YxQKkAX8qB: size=1268 bytes (has content)
- page_8yKLfSRvdN: size=858 bytes (has content)

SYMPTOM:
========
WebSocket connects, server accepts, then immediately closes.
y-websocket client auto-reconnects, creating an infinite loop:

  INFO: connection open
  INFO: connection closed
  INFO: connection open
  INFO: connection closed
  ... (repeating every ~1 second)

ROOT CAUSE HYPOTHESIS:
=====================
1. Page created via API with empty content
2. User connects via WebSocket (or disconnect happens before sync completes)
3. On disconnect, _take_snapshot() saves doc.get_update() for empty doc
4. Empty doc returns 0x0000 (2 bytes)
5. Next connection: make_ydoc() tries to apply_update(0x0000)
6. This either fails or creates invalid state
7. Connection drops, client reconnects → infinite loop
"""

import asyncio

from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.test import TestCase, TransactionTestCase

from pycrdt import Doc, Text

from backend.asgi import application
from collab.models import YSnapshot
from pages.tests.factories import PageFactory, UserFactory


# ============================================================================
# PART 1: Document the corrupted data format
# ============================================================================


class TestCorruptedSnapshotFormat(TestCase):
    """Document what the corrupted data looks like."""

    # Actual corrupted snapshot from production
    CORRUPTED_SNAPSHOT_HEX = "0000"
    CORRUPTED_SNAPSHOT_BYTES = bytes.fromhex(CORRUPTED_SNAPSHOT_HEX)

    def test_corrupted_snapshot_is_two_null_bytes(self):
        """Verify the corrupted snapshot format."""
        self.assertEqual(self.CORRUPTED_SNAPSHOT_BYTES, b"\x00\x00")
        self.assertEqual(len(self.CORRUPTED_SNAPSHOT_BYTES), 2)

    def test_empty_doc_produces_two_null_bytes(self):
        """Verify that an empty pycrdt Doc produces the corrupted 0x0000 bytes."""
        doc = Doc()
        update = doc.get_update()

        # This is the root cause - empty doc produces 0x0000
        self.assertEqual(update, b"\x00\x00", f"Expected 0x0000, got {update.hex()}")
        self.assertEqual(len(update), 2)


# ============================================================================
# PART 2: Reproduce the bug - how we get into corrupted state
# ============================================================================


class TestHowCorruptedStateOccurs(TestCase):
    """Reproduce the sequence that creates corrupted snapshots."""

    def test_empty_doc_snapshot_can_be_applied(self):
        """
        When a page has no CRDT content and we take a snapshot,
        we get 0x0000. Test if applying it causes issues.
        """
        # 1. Create empty doc (simulates page with no content)
        doc = Doc()

        # 2. Get update (this is what _take_snapshot does)
        snapshot = doc.get_update()

        # 3. This produces the corrupted 0x0000
        self.assertEqual(snapshot, b"\x00\x00")

        # 4. Now try to apply it to a new doc (simulates next connection)
        new_doc = Doc()

        # This is what happens during hydration
        new_doc.apply_update(snapshot)

        # Check if we can still use the doc
        text = new_doc.get("codemirror", type=Text)
        text.insert(0, "test")

        content = str(text)
        self.assertEqual(content, "test", f"Doc state may be corrupted, got: {content}")

    def test_disconnect_before_content_creates_corrupted_snapshot(self):
        """
        Simulate the exact sequence:
        1. Page created with empty content
        2. User connects
        3. Disconnect happens before any real content is synced
        4. _take_snapshot() saves 0x0000
        """
        # Step 1: Empty doc (page just created, no CRDT data yet)
        doc = Doc()
        text = doc.get("codemirror", type=Text)  # Create the text type

        # Step 2: User "connects" - no actual sync happens
        # (In real scenario, disconnect happens before sync completes)

        # Step 3: Disconnect - _take_snapshot() is called
        snapshot = doc.get_update()

        # Step 4: This is the corrupted snapshot
        self.assertEqual(len(snapshot), 2, f"Expected 2-byte snapshot, got {len(snapshot)}")
        self.assertEqual(snapshot, b"\x00\x00")

    def test_page_with_content_produces_valid_snapshot(self):
        """Verify that a page WITH content produces a valid snapshot."""
        doc = Doc()
        text = doc.get("codemirror", type=Text)

        # Add some content
        text.insert(0, "Hello, World!")

        snapshot = doc.get_update()

        # Should be much larger than 2 bytes
        self.assertGreater(len(snapshot), 10, f"Expected larger snapshot, got {len(snapshot)} bytes")
        self.assertNotEqual(snapshot, b"\x00\x00")


# ============================================================================
# PART 3: Test the fix - snapshot validation
# ============================================================================


class TestSnapshotValidation(TestCase):
    """Test the fix: don't save empty/invalid snapshots."""

    @staticmethod
    def is_valid_snapshot(snapshot_bytes: bytes) -> bool:
        """
        Check if a snapshot is valid (not empty/corrupted).

        A valid Yjs/pycrdt snapshot should be larger than 2 bytes.
        The 0x0000 (2 bytes) represents an empty document state
        that should NOT be saved as a snapshot.
        """
        if not snapshot_bytes:
            return False
        if len(snapshot_bytes) <= 2:
            return False
        return True

    def test_corrupted_snapshot_detected_as_invalid(self):
        """Corrupted 0x0000 snapshots should be detected."""
        self.assertFalse(self.is_valid_snapshot(b"\x00\x00"))
        self.assertFalse(self.is_valid_snapshot(b"\x00"))
        self.assertFalse(self.is_valid_snapshot(b""))
        self.assertFalse(self.is_valid_snapshot(None))

    def test_valid_snapshot_passes_validation(self):
        """Valid snapshots should pass validation."""
        # Create a valid snapshot
        doc = Doc()
        text = doc.get("codemirror", type=Text)
        text.insert(0, "Some content")

        snapshot = doc.get_update()
        self.assertTrue(self.is_valid_snapshot(snapshot))

    def test_take_snapshot_should_skip_empty_docs(self):
        """
        The fix: _take_snapshot() should check if doc is empty
        and skip saving if so.
        """
        doc = Doc()
        _ = doc.get("codemirror", type=Text)

        snapshot = doc.get_update()

        # The fix: check before saving
        should_save = self.is_valid_snapshot(snapshot)

        # Verify we would skip saving empty snapshot
        self.assertFalse(should_save, "Empty snapshot should not be saved")


# ============================================================================
# PART 4: Test fixture data for manual reproduction
# ============================================================================


class TestFixtureData(TestCase):
    """
    Fixture data that can be used to manually reproduce the bug.

    To reproduce manually:
    1. Insert this data into y_snapshots table
    2. Try to connect to the page via WebSocket
    3. Observe the reconnection loop
    """

    CORRUPTED_PAGES = [
        {
            "room_id": "page_NBgpLtb6Io",
            "snapshot_hex": "0000",
            "snapshot_size": 2,
            "last_update_id": 0,
            "page_title": "Top 10 Food Experiences in Salerno woof woof woof woof meow",
        },
        {
            "room_id": "page_vqenUt6ojs",
            "snapshot_hex": "0000",
            "snapshot_size": 2,
            "last_update_id": 0,
            "page_title": "Top 10 Food Experiences in Salerno",
        },
        {
            "room_id": "page_FpYHqYLork",
            "snapshot_hex": "0000",
            "snapshot_size": 2,
            "last_update_id": 0,
            "page_title": "Top 10 Food Experiences in Salerno",
        },
        {
            "room_id": "page_GCzvbGNy3n",
            "snapshot_hex": "0000",
            "snapshot_size": 2,
            "last_update_id": 0,
            "page_title": "Italy",
        },
    ]

    SQL_TO_CREATE_CORRUPTED_SNAPSHOT = """
    -- Insert corrupted snapshot to reproduce the bug
    INSERT INTO y_snapshots (room_id, snapshot, last_update_id, timestamp)
    VALUES ('page_TEST123', E'\\\\x0000', 0, NOW())
    ON CONFLICT (room_id) DO UPDATE SET snapshot = E'\\\\x0000', last_update_id = 0;

    -- Verify it's corrupted
    SELECT room_id, length(snapshot), encode(snapshot, 'hex')
    FROM y_snapshots
    WHERE room_id = 'page_TEST123';
    """

    SQL_TO_FIX_CORRUPTED_SNAPSHOTS = """
    -- Delete corrupted snapshots (they will be recreated on next connect)
    DELETE FROM y_snapshots
    WHERE length(snapshot) <= 2;

    -- Verify
    SELECT COUNT(*) as remaining_corrupted
    FROM y_snapshots
    WHERE length(snapshot) <= 2;
    """

    def test_fixture_data_is_documented(self):
        """Ensure we have fixture data documented."""
        self.assertEqual(len(self.CORRUPTED_PAGES), 4)
        for page in self.CORRUPTED_PAGES:
            self.assertEqual(page["snapshot_hex"], "0000")
            self.assertEqual(page["snapshot_size"], 2)

    def test_sql_fixtures_are_documented(self):
        """Ensure SQL to reproduce is documented."""
        self.assertIn("INSERT INTO y_snapshots", self.SQL_TO_CREATE_CORRUPTED_SNAPSHOT)
        self.assertIn("DELETE FROM y_snapshots", self.SQL_TO_FIX_CORRUPTED_SNAPSHOTS)


# ============================================================================
# PART 5: Integration test - actually reproduce the WebSocket failure
# ============================================================================


class TestWebSocketWithCorruptedSnapshot(TransactionTestCase):
    """
    Integration test that reproduces the actual WebSocket reconnection loop bug.

    This test:
    1. Creates a page
    2. Inserts a corrupted 0x0000 snapshot for that page
    3. Attempts to connect via WebSocket
    4. Verifies the connection behavior
    """

    async def test_websocket_with_corrupted_snapshot(self):
        """
        Reproduce the bug: WebSocket connection with corrupted 0x0000 snapshot.

        Expected behavior (current bug): Connection opens then closes quickly.
        Expected behavior (after fix): Connection should handle gracefully.
        """
        # Step 1: Create a user and page
        user = await sync_to_async(UserFactory.create)()
        page = await sync_to_async(PageFactory.create)(creator=user)

        room_id = f"page_{page.external_id}"

        # Step 2: Insert the corrupted snapshot (0x0000)
        corrupted_snapshot = b"\x00\x00"
        await sync_to_async(YSnapshot.objects.create)(
            room_id=room_id,
            snapshot=corrupted_snapshot,
            last_update_id=0,
        )

        # Verify the snapshot was inserted
        snapshot = await sync_to_async(YSnapshot.objects.get)(room_id=room_id)
        self.assertEqual(len(snapshot.snapshot), 2)
        self.assertEqual(snapshot.snapshot, corrupted_snapshot)

        # Step 3: Attempt WebSocket connection
        comm = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm.scope["user"] = user

        # Step 4: Connect and observe behavior
        connected, _ = await comm.connect()

        # The connection should initially succeed (server accepts)
        self.assertTrue(connected, "WebSocket should initially accept connection")

        # Collect ALL messages the server sends
        messages = []
        try:
            for _ in range(10):  # Collect up to 10 messages
                message = await asyncio.wait_for(comm.receive_output(), timeout=0.5)
                messages.append(message)
        except asyncio.TimeoutError:
            pass  # No more messages
        except Exception as e:
            print(f"Error receiving: {type(e).__name__}: {e}")

        # Try to disconnect cleanly
        try:
            await comm.disconnect()
        except Exception:
            pass  # May already be closed

        # Document the observed behavior
        print(f"\n=== Corrupted Snapshot Test Results ===")
        print(f"Page ID: {page.external_id}")
        print(f"Room ID: {room_id}")
        print(f"Snapshot size: {len(corrupted_snapshot)} bytes")
        print(f"Snapshot hex: {corrupted_snapshot.hex()}")
        print(f"Connection accepted: {connected}")
        print(f"Messages received: {len(messages)}")
        for i, msg in enumerate(messages):
            if isinstance(msg, bytes):
                print(f"  Message {i}: {len(msg)} bytes, hex={msg[:20].hex()}...")
            else:
                print(f"  Message {i}: {type(msg).__name__} = {msg}")

        # For now, just document the behavior - the actual assertion
        # depends on what behavior we observe
        # After the fix, we'd assert that the connection stays stable

    async def test_websocket_with_valid_snapshot_works(self):
        """
        Control test: WebSocket connection with valid snapshot works correctly.
        """
        # Step 1: Create a user and page
        user = await sync_to_async(UserFactory.create)()
        page = await sync_to_async(PageFactory.create)(creator=user)

        room_id = f"page_{page.external_id}"

        # Step 2: Create a valid snapshot with actual content
        doc = Doc()
        text = doc.get("codemirror", type=Text)
        text.insert(0, "Hello, World!")
        valid_snapshot = doc.get_update()

        await sync_to_async(YSnapshot.objects.create)(
            room_id=room_id,
            snapshot=valid_snapshot,
            last_update_id=0,
        )

        # Verify the snapshot was inserted
        snapshot = await sync_to_async(YSnapshot.objects.get)(room_id=room_id)
        self.assertGreater(len(snapshot.snapshot), 10)

        # Step 3: Attempt WebSocket connection
        comm = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm.scope["user"] = user

        # Step 4: Connect and verify it works
        connected, _ = await comm.connect()
        self.assertTrue(connected, "WebSocket should accept connection")

        # Collect ALL messages the server sends
        messages = []
        try:
            for _ in range(10):  # Collect up to 10 messages
                message = await asyncio.wait_for(comm.receive_output(), timeout=0.5)
                messages.append(message)
        except asyncio.TimeoutError:
            pass  # No more messages
        except Exception as e:
            print(f"Error receiving: {type(e).__name__}: {e}")

        await comm.disconnect()

        print(f"\n=== Valid Snapshot Test Results ===")
        print(f"Snapshot size: {len(valid_snapshot)} bytes")
        print(f"Snapshot hex: {valid_snapshot.hex()}")
        print(f"Connection accepted: {connected}")
        print(f"Messages received: {len(messages)}")
        for i, msg in enumerate(messages):
            if isinstance(msg, bytes):
                print(f"  Message {i}: {len(msg)} bytes, hex={msg[:20].hex()}...")
            else:
                print(f"  Message {i}: {type(msg).__name__} = {msg}")

        # Valid snapshot should work
        self.assertTrue(connected)
