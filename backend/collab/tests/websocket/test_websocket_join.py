"""
Tests for WebSocket document joining functionality.

Tests that clients can successfully connect to and join collaborative editing sessions.
Uses two-tier access model: Tier 1 (org membership) or Tier 2 (project editor).
"""

from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase

from backend.asgi import application
from pages.tests.factories import PageFactory, ProjectFactory
from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory

User = get_user_model()


class TestWebSocketJoin(TransactionTestCase):
    """Test clients joining collaborative editing sessions."""

    async def _create_user_with_org_and_project(self):
        """Helper to create a user with org membership and project."""
        org = await sync_to_async(OrgFactory.create)()
        user = await sync_to_async(UserFactory.create)()
        await sync_to_async(OrgMemberFactory.create)(org=org, user=user)
        project = await sync_to_async(ProjectFactory.create)(org=org, creator=user)
        return user, org, project

    async def test_owner_can_join_own_page(self):
        """Test that page owner can successfully connect to WebSocket."""
        # Create user with org/project and page
        user, org, project = await self._create_user_with_org_and_project()
        page = await sync_to_async(PageFactory.create)(project=project, creator=user)

        # Create WebSocket communicator
        communicator = WebsocketCommunicator(
            application,
            f"/ws/pages/{page.external_id}/",
        )
        communicator.scope["user"] = user

        # Connect
        connected, _ = await communicator.connect()
        self.assertTrue(connected, "Owner should be able to connect to their own page")

        # Disconnect
        await communicator.disconnect()

    async def test_editor_can_join_shared_page(self):
        """Test that a project editor can connect to a page in that project."""
        # Create owner with org/project and page
        owner, org, project = await self._create_user_with_org_and_project()
        page = await sync_to_async(PageFactory.create)(project=project, creator=owner)

        # Create project editor (not in org, but has project-level access)
        editor = await sync_to_async(UserFactory.create)()
        await sync_to_async(project.editors.add)(editor)

        # Editor connects
        communicator = WebsocketCommunicator(
            application,
            f"/ws/pages/{page.external_id}/",
        )
        communicator.scope["user"] = editor

        connected, _ = await communicator.connect()
        self.assertTrue(connected, "Project editor should be able to connect to page")

        await communicator.disconnect()

    async def test_unauthorized_user_cannot_join(self):
        """Test that a user without access cannot connect."""
        # Create page with owner who has org access
        owner, org, project = await self._create_user_with_org_and_project()
        page = await sync_to_async(PageFactory.create)(project=project, creator=owner)

        # Unauthorized user (not in org, not project editor)
        unauthorized_user = await sync_to_async(UserFactory.create)()

        # Unauthorized user tries to connect
        communicator = WebsocketCommunicator(
            application,
            f"/ws/pages/{page.external_id}/",
        )
        communicator.scope["user"] = unauthorized_user

        connected, _ = await communicator.connect()
        self.assertFalse(connected, "Unauthorized user should not be able to connect")

    async def test_unauthenticated_user_cannot_join(self):
        """Test that an unauthenticated user cannot connect."""
        # Create page
        owner, org, project = await self._create_user_with_org_and_project()
        page = await sync_to_async(PageFactory.create)(project=project, creator=owner)

        # Unauthenticated user tries to connect
        communicator = WebsocketCommunicator(
            application,
            f"/ws/pages/{page.external_id}/",
        )
        communicator.scope["user"] = AnonymousUser()

        connected, _ = await communicator.connect()
        self.assertFalse(connected, "Unauthenticated user should not be able to connect")

    async def test_nonexistent_page_connection_fails(self):
        """Test that connecting to a non-existent page fails."""
        user = await sync_to_async(UserFactory.create)()

        # Try to connect to non-existent page
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        communicator = WebsocketCommunicator(
            application,
            f"/ws/pages/{fake_uuid}/",
        )
        communicator.scope["user"] = user

        connected, _ = await communicator.connect()
        self.assertFalse(connected, "Should not be able to connect to non-existent page")

    async def test_multiple_clients_can_join_same_page(self):
        """Test that multiple clients can connect to the same page simultaneously."""
        # Create owner with org/project and page
        owner, org, project = await self._create_user_with_org_and_project()
        page = await sync_to_async(PageFactory.create)(project=project, creator=owner)

        # Create project editor
        editor = await sync_to_async(UserFactory.create)()
        await sync_to_async(project.editors.add)(editor)

        # Create two communicators
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

        # Both connect
        connected1, _ = await comm1.connect()
        connected2, _ = await comm2.connect()

        self.assertTrue(connected1, "First client should connect successfully")
        self.assertTrue(connected2, "Second client should connect successfully")

        # Disconnect both
        await comm1.disconnect()
        await comm2.disconnect()

    async def test_same_user_can_have_multiple_connections(self):
        """Test that the same user can have multiple WebSocket connections (e.g., multiple browser tabs)."""
        user, org, project = await self._create_user_with_org_and_project()
        page = await sync_to_async(PageFactory.create)(project=project, creator=user)

        # Create two communicators for same user
        comm1 = WebsocketCommunicator(
            application,
            f"/ws/pages/{page.external_id}/",
        )
        comm1.scope["user"] = user

        comm2 = WebsocketCommunicator(
            application,
            f"/ws/pages/{page.external_id}/",
        )
        comm2.scope["user"] = user

        # Both connect
        connected1, _ = await comm1.connect()
        connected2, _ = await comm2.connect()

        self.assertTrue(connected1, "First connection should succeed")
        self.assertTrue(connected2, "Second connection should succeed")

        # Disconnect both
        await comm1.disconnect()
        await comm2.disconnect()

    async def test_connection_rejected_with_proper_close_code(self):
        """Test that unauthorized connections are rejected with proper WebSocket close code."""
        owner, org, project = await self._create_user_with_org_and_project()
        page = await sync_to_async(PageFactory.create)(project=project, creator=owner)

        # Unauthorized user (not in org, not project editor)
        unauthorized_user = await sync_to_async(UserFactory.create)()

        communicator = WebsocketCommunicator(
            application,
            f"/ws/pages/{page.external_id}/",
        )
        communicator.scope["user"] = unauthorized_user

        connected, close_code = await communicator.connect()

        # Should be rejected
        self.assertFalse(connected, "Unauthorized user should be rejected")
        # Close code 4003 is used for access denied (see consumers.py:60)
        self.assertEqual(close_code, 4003, f"Expected close code 4003, got {close_code}")
