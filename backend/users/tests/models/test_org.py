from django.db import IntegrityError
from django.test import TestCase

from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory


class TestOrgModel(TestCase):
    """Test Org model instance methods and properties."""

    def test_org_creation(self):
        """Test that org can be created with basic fields."""
        org = OrgFactory(name="Test Company")

        self.assertIsNotNone(org.id)
        self.assertIsNotNone(org.external_id)
        self.assertEqual(org.name, "Test Company")
        self.assertIsNotNone(org.created)
        self.assertIsNotNone(org.modified)

    def test_org_creation_without_name(self):
        """Test that org can be created without a name (blank=True)."""
        org = OrgFactory(name="")

        self.assertIsNotNone(org.id)
        self.assertEqual(org.name, "")

    def test_external_id_is_auto_generated(self):
        """Test that external_id is automatically generated and unique."""
        org1 = OrgFactory()
        org2 = OrgFactory()

        self.assertIsNotNone(org1.external_id)
        self.assertIsNotNone(org2.external_id)
        self.assertNotEqual(org1.external_id, org2.external_id)

    def test_domain_is_unique(self):
        """Test that domain must be unique."""
        domain = "example.com"
        OrgFactory(domain=domain)

        with self.assertRaises(IntegrityError):
            OrgFactory(domain=domain)

    def test_domain_can_be_null(self):
        """Test that multiple orgs can have null domain."""
        org1 = OrgFactory(domain=None)
        org2 = OrgFactory(domain=None)

        self.assertIsNone(org1.domain)
        self.assertIsNone(org2.domain)
        self.assertNotEqual(org1.id, org2.id)

    def test_str_representation_with_name(self):
        """Test string representation returns name when available."""
        org = OrgFactory(name="Acme Corp")

        self.assertEqual(str(org), "Acme Corp")

    def test_str_representation_without_name(self):
        """Test string representation returns external_id when name is blank."""
        org = OrgFactory(name="")

        self.assertEqual(str(org), org.external_id)

    def test_members_relationship(self):
        """Test many-to-many relationship with users through OrgMember."""
        org = OrgFactory()
        user1 = UserFactory()
        user2 = UserFactory()

        OrgMemberFactory(org=org, user=user1)
        OrgMemberFactory(org=org, user=user2)

        members = org.members.all()
        self.assertEqual(members.count(), 2)
        self.assertIn(user1, members)
        self.assertIn(user2, members)

    def test_reverse_relationship_from_user(self):
        """Test that users can access orgs they belong to via reverse relationship."""
        user = UserFactory()
        org1 = OrgFactory()
        org2 = OrgFactory()

        OrgMemberFactory(org=org1, user=user)
        OrgMemberFactory(org=org2, user=user)

        user_orgs = user.orgs.all()
        self.assertEqual(user_orgs.count(), 2)
        self.assertIn(org1, user_orgs)
        self.assertIn(org2, user_orgs)

    def test_timestamped_fields(self):
        """Test that created and modified timestamps are set correctly."""
        org = OrgFactory()

        self.assertIsNotNone(org.created)
        self.assertIsNotNone(org.modified)
        # Modified should be >= created
        self.assertGreaterEqual(org.modified, org.created)

    def test_modified_updates_on_save(self):
        """Test that modified timestamp updates when org is saved."""
        org = OrgFactory()
        original_modified = org.modified

        org.name = "Updated Name"
        org.save()

        self.assertGreater(org.modified, original_modified)

    def test_domain_default_is_none(self):
        """Test that domain defaults to None."""
        org = OrgFactory.build(domain=None)
        org.save()

        self.assertIsNone(org.domain)
