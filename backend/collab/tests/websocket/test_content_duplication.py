"""
Tests for content duplication scenarios.

The duplication issue was a FRONTEND problem where:
1. Client times out waiting for WebSocket sync
2. Client inserts REST API content into local ytext
3. WebSocket eventually connects and syncs
4. CRDT merges both (different operation IDs) → duplication

The fix is on the frontend: don't insert content locally before sync completes.
If sync times out, editor starts empty and shows content when sync succeeds.

These tests verify the backend CRDT behavior:
- CRDT correctly merges operations from different sources
- Same content from same source doesn't duplicate
- Multiple clients reading without editing don't corrupt content
"""

import asyncio

from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase
from pycrdt import Doc, Text

from backend.asgi import application
from collab.models import YSnapshot, YUpdate
from pages.tests.factories import PageFactory, UserFactory


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
        user = await sync_to_async(UserFactory.create)()
        page = await sync_to_async(PageFactory.create)(creator=user)
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
        user = await sync_to_async(UserFactory.create)()
        page = await sync_to_async(PageFactory.create)(creator=user)
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
        user = await sync_to_async(UserFactory.create)()
        page = await sync_to_async(PageFactory.create)(creator=user)
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
        user = await sync_to_async(UserFactory.create)()
        page = await sync_to_async(PageFactory.create)(creator=user)
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
        user = await sync_to_async(UserFactory.create)()
        page = await sync_to_async(PageFactory.create)(creator=user)
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
