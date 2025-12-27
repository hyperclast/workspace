"""
Tests for WebSocket access revocation when users are removed from projects/orgs.

Note: These tests verify that:
1. Project-level and org-level access revocation notifications are properly implemented
2. The WebSocket consumer correctly re-checks access before kicking users
3. Users with dual access (org + project) are not incorrectly kicked
"""

import asyncio
import json

from asgiref.sync import sync_to_async
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase

from backend.asgi import application
from pages.tests.factories import PageFactory, ProjectFactory, UserFactory
from users.tests.factories import OrgFactory, OrgMemberFactory

User = get_user_model()


class TestProjectAccessRevocation(TransactionTestCase):
    """Test that removing a project editor closes their WebSocket connection."""

    async def test_project_editor_removed_gets_kicked(self):
        """Test that when a project editor is removed, their WebSocket connection closes."""
        # Create org with member
        org = await sync_to_async(OrgFactory.create)()
        member = await sync_to_async(UserFactory.create)()
        external_user = await sync_to_async(UserFactory.create)()

        await sync_to_async(OrgMemberFactory.create)(org=org, user=member, role="member")

        # Create project and page
        project = await sync_to_async(ProjectFactory.create)(org=org, creator=member)
        page = await sync_to_async(PageFactory.create)(project=project, creator=member)

        # Add external user as project editor
        await sync_to_async(project.editors.add)(external_user)

        # External user connects
        communicator = WebsocketCommunicator(
            application,
            f"/ws/pages/{page.external_id}/",
        )
        communicator.scope["user"] = external_user

        connected, _ = await communicator.connect()
        self.assertTrue(connected, "Project editor should be able to connect")

        # Consume any initial sync messages
        try:
            while True:
                await asyncio.wait_for(communicator.receive_output(), timeout=0.1)
        except asyncio.TimeoutError:
            pass

        # Remove the user from project editors
        await sync_to_async(project.editors.remove)(external_user)

        # Send access revoked message directly to the consumer via channel layer
        channel_layer = get_channel_layer()
        room_name = f"page_{page.external_id}"
        await channel_layer.group_send(
            room_name,
            {
                "type": "access_revoked",
                "user_id": external_user.id,
            },
        )

        # User should receive access_revoked message
        response = await asyncio.wait_for(communicator.receive_output(), timeout=2)

        if response["type"] == "websocket.send":
            text = response.get("text", "")
            self.assertIn("access_revoked", text)

            # Connection should be closed next
            close_response = await asyncio.wait_for(communicator.receive_output(), timeout=2)
            self.assertEqual(close_response["type"], "websocket.close")
            self.assertEqual(close_response.get("code"), 4001)
        else:
            self.assertEqual(response["type"], "websocket.close")
            self.assertEqual(response.get("code"), 4001)

    async def test_project_editor_with_org_access_not_kicked(self):
        """Test that org members with project editor access aren't kicked when removed as editor."""
        # Create org with two members
        org = await sync_to_async(OrgFactory.create)()
        member1 = await sync_to_async(UserFactory.create)()
        member2 = await sync_to_async(UserFactory.create)()

        await sync_to_async(OrgMemberFactory.create)(org=org, user=member1, role="member")
        await sync_to_async(OrgMemberFactory.create)(org=org, user=member2, role="member")

        # Create project and page
        project = await sync_to_async(ProjectFactory.create)(org=org, creator=member1)
        page = await sync_to_async(PageFactory.create)(project=project, creator=member1)

        # Also add member2 as explicit project editor
        await sync_to_async(project.editors.add)(member2)

        # Member2 connects
        communicator = WebsocketCommunicator(
            application,
            f"/ws/pages/{page.external_id}/",
        )
        communicator.scope["user"] = member2

        connected, _ = await communicator.connect()
        self.assertTrue(connected, "Member should be able to connect")

        # Consume any initial sync messages
        try:
            while True:
                await asyncio.wait_for(communicator.receive_output(), timeout=0.1)
        except asyncio.TimeoutError:
            pass

        # Remove member2 as project editor (but they still have org access)
        await sync_to_async(project.editors.remove)(member2)

        # Send access revoked message
        channel_layer = get_channel_layer()
        room_name = f"page_{page.external_id}"
        await channel_layer.group_send(
            room_name,
            {
                "type": "access_revoked",
                "user_id": member2.id,
            },
        )

        # Connection should NOT be closed because user still has org access
        try:
            response = await asyncio.wait_for(communicator.receive_output(), timeout=0.5)
            # If we get a close message, fail the test
            if response["type"] == "websocket.close":
                self.fail("User with org access should not be kicked when removed as project editor")
            # If it's a text message with access_revoked, also fail
            if response["type"] == "websocket.send" and "access_revoked" in response.get("text", ""):
                self.fail("User with org access should not receive access_revoked message")
        except asyncio.TimeoutError:
            # Good - no close message means connection is still open
            pass

        await communicator.disconnect()


class TestOrgAccessRevocation(TransactionTestCase):
    """Test that removing an org member closes their WebSocket connections."""

    async def test_org_member_removed_gets_kicked(self):
        """Test that when an org member is removed, their WebSocket connection closes."""
        # Create org with two members
        org = await sync_to_async(OrgFactory.create)()
        admin = await sync_to_async(UserFactory.create)()
        member = await sync_to_async(UserFactory.create)()

        await sync_to_async(OrgMemberFactory.create)(org=org, user=admin, role="admin")
        await sync_to_async(OrgMemberFactory.create)(org=org, user=member, role="member")

        # Create project and page
        project = await sync_to_async(ProjectFactory.create)(org=org, creator=admin)
        page = await sync_to_async(PageFactory.create)(project=project, creator=admin)

        # Member connects
        communicator = WebsocketCommunicator(
            application,
            f"/ws/pages/{page.external_id}/",
        )
        communicator.scope["user"] = member

        connected, _ = await communicator.connect()
        self.assertTrue(connected, "Org member should be able to connect")

        # Consume any initial sync messages
        try:
            while True:
                await asyncio.wait_for(communicator.receive_output(), timeout=0.1)
        except asyncio.TimeoutError:
            pass

        # Remove the member from org
        await sync_to_async(lambda: org.members.remove(member))()

        # Send access revoked message
        channel_layer = get_channel_layer()
        room_name = f"page_{page.external_id}"
        await channel_layer.group_send(
            room_name,
            {
                "type": "access_revoked",
                "user_id": member.id,
            },
        )

        # User should receive access_revoked message and connection should close
        response = await asyncio.wait_for(communicator.receive_output(), timeout=2)

        if response["type"] == "websocket.send":
            text = response.get("text", "")
            self.assertIn("access_revoked", text)

            # Connection should be closed next
            close_response = await asyncio.wait_for(communicator.receive_output(), timeout=2)
            self.assertEqual(close_response["type"], "websocket.close")
            self.assertEqual(close_response.get("code"), 4001)
        else:
            self.assertEqual(response["type"], "websocket.close")
            self.assertEqual(response.get("code"), 4001)

    async def test_org_member_with_project_access_not_kicked(self):
        """Test that project editors aren't kicked when removed from org."""
        # Create org with member
        org = await sync_to_async(OrgFactory.create)()
        admin = await sync_to_async(UserFactory.create)()
        member = await sync_to_async(UserFactory.create)()

        await sync_to_async(OrgMemberFactory.create)(org=org, user=admin, role="admin")
        await sync_to_async(OrgMemberFactory.create)(org=org, user=member, role="member")

        # Create project and page
        project = await sync_to_async(ProjectFactory.create)(org=org, creator=admin)
        page = await sync_to_async(PageFactory.create)(project=project, creator=admin)

        # Also add member as project editor (dual access)
        await sync_to_async(project.editors.add)(member)

        # Member connects
        communicator = WebsocketCommunicator(
            application,
            f"/ws/pages/{page.external_id}/",
        )
        communicator.scope["user"] = member

        connected, _ = await communicator.connect()
        self.assertTrue(connected, "Member should be able to connect")

        # Consume any initial sync messages
        try:
            while True:
                await asyncio.wait_for(communicator.receive_output(), timeout=0.1)
        except asyncio.TimeoutError:
            pass

        # Remove member from org (but they still have project editor access)
        await sync_to_async(lambda: org.members.remove(member))()

        # Send access revoked message
        channel_layer = get_channel_layer()
        room_name = f"page_{page.external_id}"
        await channel_layer.group_send(
            room_name,
            {
                "type": "access_revoked",
                "user_id": member.id,
            },
        )

        # Connection should NOT be closed because user still has project editor access
        try:
            response = await asyncio.wait_for(communicator.receive_output(), timeout=0.5)
            if response["type"] == "websocket.close":
                self.fail("User with project editor access should not be kicked when removed from org")
            if response["type"] == "websocket.send" and "access_revoked" in response.get("text", ""):
                self.fail("User with project editor access should not receive access_revoked message")
        except asyncio.TimeoutError:
            # Good - no close message means connection is still open
            pass

        await communicator.disconnect()
