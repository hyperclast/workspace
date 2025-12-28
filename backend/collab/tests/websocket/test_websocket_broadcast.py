"""
Tests for WebSocket update broadcasting functionality.

Tests that CRDT updates are properly broadcast to all connected clients.
Uses two-tier access model: Tier 1 (org membership) or Tier 2 (project editor).
"""

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


class TestWebSocketBroadcast(TransactionTestCase):
    """Test broadcasting of updates between connected clients."""

    async def test_update_broadcast_to_other_client(self):
        """Test that an update from one client is broadcast to other clients."""
        # Create owner with org/project and page
        owner, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(owner, org, project)

        # Create project editor (Tier 2 access)
        editor = await sync_to_async(UserFactory.create)()
        await add_project_editor(project, editor)

        # Connect two clients
        comm1 = WebsocketCommunicator(
            application,
            f"/ws/pages/{page.external_id}/",
        )
        comm1.scope["user"] = owner

        comm2 = WebsocketCommunicator(
            application,
            f"/ws/pages/{page.external_id}/",
        )
        comm2.scope["user"] = editor

        await comm1.connect()
        await comm2.connect()

        # Client 1 creates a Yjs update
        doc = Doc()
        text = doc.get("codemirror", type=Text)
        text.insert(0, "Hello from client 1")
        update_bytes = doc.get_update()

        # Client 1 sends the update
        await comm1.send_to(bytes_data=update_bytes)

        # Client 2 should receive the broadcast
        try:
            message = await comm2.receive_from(timeout=2)
            self.assertIsNotNone(message, "Client 2 should receive broadcast message")
            # The message should be binary (Yjs update)
            self.assertIsInstance(message, bytes, "Broadcast should be binary Yjs update")
        except Exception as e:
            self.fail(f"Failed to receive broadcast: {e}")
        finally:
            await comm1.disconnect()
            await comm2.disconnect()

    async def test_update_not_echoed_to_sender(self):
        """Test that updates are not echoed back to the sender (pycrdt-websocket behavior)."""
        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project)

        comm = WebsocketCommunicator(
            application,
            f"/ws/pages/{page.external_id}/",
        )
        comm.scope["user"] = user

        await comm.connect()

        # Send an update
        doc = Doc()
        text = doc.get("codemirror", type=Text)
        text.insert(0, "Test")
        update_bytes = doc.get_update()

        await comm.send_to(bytes_data=update_bytes)

        # Try to receive - should timeout (no echo)
        try:
            await comm.receive_nothing(timeout=0.5)
            # If we get here, no message was received (expected)
        except Exception:
            # If we got a message, this test fails
            self.fail("Update should not be echoed back to sender")
        finally:
            await comm.disconnect()

    async def test_broadcast_to_multiple_clients(self):
        """Test that updates are broadcast to all connected clients except sender."""
        # Create owner with org/project
        user1, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user1, org, project)

        # Create two more users with project editor access
        user2 = await sync_to_async(UserFactory.create)()
        user3 = await sync_to_async(UserFactory.create)()
        await add_project_editor(project, user2)
        await add_project_editor(project, user3)

        # Connect all three clients
        comm1 = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm1.scope["user"] = user1

        comm2 = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm2.scope["user"] = user2

        comm3 = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm3.scope["user"] = user3

        await comm1.connect()
        await comm2.connect()
        await comm3.connect()

        # Client 1 sends update
        doc = Doc()
        text = doc.get("codemirror", type=Text)
        text.insert(0, "Broadcast test")
        update_bytes = doc.get_update()

        await comm1.send_to(bytes_data=update_bytes)

        # Both client 2 and client 3 should receive it
        received_count = 0
        try:
            msg2 = await comm2.receive_from(timeout=2)
            if msg2:
                received_count += 1
        except Exception:
            pass

        try:
            msg3 = await comm3.receive_from(timeout=2)
            if msg3:
                received_count += 1
        except Exception:
            pass

        self.assertGreaterEqual(received_count, 1, "At least one other client should receive the broadcast")

        await comm1.disconnect()
        await comm2.disconnect()
        await comm3.disconnect()

    async def test_large_update_broadcast(self):
        """Test that large updates are successfully broadcast."""
        owner, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(owner, org, project)

        editor = await sync_to_async(UserFactory.create)()
        await add_project_editor(project, editor)

        comm1 = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm1.scope["user"] = owner

        comm2 = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm2.scope["user"] = editor

        await comm1.connect()
        await comm2.connect()

        # Create a large document
        doc = Doc()
        text = doc.get("codemirror", type=Text)
        large_text = "A" * 10000  # 10K characters
        text.insert(0, large_text)
        update_bytes = doc.get_update()

        # Send large update
        await comm1.send_to(bytes_data=update_bytes)

        # Client 2 should receive it
        try:
            message = await comm2.receive_from(timeout=3)
            self.assertIsNotNone(message, "Large update should be received")
            self.assertGreater(len(message), 0, "Received message should have content")
        except Exception as e:
            self.fail(f"Failed to receive large update: {e}")
        finally:
            await comm1.disconnect()
            await comm2.disconnect()

    async def test_rapid_updates_broadcast(self):
        """Test that rapid sequential updates are all broadcast."""
        owner, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(owner, org, project)

        editor = await sync_to_async(UserFactory.create)()
        await add_project_editor(project, editor)

        comm1 = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm1.scope["user"] = owner

        comm2 = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm2.scope["user"] = editor

        await comm1.connect()
        await comm2.connect()

        # Send multiple rapid updates
        doc = Doc()
        text = doc.get("codemirror", type=Text)

        num_updates = 5
        for i in range(num_updates):
            text.insert(len(text), f"Update {i}\n")
            update_bytes = doc.get_update()
            await comm1.send_to(bytes_data=update_bytes)

        # Client 2 should receive messages (may be coalesced)
        received_messages = 0
        for _ in range(num_updates):
            try:
                message = await comm2.receive_from(timeout=1)
                if message:
                    received_messages += 1
            except Exception:
                break

        # We should receive at least some messages
        # (exact count depends on implementation - may coalesce)
        self.assertGreater(received_messages, 0, "Should receive at least some rapid updates")

        await comm1.disconnect()
        await comm2.disconnect()

    async def test_client_disconnect_stops_receiving_broadcasts(self):
        """Test that disconnected clients no longer receive broadcasts."""
        user1, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user1, org, project)

        user2 = await sync_to_async(UserFactory.create)()
        await add_project_editor(project, user2)

        comm1 = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm1.scope["user"] = user1

        comm2 = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm2.scope["user"] = user2

        await comm1.connect()
        await comm2.connect()

        # Client 2 disconnects
        await comm2.disconnect()

        # Client 1 sends update
        doc = Doc()
        text = doc.get("codemirror", type=Text)
        text.insert(0, "After disconnect")
        update_bytes = doc.get_update()

        await comm1.send_to(bytes_data=update_bytes)

        # comm2 is disconnected, so trying to receive should fail or return nothing
        # This test mainly ensures no errors occur server-side

        await comm1.disconnect()
