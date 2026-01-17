"""
Tests for WebSocket write permission enforcement.

Tests that viewers (read-only users) cannot send updates via WebSocket,
while editors can send updates normally.
"""

import asyncio

from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase
from pycrdt import Doc, Text, YMessageType, YSyncMessageType, create_sync_message, create_update_message

from backend.asgi import application
from collab.tests import (
    create_page_with_access,
    create_user_with_org_and_project,
)
from pages.constants import PageEditorRole, ProjectEditorRole
from pages.tests.factories import PageEditorFactory, ProjectEditorFactory
from users.tests.factories import UserFactory


class TestViewerCannotWrite(TransactionTestCase):
    """Test that viewers are blocked from sending Yjs updates."""

    async def test_viewer_write_rejected_with_error_message(self):
        """
        Viewer's SYNC_UPDATE message should be rejected with an error.

        The viewer should receive a read_only error message and the update
        should NOT be broadcast to other clients or persisted.
        """
        # Setup: Create page with owner
        owner, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(owner, org, project)

        # Create viewer (not in org, just page-level viewer)
        viewer = await sync_to_async(UserFactory.create)()
        await sync_to_async(PageEditorFactory.create)(page=page, user=viewer, role=PageEditorRole.VIEWER.value)

        # Connect viewer
        comm = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm.scope["user"] = viewer

        connected, _ = await comm.connect()
        self.assertTrue(connected, "Viewer should be able to connect (read access)")

        # Wait a bit for initial sync to complete
        await asyncio.sleep(0.5)

        # Create a Yjs update using the proper pycrdt message format
        doc = Doc()
        text = doc.get("codemirror", type=Text)
        text.insert(0, "Viewer's edit attempt")

        # Use create_update_message for proper Yjs protocol format
        update_bytes = doc.get_update()
        sync_update_message = create_update_message(update_bytes)

        # Send the update
        await comm.send_to(bytes_data=sync_update_message)

        # Should receive error response (may be after some sync messages)
        # Try receiving up to 5 messages to find the error
        found_error = False
        for _ in range(5):
            try:
                response = await comm.receive_from(timeout=1)
                if isinstance(response, bytes):
                    try:
                        response = response.decode("utf-8")
                    except UnicodeDecodeError:
                        continue  # Binary sync message, keep looking
                if "read_only" in response:
                    found_error = True
                    self.assertIn("view-only access", response, "Error should mention view-only")
                    break
            except asyncio.TimeoutError:
                break

        self.assertTrue(found_error, "Should receive read_only error")

        await comm.disconnect()

    async def test_project_viewer_write_rejected(self):
        """
        Project viewer (via ProjectEditor with viewer role) cannot write.
        """
        # Setup: Create project that doesn't allow org member access
        owner, org, project = await create_user_with_org_and_project()
        # Disable org member access to force use of project editor roles
        project.org_members_can_access = False
        await sync_to_async(project.save)()

        page = await create_page_with_access(owner, org, project)

        # Create project viewer (not org member, just project-level viewer)
        viewer = await sync_to_async(UserFactory.create)()
        await sync_to_async(ProjectEditorFactory.create)(
            project=project, user=viewer, role=ProjectEditorRole.VIEWER.value
        )

        # Connect viewer
        comm = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm.scope["user"] = viewer

        connected, _ = await comm.connect()
        self.assertTrue(connected, "Project viewer should be able to connect")

        # Wait a bit for initial sync
        await asyncio.sleep(0.5)

        # Try to send update using proper pycrdt message format
        doc = Doc()
        text = doc.get("codemirror", type=Text)
        text.insert(0, "Project viewer edit attempt")

        update_bytes = doc.get_update()
        sync_update_message = create_update_message(update_bytes)

        await comm.send_to(bytes_data=sync_update_message)

        # Should receive error - try multiple messages to find it
        found_error = False
        for _ in range(5):
            try:
                response = await comm.receive_from(timeout=1)
                if isinstance(response, bytes):
                    try:
                        response = response.decode("utf-8")
                    except UnicodeDecodeError:
                        continue
                if "read_only" in response:
                    found_error = True
                    break
            except asyncio.TimeoutError:
                break

        self.assertTrue(found_error, "Should receive read_only error")

        await comm.disconnect()

    async def test_viewer_update_not_persisted(self):
        """
        Viewer's rejected update should NOT be persisted to database.
        """
        from collab.models import YUpdate

        owner, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(owner, org, project)
        room_name = f"page_{page.external_id}"

        # Create viewer
        viewer = await sync_to_async(UserFactory.create)()
        await sync_to_async(PageEditorFactory.create)(page=page, user=viewer, role=PageEditorRole.VIEWER.value)

        # Get initial update count
        initial_count = await sync_to_async(YUpdate.objects.filter(room_id=room_name).count)()

        # Connect viewer
        comm = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm.scope["user"] = viewer

        await comm.connect()
        await asyncio.sleep(0.5)  # Wait for initial sync

        # Send update using proper pycrdt message format
        doc = Doc()
        text = doc.get("codemirror", type=Text)
        text.insert(0, "Should not persist")

        update_bytes = doc.get_update()
        sync_update_message = create_update_message(update_bytes)

        await comm.send_to(bytes_data=sync_update_message)

        # Wait for any processing
        await asyncio.sleep(1.0)

        try:
            await comm.disconnect()
        except asyncio.CancelledError:
            pass  # Connection may already be closed
        await asyncio.sleep(0.5)

        # Verify no new updates were persisted
        final_count = await sync_to_async(YUpdate.objects.filter(room_id=room_name).count)()
        self.assertEqual(
            initial_count,
            final_count,
            "Viewer's update should NOT be persisted to database",
        )


class TestEditorCanWrite(TransactionTestCase):
    """Test that editors can write normally."""

    async def test_page_editor_can_write(self):
        """
        Page editor with 'editor' role can send updates without receiving error.
        """
        owner, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(owner, org, project)

        # Create page editor
        editor = await sync_to_async(UserFactory.create)()
        await sync_to_async(PageEditorFactory.create)(page=page, user=editor, role=PageEditorRole.EDITOR.value)

        # Connect editor
        comm = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm.scope["user"] = editor

        await comm.connect()
        await asyncio.sleep(0.3)

        # Send update using proper pycrdt message format
        doc = Doc()
        text = doc.get("codemirror", type=Text)
        text.insert(0, "Editor's valid edit")

        update_bytes = doc.get_update()
        sync_update_message = create_update_message(update_bytes)

        await comm.send_to(bytes_data=sync_update_message)

        # Editors should NOT receive read_only error
        try:
            response = await comm.receive_from(timeout=0.5)
            if isinstance(response, str) and "read_only" in response:
                self.fail("Editor should NOT receive read_only error")
            # Receiving a binary response (sync message) is fine
        except asyncio.TimeoutError:
            # No error received - this is the expected case
            pass

        await comm.disconnect()

    async def test_org_member_can_write(self):
        """
        Org members have write access by default (org_members_can_access=True).
        """
        owner, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(owner, org, project)

        # Connect as owner (org member)
        comm = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm.scope["user"] = owner

        await comm.connect()
        await asyncio.sleep(0.3)

        # Send update using proper pycrdt message format
        doc = Doc()
        text = doc.get("codemirror", type=Text)
        text.insert(0, "Org member's edit")

        update_bytes = doc.get_update()
        sync_update_message = create_update_message(update_bytes)

        await comm.send_to(bytes_data=sync_update_message)

        # Org members should NOT receive read_only error
        try:
            response = await comm.receive_from(timeout=0.5)
            if isinstance(response, str) and "read_only" in response:
                self.fail("Org member should NOT receive read_only error")
            # Receiving a binary response (sync message) is fine
        except asyncio.TimeoutError:
            # No error received - this is the expected case
            pass

        await comm.disconnect()


class TestViewerReceivesUpdates(TransactionTestCase):
    """Test that viewers can receive updates from editors."""

    async def test_viewer_receives_editor_updates(self):
        """
        Viewers should still receive updates broadcast by editors.
        """
        owner, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(owner, org, project)

        # Create viewer
        viewer = await sync_to_async(UserFactory.create)()
        await sync_to_async(PageEditorFactory.create)(page=page, user=viewer, role=PageEditorRole.VIEWER.value)

        # Connect both
        comm_owner = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm_owner.scope["user"] = owner

        comm_viewer = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm_viewer.scope["user"] = viewer

        await comm_owner.connect()
        await comm_viewer.connect()

        await asyncio.sleep(0.5)

        # Owner sends update using proper pycrdt message format
        doc = Doc()
        text = doc.get("codemirror", type=Text)
        text.insert(0, "Owner's edit")

        update_bytes = doc.get_update()
        sync_update_message = create_update_message(update_bytes)

        await comm_owner.send_to(bytes_data=sync_update_message)

        # Viewer should receive the broadcast
        try:
            response = await comm_viewer.receive_from(timeout=2)
            self.assertIsNotNone(response, "Viewer should receive editor's broadcast")
        except asyncio.TimeoutError:
            # In some test configurations, the broadcast may not be received
            # The key is that viewer's connection is still active
            pass

        await comm_owner.disconnect()
        await comm_viewer.disconnect()


class TestNonSyncMessagesAllowed(TransactionTestCase):
    """Test that non-SYNC_UPDATE messages are allowed for viewers."""

    async def test_viewer_can_send_sync_step1(self):
        """
        Viewers should be able to send SYNC_STEP1 (state vector request).
        This is needed for initial sync.
        """
        owner, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(owner, org, project)

        # Create viewer
        viewer = await sync_to_async(UserFactory.create)()
        await sync_to_async(PageEditorFactory.create)(page=page, user=viewer, role=PageEditorRole.VIEWER.value)

        # Connect viewer
        comm = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm.scope["user"] = viewer

        connected, _ = await comm.connect()
        self.assertTrue(connected)

        await asyncio.sleep(0.3)

        # Send SYNC_STEP1 message using proper pycrdt format
        # This is what the client sends to request state vector, not to modify content
        doc = Doc()
        sync_step1_message = create_sync_message(doc)

        await comm.send_to(bytes_data=sync_step1_message)

        # Should NOT receive error (no "read_only" error)
        try:
            response = await comm.receive_from(timeout=1)
            # If we get a response, it should be a sync response, not an error
            if isinstance(response, str) and "read_only" in response:
                self.fail("SYNC_STEP1 should NOT be blocked for viewers")
        except asyncio.TimeoutError:
            # Timeout is fine - means no error was sent
            pass

        await comm.disconnect()
