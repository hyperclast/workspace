from django.db import IntegrityError
from django.test import TestCase

from users.constants import OrgMemberRole
from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory


class TestOrgMemberModel(TestCase):
    """Test OrgMember model instance methods and properties."""

    def test_org_member_creation(self):
        """Test that org member can be created with basic fields."""
        org = OrgFactory()
        user = UserFactory()
        member = OrgMemberFactory(org=org, user=user, role=OrgMemberRole.ADMIN.value)

        self.assertIsNotNone(member.id)
        self.assertEqual(member.org, org)
        self.assertEqual(member.user, user)
        self.assertEqual(member.role, OrgMemberRole.ADMIN.value)
        self.assertIsNotNone(member.created)
        self.assertIsNotNone(member.modified)

    def test_default_role_is_member(self):
        """Test that default role is MEMBER."""
        member = OrgMemberFactory()

        self.assertEqual(member.role, OrgMemberRole.MEMBER.value)

    def test_role_choices(self):
        """Test that all role choices can be assigned."""
        org = OrgFactory()
        user1 = UserFactory()
        user2 = UserFactory()

        admin = OrgMemberFactory(org=org, user=user1, role=OrgMemberRole.ADMIN.value)
        member = OrgMemberFactory(org=org, user=user2, role=OrgMemberRole.MEMBER.value)

        self.assertEqual(admin.role, OrgMemberRole.ADMIN.value)
        self.assertEqual(member.role, OrgMemberRole.MEMBER.value)

    def test_unique_constraint_org_user(self):
        """Test that a user can only have one membership per org."""
        org = OrgFactory()
        user = UserFactory()

        OrgMemberFactory(org=org, user=user)

        with self.assertRaises(IntegrityError):
            OrgMemberFactory(org=org, user=user)

    def test_user_can_belong_to_multiple_orgs(self):
        """Test that a user can be a member of multiple organizations."""
        user = UserFactory()
        org1 = OrgFactory()
        org2 = OrgFactory()

        member1 = OrgMemberFactory(org=org1, user=user)
        member2 = OrgMemberFactory(org=org2, user=user)

        self.assertEqual(member1.user, user)
        self.assertEqual(member2.user, user)
        self.assertNotEqual(member1.org, member2.org)

    def test_org_can_have_multiple_members(self):
        """Test that an org can have multiple members."""
        org = OrgFactory()
        user1 = UserFactory()
        user2 = UserFactory()
        user3 = UserFactory()

        OrgMemberFactory(org=org, user=user1)
        OrgMemberFactory(org=org, user=user2)
        OrgMemberFactory(org=org, user=user3)

        members = org.orgmember_set.all()
        self.assertEqual(members.count(), 3)

    def test_str_representation(self):
        """Test string representation of org member."""
        org = OrgFactory(name="Test Org")
        user = UserFactory(email="test@example.com")
        member = OrgMemberFactory(org=org, user=user)

        str_repr = str(member)

        self.assertIn("Test Org", str_repr)
        # User's string representation is included
        self.assertIn(str(user), str_repr)

    def test_cascade_delete_org(self):
        """Test that deleting org cascades to org members."""
        org = OrgFactory()
        user = UserFactory()
        member = OrgMemberFactory(org=org, user=user)
        member_id = member.id

        org.delete()

        # Verify member was deleted
        from users.models import OrgMember

        self.assertFalse(OrgMember.objects.filter(id=member_id).exists())

    def test_cascade_delete_user(self):
        """Test that deleting user cascades to org members."""
        org = OrgFactory()
        user = UserFactory()
        member = OrgMemberFactory(org=org, user=user)
        member_id = member.id

        user.delete()

        # Verify member was deleted
        from users.models import OrgMember

        self.assertFalse(OrgMember.objects.filter(id=member_id).exists())

    def test_timestamped_fields(self):
        """Test that created and modified timestamps are set correctly."""
        member = OrgMemberFactory()

        self.assertIsNotNone(member.created)
        self.assertIsNotNone(member.modified)
        self.assertGreaterEqual(member.modified, member.created)

    def test_modified_updates_on_save(self):
        """Test that modified timestamp updates when member is saved."""
        member = OrgMemberFactory(role=OrgMemberRole.MEMBER.value)
        original_modified = member.modified

        member.role = OrgMemberRole.ADMIN.value
        member.save()

        self.assertGreater(member.modified, original_modified)

    def test_role_can_be_updated(self):
        """Test that member role can be changed."""
        member = OrgMemberFactory(role=OrgMemberRole.MEMBER.value)

        self.assertEqual(member.role, OrgMemberRole.MEMBER.value)

        member.role = OrgMemberRole.ADMIN.value
        member.save()
        member.refresh_from_db()

        self.assertEqual(member.role, OrgMemberRole.ADMIN.value)

    def test_filtering_by_role(self):
        """Test that members can be filtered by role."""
        org = OrgFactory()
        admin_user = UserFactory()
        member_user1 = UserFactory()
        member_user2 = UserFactory()

        OrgMemberFactory(org=org, user=admin_user, role=OrgMemberRole.ADMIN.value)
        OrgMemberFactory(org=org, user=member_user1, role=OrgMemberRole.MEMBER.value)
        OrgMemberFactory(org=org, user=member_user2, role=OrgMemberRole.MEMBER.value)

        from users.models import OrgMember

        admins = OrgMember.objects.filter(org=org, role=OrgMemberRole.ADMIN.value)
        members = OrgMember.objects.filter(org=org, role=OrgMemberRole.MEMBER.value)

        self.assertEqual(admins.count(), 1)
        self.assertEqual(members.count(), 2)
        self.assertEqual(admins.first().user, admin_user)

    def test_access_via_org_members_relationship(self):
        """Test accessing members through org.members ManyToMany field."""
        org = OrgFactory()
        user1 = UserFactory()
        user2 = UserFactory()

        OrgMemberFactory(org=org, user=user1)
        OrgMemberFactory(org=org, user=user2)

        # Access via ManyToMany 'members' field
        org_members = org.members.all()

        self.assertEqual(org_members.count(), 2)
        self.assertIn(user1, org_members)
        self.assertIn(user2, org_members)
