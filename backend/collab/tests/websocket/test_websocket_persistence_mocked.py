"""
Tests for WebSocket persistence using mocks.

These tests verify that the ystore.write() and ystore.upsert_snapshot() methods
are called (or not called) at the appropriate times, without actually writing to
the database.

NOTE: The consumer now skips saving empty/minimal snapshots (<=2 bytes) to prevent
corrupted 0x0000 snapshots that cause client reconnection loops. Tests that expect
upsert_snapshot() to be called must ensure the document has real content.
"""

import asyncio
from unittest.mock import AsyncMock, patch

from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase
from pycrdt import Doc, Text

from backend.asgi import application
from collab.tests import (
    add_project_editor,
    create_page_with_access,
    create_user_with_org_and_project,
)
from users.tests.factories import UserFactory


class AsyncIteratorMock:
    """Mock async iterator for ystore.read() that yields no updates."""

    def __aiter__(self):
        return self

    async def __anext__(self):
        # No updates yielded in these tests; we just need a valid async iterator.
        raise StopAsyncIteration


class AsyncIteratorWithUpdates:
    """Mock async iterator for ystore.read() that yields actual updates."""

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


class FakeYStore:
    """
    Small fake YStore object that matches how the consumer uses PostgresYStore.

    From the stack trace, the consumer does something like:

        await self.ystore.initialize_pool()
        async for update_bytes, meta, ts in self.ystore.read():
            ...
        await self.ystore.write(...)
        await self.ystore.upsert_snapshot(...)
        await self.ystore.get_max_update_id(...)
        await self.ystore.get_snapshot()
        async for update_bytes, meta, ts, id in self.ystore.read_since(...):
            ...

    So:
    - initialize_pool, write, upsert_snapshot, get_max_update_id, get_snapshot are awaitable.
    - read() and read_since() are *not* awaited; they must return async iterators directly.
    """

    def __init__(self, initial_updates=None):
        """
        Args:
            initial_updates: List of (update_bytes, meta, ts) tuples to return from read()
        """
        self.initialize_pool = AsyncMock()
        self.write = AsyncMock()
        self.upsert_snapshot = AsyncMock()
        self.get_max_update_id = AsyncMock(return_value=0)
        self.get_snapshot = AsyncMock(return_value=None)  # Default: no snapshot exists
        self.close_pool = AsyncMock()
        self.delete_updates_before_snapshot = AsyncMock(return_value=0)
        self._initial_updates = initial_updates or []

    def read(self, *args, **kwargs):
        # Called without await; must return an async iterator usable in `async for`.
        if self._initial_updates:
            return AsyncIteratorWithUpdates(self._initial_updates)
        return AsyncIteratorMock()

    def read_since(self, *args, **kwargs):
        # Called without await; must return an async iterator usable in `async for`.
        return AsyncIteratorMock()


def create_mock_ystore(initial_updates=None):
    """Create a properly configured fake YStore instance."""
    return FakeYStore(initial_updates=initial_updates)


def create_initial_update_with_content():
    """
    Create initial update data that the mock ystore can return.
    This ensures the consumer's ydoc has content after hydration.
    Returns a list of (update_bytes, meta, ts) tuples.
    """
    doc = Doc()
    text = doc.get("codemirror", type=Text)
    text.insert(0, "Test content for snapshot")
    update_bytes = doc.get_update()
    return [(update_bytes, None, None)]


def create_non_empty_doc():
    """
    Create a Yjs doc with actual content.
    This ensures get_update() returns > 2 bytes, which is required for
    snapshot to be saved (empty docs are skipped to prevent corruption).
    """
    doc = Doc()
    text = doc.get("codemirror", type=Text)
    text.insert(0, "Test content for snapshot")
    return doc


class TestWebSocketUpdatePersistenceMocked(TransactionTestCase):
    """Test that ystore.write() is called appropriately for updates."""

    @patch("collab.consumers.PostgresYStore")
    async def test_ystore_write_not_called_on_connect_without_updates(self, MockYStore):
        """Test that ystore.write() is NOT called when a client just connects without sending updates."""
        # Setup fake ystore
        mock_ystore_instance = create_mock_ystore()
        MockYStore.return_value = mock_ystore_instance

        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project)

        comm = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm.scope["user"] = user

        await comm.connect()

        # Wait a bit
        await asyncio.sleep(0.5)

        await comm.disconnect()

        # Wait for any potential async tasks
        await asyncio.sleep(0.5)

        # Verify ystore.write() was NOT called
        self.assertEqual(
            mock_ystore_instance.write.call_count,
            0,
            "ystore.write() should NOT be called when client connects without sending updates",
        )

    @patch("collab.consumers.PostgresYStore")
    async def test_ystore_write_not_called_on_unauthorized_connection(self, MockYStore):
        """Test that ystore.write() is NOT called when unauthorized user tries to connect."""
        # Setup fake ystore
        mock_ystore_instance = create_mock_ystore()
        MockYStore.return_value = mock_ystore_instance

        owner, org, project = await create_user_with_org_and_project()
        unauthorized_user = await sync_to_async(UserFactory.create)()
        page = await create_page_with_access(owner, org, project)

        comm = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm.scope["user"] = unauthorized_user

        # Connection should be rejected
        connected, _ = await comm.connect()
        self.assertFalse(connected)

        # Wait a bit to ensure no async tasks run
        await asyncio.sleep(0.5)

        # Verify ystore.write() was NOT called
        self.assertEqual(
            mock_ystore_instance.write.call_count,
            0,
            "ystore.write() should NOT be called for unauthorized connections",
        )


class TestWebSocketSnapshotPersistence(TransactionTestCase):
    """Test that ystore.upsert_snapshot() is called appropriately."""

    @patch("collab.consumers.PostgresYStore")
    async def test_upsert_snapshot_called_on_disconnect_with_content(self, MockYStore):
        """
        Test that upsert_snapshot() is called when a client disconnects
        AND the document has content.

        Note: Empty documents (<=2 bytes) are intentionally skipped to prevent
        corrupted 0x0000 snapshots that cause client reconnection loops.
        """
        # Setup fake ystore with initial content
        # This ensures the consumer's ydoc has content after hydration
        initial_updates = create_initial_update_with_content()
        mock_ystore_instance = create_mock_ystore(initial_updates=initial_updates)
        mock_ystore_instance.get_max_update_id.return_value = 5
        MockYStore.return_value = mock_ystore_instance

        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project)

        comm = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm.scope["user"] = user

        await comm.connect()

        await asyncio.sleep(0.3)

        # Disconnect - should trigger snapshot write since doc has content
        await comm.disconnect()

        # Wait for async snapshot write
        await asyncio.sleep(1.0)

        # Verify upsert_snapshot was called
        self.assertGreater(
            mock_ystore_instance.upsert_snapshot.call_count,
            0,
            "upsert_snapshot() should be called on disconnect when doc has content",
        )

    @patch("collab.consumers.PostgresYStore")
    async def test_upsert_snapshot_skipped_for_empty_doc(self, MockYStore):
        """
        Test that upsert_snapshot() is NOT called when the document is empty.

        Empty documents produce a 2-byte 0x0000 update which can cause client
        reconnection loops. This is intentionally skipped.
        """
        # Setup fake ystore
        mock_ystore_instance = create_mock_ystore()
        MockYStore.return_value = mock_ystore_instance

        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project)

        comm = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm.scope["user"] = user

        await comm.connect()

        # Don't add any content - document stays empty

        await asyncio.sleep(0.3)

        # Disconnect
        await comm.disconnect()

        # Wait for async tasks
        await asyncio.sleep(0.5)

        # Verify upsert_snapshot was NOT called (empty doc is skipped)
        self.assertEqual(
            mock_ystore_instance.upsert_snapshot.call_count,
            0,
            "upsert_snapshot() should NOT be called for empty documents",
        )

    @patch("collab.consumers.PostgresYStore")
    async def test_upsert_snapshot_not_called_on_rejected_connection(self, MockYStore):
        """Test that upsert_snapshot() is NOT called when connection is rejected."""
        # Setup fake ystore
        mock_ystore_instance = create_mock_ystore()
        MockYStore.return_value = mock_ystore_instance

        owner, org, project = await create_user_with_org_and_project()
        unauthorized_user = await sync_to_async(UserFactory.create)()
        page = await create_page_with_access(owner, org, project)

        comm = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm.scope["user"] = unauthorized_user

        # Connection should be rejected
        connected, _ = await comm.connect()
        self.assertFalse(connected)

        # Wait a bit to ensure no async tasks run
        await asyncio.sleep(0.5)

        # Verify upsert_snapshot was NOT called
        self.assertEqual(
            mock_ystore_instance.upsert_snapshot.call_count,
            0,
            "upsert_snapshot() should NOT be called for rejected connections",
        )

    @patch("collab.consumers.PostgresYStore")
    async def test_upsert_snapshot_not_called_on_connect_only_on_disconnect(self, MockYStore):
        """
        Test that upsert_snapshot() is NOT called on connect, only on disconnect
        when the document has content.
        """
        # Setup fake ystore with initial content
        initial_updates = create_initial_update_with_content()
        mock_ystore_instance = create_mock_ystore(initial_updates=initial_updates)
        mock_ystore_instance.get_max_update_id.return_value = 5
        MockYStore.return_value = mock_ystore_instance

        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project)

        comm = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm.scope["user"] = user

        await comm.connect()

        # Wait a bit
        await asyncio.sleep(0.3)

        # Check that upsert_snapshot was NOT called yet (only on disconnect)
        initial_call_count = mock_ystore_instance.upsert_snapshot.call_count
        self.assertEqual(
            initial_call_count,
            0,
            "upsert_snapshot() should NOT be called on connect",
        )

        # Now disconnect
        await comm.disconnect()

        # Wait for async snapshot write
        await asyncio.sleep(1.0)

        # Now it should have been called (document has content from initial hydration)
        self.assertGreater(
            mock_ystore_instance.upsert_snapshot.call_count,
            initial_call_count,
            "upsert_snapshot() should be called after disconnect when doc has content",
        )

    @patch("collab.consumers.PostgresYStore")
    async def test_upsert_snapshot_called_for_each_disconnect_with_content(self, MockYStore):
        """
        Test that upsert_snapshot() is called for each client disconnect
        when the document has content.
        """
        # Setup fake ystore with initial content
        initial_updates = create_initial_update_with_content()
        mock_ystore_instance = create_mock_ystore(initial_updates=initial_updates)
        mock_ystore_instance.get_max_update_id.return_value = 3
        MockYStore.return_value = mock_ystore_instance

        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project)

        # Connect first client
        comm1 = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm1.scope["user"] = user

        await comm1.connect()
        await asyncio.sleep(0.3)

        # Disconnect first client - should trigger snapshot since doc has content
        await comm1.disconnect()
        await asyncio.sleep(0.5)

        first_disconnect_calls = mock_ystore_instance.upsert_snapshot.call_count

        # Connect second client
        comm2 = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm2.scope["user"] = user

        await comm2.connect()
        await asyncio.sleep(0.3)

        # Disconnect second client - should trigger snapshot since doc has content
        await comm2.disconnect()
        await asyncio.sleep(0.5)

        second_disconnect_calls = mock_ystore_instance.upsert_snapshot.call_count

        # Verify snapshot was written for both disconnects
        self.assertGreater(
            first_disconnect_calls,
            0,
            "upsert_snapshot() should be called on first disconnect",
        )
        self.assertGreater(
            second_disconnect_calls,
            first_disconnect_calls,
            "upsert_snapshot() should be called on second disconnect",
        )
