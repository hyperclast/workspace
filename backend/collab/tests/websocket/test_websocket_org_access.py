"""
Tests for WebSocket two-tier access control (org-level + project-level).

Tests that org members and project editors can access pages via WebSocket connections.
"""

from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase

from backend.asgi import application
from pages.tests.factories import PageFactory, ProjectFactory, UserFactory
from users.tests.factories import OrgFactory, OrgMemberFactory

User = get_user_model()


class TestWebSocketTwoTierAccess(TransactionTestCase):
    """Test two-tier access control for WebSocket connections."""

    async def test_org_member_can_join_org_page(self):
        """Test that org members can connect to pages in org projects."""
        # Create org with admin and member
        org = await sync_to_async(OrgFactory.create)()
        admin = await sync_to_async(UserFactory.create)()
        member = await sync_to_async(UserFactory.create)()

        await sync_to_async(OrgMemberFactory.create)(org=org, user=admin, role="admin")
        await sync_to_async(OrgMemberFactory.create)(org=org, user=member, role="member")

        # Create project and page
        project = await sync_to_async(ProjectFactory.create)(org=org, creator=admin)
        page = await sync_to_async(PageFactory.create)(project=project, creator=admin)

        # Org member connects
        communicator = WebsocketCommunicator(
            application,
            f"/ws/pages/{page.external_id}/",
        )
        communicator.scope["user"] = member

        connected, _ = await communicator.connect()
        self.assertTrue(connected, "Org member should be able to connect to org project page")

        await communicator.disconnect()

    async def test_org_admin_can_join_org_page(self):
        """Test that org admins can connect to pages in org projects."""
        # Create org with admin
        org = await sync_to_async(OrgFactory.create)()
        admin = await sync_to_async(UserFactory.create)()

        await sync_to_async(OrgMemberFactory.create)(org=org, user=admin, role="admin")

        # Create project and page
        project = await sync_to_async(ProjectFactory.create)(org=org, creator=admin)
        page = await sync_to_async(PageFactory.create)(project=project, creator=admin)

        # Org admin connects
        communicator = WebsocketCommunicator(
            application,
            f"/ws/pages/{page.external_id}/",
        )
        communicator.scope["user"] = admin

        connected, _ = await communicator.connect()
        self.assertTrue(connected, "Org admin should be able to connect to org project page")

        await communicator.disconnect()

    async def test_external_user_cannot_join_org_page(self):
        """Test that external users cannot connect to org pages by default."""
        # Create org with member
        org = await sync_to_async(OrgFactory.create)()
        member = await sync_to_async(UserFactory.create)()
        external_user = await sync_to_async(UserFactory.create)()

        await sync_to_async(OrgMemberFactory.create)(org=org, user=member, role="member")

        # Create project and page
        project = await sync_to_async(ProjectFactory.create)(org=org, creator=member)
        page = await sync_to_async(PageFactory.create)(project=project, creator=member)

        # External user tries to connect
        communicator = WebsocketCommunicator(
            application,
            f"/ws/pages/{page.external_id}/",
        )
        communicator.scope["user"] = external_user

        connected, _ = await communicator.connect()
        self.assertFalse(connected, "External user should not be able to connect to org page")

    async def test_project_editor_can_join_page(self):
        """Test that project editors can connect to pages in shared projects."""
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
        self.assertTrue(connected, "Project editor should be able to connect to project page")

        await communicator.disconnect()

    async def test_multiple_org_members_can_join_simultaneously(self):
        """Test that multiple org members can connect to the same page simultaneously."""
        # Create org with two members
        org = await sync_to_async(OrgFactory.create)()
        member1 = await sync_to_async(UserFactory.create)()
        member2 = await sync_to_async(UserFactory.create)()

        await sync_to_async(OrgMemberFactory.create)(org=org, user=member1, role="member")
        await sync_to_async(OrgMemberFactory.create)(org=org, user=member2, role="member")

        # Create project and page
        project = await sync_to_async(ProjectFactory.create)(org=org, creator=member1)
        page = await sync_to_async(PageFactory.create)(project=project, creator=member1)

        # Create two communicators
        comm1 = WebsocketCommunicator(
            application,
            f"/ws/pages/{page.external_id}/",
        )
        comm1.scope["user"] = member1

        comm2 = WebsocketCommunicator(
            application,
            f"/ws/pages/{page.external_id}/",
        )
        comm2.scope["user"] = member2

        # Both connect
        connected1, _ = await comm1.connect()
        connected2, _ = await comm2.connect()

        self.assertTrue(connected1, "First org member should connect successfully")
        self.assertTrue(connected2, "Second org member should connect successfully")

        # Disconnect both
        await comm1.disconnect()
        await comm2.disconnect()

    async def test_user_with_both_access_types_can_join(self):
        """Test that user with both org and project-level access can connect."""
        # Create org with member
        org = await sync_to_async(OrgFactory.create)()
        member = await sync_to_async(UserFactory.create)()

        await sync_to_async(OrgMemberFactory.create)(org=org, user=member, role="member")

        # Create project and page
        project = await sync_to_async(ProjectFactory.create)(org=org, creator=member)
        page = await sync_to_async(PageFactory.create)(project=project, creator=member)

        # Also add as project editor (dual access)
        await sync_to_async(project.editors.add)(member)

        # Member connects (has both org and project access)
        communicator = WebsocketCommunicator(
            application,
            f"/ws/pages/{page.external_id}/",
        )
        communicator.scope["user"] = member

        connected, _ = await communicator.connect()
        self.assertTrue(connected, "User with both access types should be able to connect")

        await communicator.disconnect()
