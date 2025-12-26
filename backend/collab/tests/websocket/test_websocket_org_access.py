"""
Tests for WebSocket two-tier access control (org-level + page-level).

Tests that org members can access pages in org projects via WebSocket connections.
"""

from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase

from backend.asgi import application
from pages.tests.factories import PageFactory, ProjectFactory, UserFactory
from users.tests.factories import OrgFactory, OrgMemberFactory

User = get_user_model()


class TestWebSocketOrgAccess(TransactionTestCase):
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

        # Org member (not page editor) connects
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

    async def test_external_user_can_join_shared_org_page(self):
        """Test that external users can connect when explicitly shared."""
        # Create org with member
        org = await sync_to_async(OrgFactory.create)()
        member = await sync_to_async(UserFactory.create)()
        external_user = await sync_to_async(UserFactory.create)()

        await sync_to_async(OrgMemberFactory.create)(org=org, user=member, role="member")

        # Create project and page
        project = await sync_to_async(ProjectFactory.create)(org=org, creator=member)
        page = await sync_to_async(PageFactory.create)(project=project, creator=member)

        # Share page with external user
        await sync_to_async(page.editors.add)(external_user)

        # External user connects
        communicator = WebsocketCommunicator(
            application,
            f"/ws/pages/{page.external_id}/",
        )
        communicator.scope["user"] = external_user

        connected, _ = await communicator.connect()
        self.assertTrue(connected, "External user should be able to connect to shared page")

        await communicator.disconnect()

    async def test_org_member_keeps_access_after_removed_as_editor(self):
        """Test that org members retain access even if removed as page editor."""
        # Create org with member
        org = await sync_to_async(OrgFactory.create)()
        admin = await sync_to_async(UserFactory.create)()
        member = await sync_to_async(UserFactory.create)()

        await sync_to_async(OrgMemberFactory.create)(org=org, user=admin, role="admin")
        await sync_to_async(OrgMemberFactory.create)(org=org, user=member, role="member")

        # Create project and page
        project = await sync_to_async(ProjectFactory.create)(org=org, creator=admin)
        page = await sync_to_async(PageFactory.create)(project=project, creator=admin)

        # Add member as explicit editor
        await sync_to_async(page.editors.add)(member)

        # Remove member as editor
        await sync_to_async(page.editors.remove)(member)

        # Member should still be able to connect (via org access)
        communicator = WebsocketCommunicator(
            application,
            f"/ws/pages/{page.external_id}/",
        )
        communicator.scope["user"] = member

        connected, _ = await communicator.connect()
        self.assertTrue(
            connected, "Org member should retain access via org membership after being removed as page editor"
        )

        await communicator.disconnect()

    async def test_user_with_both_access_types_can_join(self):
        """Test that user with both org and page-level access can connect."""
        # Create org with member
        org = await sync_to_async(OrgFactory.create)()
        member = await sync_to_async(UserFactory.create)()

        await sync_to_async(OrgMemberFactory.create)(org=org, user=member, role="member")

        # Create project and page
        project = await sync_to_async(ProjectFactory.create)(org=org, creator=member)
        page = await sync_to_async(PageFactory.create)(project=project, creator=member)

        # Also add as explicit editor (dual access)
        await sync_to_async(page.editors.add)(member)

        # Member connects (has both org and page access)
        communicator = WebsocketCommunicator(
            application,
            f"/ws/pages/{page.external_id}/",
        )
        communicator.scope["user"] = member

        connected, _ = await communicator.connect()
        self.assertTrue(connected, "User with both access types should be able to connect")

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

    async def test_page_without_project_uses_editor_only_access(self):
        """Test that pages without projects fall back to editor-only access."""
        # Create org with member
        org = await sync_to_async(OrgFactory.create)()
        member = await sync_to_async(UserFactory.create)()
        external_user = await sync_to_async(UserFactory.create)()

        await sync_to_async(OrgMemberFactory.create)(org=org, user=member, role="member")

        # Create orphan page (no project)
        page = await sync_to_async(PageFactory.create)(project=None, creator=member)
        await sync_to_async(page.editors.add)(external_user)

        # Org member has NO access (no project = no org access)
        comm_member = WebsocketCommunicator(
            application,
            f"/ws/pages/{page.external_id}/",
        )
        comm_member.scope["user"] = member

        # External editor has access
        comm_external = WebsocketCommunicator(
            application,
            f"/ws/pages/{page.external_id}/",
        )
        comm_external.scope["user"] = external_user

        # Note: Member is the creator, so they should still have access via editors
        # Let's adjust this - create page with different creator
        creator = await sync_to_async(UserFactory.create)()
        page = await sync_to_async(PageFactory.create)(project=None, creator=creator)
        await sync_to_async(page.editors.add)(external_user)

        # Now test - org member has NO access
        comm_member = WebsocketCommunicator(
            application,
            f"/ws/pages/{page.external_id}/",
        )
        comm_member.scope["user"] = member

        connected_member, _ = await comm_member.connect()
        self.assertFalse(
            connected_member, "Org member should NOT have access to orphan page (no project = no org access)"
        )

        # External editor has access
        comm_external = WebsocketCommunicator(
            application,
            f"/ws/pages/{page.external_id}/",
        )
        comm_external.scope["user"] = external_user

        connected_external, _ = await comm_external.connect()
        self.assertTrue(connected_external, "External editor should have access to orphan page")

        await comm_external.disconnect()
