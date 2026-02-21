from http import HTTPStatus

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.tests.common import BaseAuthenticatedViewTestCase
from pages.models import Page, PageMention, Project
from pages.tests.factories import PageFactory, ProjectFactory
from users.constants import OrgMemberRole
from users.models import Org
from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory


User = get_user_model()


class PageMentionModelTests(TestCase):
    """Tests for the PageMention model and sync_mentions_for_page method."""

    def setUp(self):
        self.user1 = User.objects.create_user(
            email="user1@example.com",
            username="user1",
            password="testpass123",
        )
        self.user2 = User.objects.create_user(
            email="user2@example.com",
            username="user2",
            password="testpass123",
        )
        self.user3 = User.objects.create_user(
            email="user3@example.com",
            username="user3",
            password="testpass123",
        )
        self.org = Org.objects.create(name="Test Org")
        self.org.members.add(self.user1)
        self.org.members.add(self.user2)
        self.org.members.add(self.user3)
        self.project = Project.objects.create(
            name="Test Project",
            org=self.org,
            creator=self.user1,
        )
        self.page = Page.objects.create_with_owner(
            user=self.user1,
            project=self.project,
            title="Test Page",
        )

    def test_sync_mentions_creates_mentions(self):
        """sync_mentions_for_page creates PageMention records for @mentions."""
        content = f"Hey @[user2](@{self.user2.external_id}) can you review this?"

        created, changed = PageMention.objects.sync_mentions_for_page(self.page, content)

        self.assertTrue(changed)
        self.assertEqual(PageMention.objects.count(), 1)
        mention = PageMention.objects.first()
        self.assertEqual(mention.source_page, self.page)
        self.assertEqual(mention.mentioned_user, self.user2)

    def test_sync_mentions_creates_multiple_mentions(self):
        """sync_mentions_for_page creates mentions for multiple users."""
        content = f"Hey @[user2](@{self.user2.external_id}) and @[user3](@{self.user3.external_id})!"

        created, changed = PageMention.objects.sync_mentions_for_page(self.page, content)

        self.assertTrue(changed)
        self.assertEqual(PageMention.objects.count(), 2)
        mentioned_users = set(PageMention.objects.values_list("mentioned_user_id", flat=True))
        self.assertEqual(mentioned_users, {self.user2.id, self.user3.id})

    def test_sync_mentions_removes_old_mentions(self):
        """sync_mentions_for_page removes mentions that are no longer in content."""
        content1 = f"Hey @[user2](@{self.user2.external_id})!"
        PageMention.objects.sync_mentions_for_page(self.page, content1)
        self.assertEqual(PageMention.objects.count(), 1)

        content2 = "No mentions here"
        created, changed = PageMention.objects.sync_mentions_for_page(self.page, content2)

        self.assertTrue(changed)
        self.assertEqual(PageMention.objects.count(), 0)

    def test_sync_mentions_updates_mentions(self):
        """sync_mentions_for_page adds and removes mentions correctly."""
        content1 = f"Hey @[user2](@{self.user2.external_id})!"
        PageMention.objects.sync_mentions_for_page(self.page, content1)
        self.assertEqual(PageMention.objects.count(), 1)

        # Change to mention user3 instead of user2
        content2 = f"Hey @[user3](@{self.user3.external_id})!"
        created, changed = PageMention.objects.sync_mentions_for_page(self.page, content2)

        self.assertTrue(changed)
        self.assertEqual(PageMention.objects.count(), 1)
        mention = PageMention.objects.first()
        self.assertEqual(mention.mentioned_user, self.user3)

    def test_sync_mentions_ignores_invalid_user_ids(self):
        """sync_mentions_for_page ignores mentions with invalid user IDs."""
        content = "Hey @[nobody](@invalid_id_12345)!"

        created, changed = PageMention.objects.sync_mentions_for_page(self.page, content)

        self.assertFalse(changed)
        self.assertEqual(PageMention.objects.count(), 0)

    def test_sync_mentions_deduplicates_same_user(self):
        """sync_mentions_for_page only creates one mention per user per page."""
        content = f"Hey @[user2](@{self.user2.external_id}) and also @[user2](@{self.user2.external_id}) again!"

        created, changed = PageMention.objects.sync_mentions_for_page(self.page, content)

        self.assertTrue(changed)
        self.assertEqual(PageMention.objects.count(), 1)

    def test_sync_mentions_returns_changed_false_when_unchanged(self):
        """sync_mentions_for_page returns changed=False when mentions are unchanged."""
        content = f"Hey @[user2](@{self.user2.external_id})!"

        _, changed1 = PageMention.objects.sync_mentions_for_page(self.page, content)
        self.assertTrue(changed1)

        _, changed2 = PageMention.objects.sync_mentions_for_page(self.page, content)
        self.assertFalse(changed2)

    def test_sync_mentions_self_mention_allowed(self):
        """sync_mentions_for_page allows users to mention themselves."""
        content = f"Note to self: @[user1](@{self.user1.external_id})"

        created, changed = PageMention.objects.sync_mentions_for_page(self.page, content)

        self.assertTrue(changed)
        self.assertEqual(PageMention.objects.count(), 1)
        mention = PageMention.objects.first()
        self.assertEqual(mention.mentioned_user, self.user1)

    def test_sync_mentions_empty_content(self):
        """sync_mentions_for_page handles empty content gracefully."""
        content = ""

        created, changed = PageMention.objects.sync_mentions_for_page(self.page, content)

        self.assertFalse(changed)
        self.assertEqual(PageMention.objects.count(), 0)

    def test_sync_mentions_partial_format_ignored(self):
        """sync_mentions_for_page ignores incomplete mention formats."""
        test_cases = [
            "@user2",  # Missing brackets
            "@[user2]",  # Missing (id)
            "(user2)",  # Missing @[name]
            "[@user2](id)",  # Wrong bracket placement
        ]

        for content in test_cases:
            with self.subTest(content=content):
                PageMention.objects.all().delete()
                created, changed = PageMention.objects.sync_mentions_for_page(self.page, content)
                self.assertEqual(PageMention.objects.count(), 0, f"Should not match: {content}")


class PageMentionsAPITests(BaseAuthenticatedViewTestCase):
    """Tests for GET /api/mentions/ endpoint."""

    @classmethod
    def setUpTestData(cls):
        cls.user = UserFactory(username="testuser", email="testuser@example.com")
        cls.user2 = UserFactory(username="otheruser", email="otheruser@example.com")
        cls.user3 = UserFactory(username="thirduser", email="thirduser@example.com")

        cls.org = OrgFactory()
        OrgMemberFactory(org=cls.org, user=cls.user)
        OrgMemberFactory(org=cls.org, user=cls.user2)
        OrgMemberFactory(org=cls.org, user=cls.user3)

        cls.project = ProjectFactory(org=cls.org, creator=cls.user)

    def test_get_mentions_returns_empty_list_when_no_mentions(self):
        """User with no mentions should see empty list."""
        response = self.send_api_request(url="/api/mentions/", method="get")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(data["mentions"], [])

    def test_get_mentions_returns_user_mentions(self):
        """User should see pages where they are mentioned."""
        page = PageFactory(project=self.project, creator=self.user2, title="Meeting Notes")
        PageMention.objects.create(source_page=page, mentioned_user=self.user)

        response = self.send_api_request(url="/api/mentions/", method="get")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(len(data["mentions"]), 1)
        self.assertEqual(data["mentions"][0]["page_external_id"], page.external_id)
        self.assertEqual(data["mentions"][0]["page_title"], "Meeting Notes")
        self.assertEqual(data["mentions"][0]["project_name"], self.project.name)

    def test_get_mentions_excludes_other_users_mentions(self):
        """User should not see mentions belonging to other users."""
        page = PageFactory(project=self.project, creator=self.user2, title="Meeting Notes")
        # Mention user3, not the logged-in user
        PageMention.objects.create(source_page=page, mentioned_user=self.user3)

        response = self.send_api_request(url="/api/mentions/", method="get")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(data["mentions"], [])

    def test_get_mentions_excludes_deleted_pages(self):
        """Mentions in soft-deleted pages should not appear."""
        page = PageFactory(project=self.project, creator=self.user2, title="Deleted Page")
        PageMention.objects.create(source_page=page, mentioned_user=self.user)
        page.is_deleted = True
        page.save()

        response = self.send_api_request(url="/api/mentions/", method="get")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(data["mentions"], [])

    def test_get_mentions_excludes_pages_in_deleted_projects(self):
        """Mentions in pages from soft-deleted projects should not appear."""
        deleted_project = ProjectFactory(org=self.org, creator=self.user2, is_deleted=True)
        page = PageFactory(project=deleted_project, creator=self.user2, title="Page in Deleted")
        PageMention.objects.create(source_page=page, mentioned_user=self.user)

        response = self.send_api_request(url="/api/mentions/", method="get")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(data["mentions"], [])

    def test_get_mentions_ordered_by_modified_desc(self):
        """Mentions should be ordered by page modified date, most recent first."""
        from django.utils import timezone
        from datetime import timedelta

        page1 = PageFactory(project=self.project, creator=self.user2, title="Old Page")
        page2 = PageFactory(project=self.project, creator=self.user2, title="New Page")

        PageMention.objects.create(source_page=page1, mentioned_user=self.user)
        PageMention.objects.create(source_page=page2, mentioned_user=self.user)

        # Make page1 older
        Page.objects.filter(pk=page1.pk).update(modified=timezone.now() - timedelta(days=1))

        response = self.send_api_request(url="/api/mentions/", method="get")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(len(data["mentions"]), 2)
        self.assertEqual(data["mentions"][0]["page_title"], "New Page")
        self.assertEqual(data["mentions"][1]["page_title"], "Old Page")

    def test_get_mentions_requires_authentication(self):
        """Unauthenticated requests should be rejected."""
        self.client.logout()

        response = self.send_api_request(url="/api/mentions/", method="get")

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)

    def test_get_mentions_handles_untitled_pages(self):
        """Pages without titles should show 'Untitled'."""
        page = PageFactory(project=self.project, creator=self.user2, title="")
        PageMention.objects.create(source_page=page, mentioned_user=self.user)

        response = self.send_api_request(url="/api/mentions/", method="get")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(len(data["mentions"]), 1)
        self.assertEqual(data["mentions"][0]["page_title"], "Untitled")


class OrgMembersAutocompleteAPITests(BaseAuthenticatedViewTestCase):
    """Tests for GET /api/orgs/{id}/members/autocomplete/ endpoint."""

    @classmethod
    def setUpTestData(cls):
        cls.user = UserFactory(username="testuser", email="testuser@example.com")
        cls.user2 = UserFactory(username="alice", email="alice@example.com")
        cls.user3 = UserFactory(username="bob", email="bob@example.com")
        cls.user4 = UserFactory(username="charlie", email="charlie@example.com")
        cls.outsider = UserFactory(username="outsider", email="outsider@example.com")

        cls.org = OrgFactory()
        OrgMemberFactory(org=cls.org, user=cls.user, role=OrgMemberRole.ADMIN.value)
        OrgMemberFactory(org=cls.org, user=cls.user2)
        OrgMemberFactory(org=cls.org, user=cls.user3)
        OrgMemberFactory(org=cls.org, user=cls.user4)

        cls.other_org = OrgFactory()
        OrgMemberFactory(org=cls.other_org, user=cls.outsider)

    def test_autocomplete_returns_all_members_without_query(self):
        """Should return all org members when no query is provided."""
        response = self.client.get(f"/api/orgs/{self.org.external_id}/members/autocomplete/")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(len(data["members"]), 4)
        usernames = {m["username"] for m in data["members"]}
        self.assertEqual(usernames, {"testuser", "alice", "bob", "charlie"})

    def test_autocomplete_filters_by_username(self):
        """Should filter members by username."""
        response = self.client.get(f"/api/orgs/{self.org.external_id}/members/autocomplete/?q=ali")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(len(data["members"]), 1)
        self.assertEqual(data["members"][0]["username"], "alice")

    def test_autocomplete_filters_by_email(self):
        """Should filter members by email."""
        response = self.client.get(f"/api/orgs/{self.org.external_id}/members/autocomplete/?q=bob@")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(len(data["members"]), 1)
        self.assertEqual(data["members"][0]["username"], "bob")

    def test_autocomplete_is_case_insensitive(self):
        """Search should be case-insensitive."""
        response = self.client.get(f"/api/orgs/{self.org.external_id}/members/autocomplete/?q=ALICE")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(len(data["members"]), 1)
        self.assertEqual(data["members"][0]["username"], "alice")

    def test_autocomplete_requires_org_membership(self):
        """Non-members should not be able to access autocomplete."""
        response = self.client.get(f"/api/orgs/{self.other_org.external_id}/members/autocomplete/")

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_autocomplete_returns_404_for_invalid_org(self):
        """Invalid org ID should return 404."""
        response = self.client.get("/api/orgs/invalid_org_id/members/autocomplete/")

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_autocomplete_requires_authentication(self):
        """Unauthenticated requests should be rejected."""
        self.client.logout()

        response = self.client.get(f"/api/orgs/{self.org.external_id}/members/autocomplete/")

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)

    def test_autocomplete_limits_results_to_10(self):
        """Should return maximum of 10 results."""
        # Add more users to org (already have 4)
        for i in range(10):
            user = UserFactory(username=f"extra{i}", email=f"extra{i}@example.com")
            OrgMemberFactory(org=self.org, user=user)

        response = self.client.get(f"/api/orgs/{self.org.external_id}/members/autocomplete/")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(len(data["members"]), 10)

    def test_autocomplete_returns_correct_fields(self):
        """Should return external_id, username, and email for each member."""
        response = self.client.get(f"/api/orgs/{self.org.external_id}/members/autocomplete/?q=alice")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(len(data["members"]), 1)
        member = data["members"][0]
        self.assertIn("external_id", member)
        self.assertIn("username", member)
        self.assertIn("email", member)
        self.assertEqual(member["username"], "alice")
        self.assertEqual(member["email"], "alice@example.com")
        self.assertEqual(member["external_id"], str(self.user2.external_id))

    def test_autocomplete_empty_query_string(self):
        """Empty query string should return all members."""
        response = self.client.get(f"/api/orgs/{self.org.external_id}/members/autocomplete/?q=")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(len(data["members"]), 4)

    def test_autocomplete_no_matches(self):
        """Query with no matches should return empty list."""
        response = self.client.get(f"/api/orgs/{self.org.external_id}/members/autocomplete/?q=nonexistent")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(data["members"], [])

    def test_autocomplete_does_not_expose_outsiders(self):
        """Should not return users from other orgs."""
        response = self.client.get(f"/api/orgs/{self.org.external_id}/members/autocomplete/?q=outsider")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(data["members"], [])


class MentionsAccessControlTests(BaseAuthenticatedViewTestCase):
    """Tests for access control in GET /api/mentions/ endpoint.

    Verifies that users only see mentions from pages they have access to,
    and that revoking access properly filters out mentions.
    """

    @classmethod
    def setUpTestData(cls):
        cls.user = UserFactory(username="testuser", email="testuser@example.com")
        cls.user2 = UserFactory(username="pageowner", email="pageowner@example.com")
        cls.outsider = UserFactory(username="outsider", email="outsider@example.com")

        cls.org = OrgFactory()
        OrgMemberFactory(org=cls.org, user=cls.user)
        OrgMemberFactory(org=cls.org, user=cls.user2)

        cls.project = ProjectFactory(org=cls.org, creator=cls.user2)

    def test_mentions_filtered_by_page_access(self):
        """User should not see mentions from pages they cannot access."""
        # Create a page and mention the outsider (who is NOT an org member)
        page = PageFactory(project=self.project, creator=self.user2, title="Team Meeting")
        PageMention.objects.create(source_page=page, mentioned_user=self.outsider)

        # Log in as the outsider
        self.client.force_login(self.outsider)
        response = self.client.get("/api/mentions/")

        # Outsider should NOT see the mention (no access to the page)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(data["mentions"], [])
        self.assertEqual(data["total"], 0)

    def test_mentions_visible_when_user_has_access(self):
        """User should see mentions from pages they have access to."""
        page = PageFactory(project=self.project, creator=self.user2, title="Team Meeting")
        PageMention.objects.create(source_page=page, mentioned_user=self.user)

        response = self.send_api_request(url="/api/mentions/", method="get")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(len(data["mentions"]), 1)
        self.assertEqual(data["mentions"][0]["page_title"], "Team Meeting")

    def test_mentions_hidden_after_org_access_revoked(self):
        """Mentions should disappear when user loses org access."""
        from users.models import OrgMember

        # Create a temporary user and add to org
        temp_user = UserFactory(username="tempuser", email="temp@example.com")
        OrgMemberFactory(org=self.org, user=temp_user)

        # Create a page and mention the temp user
        page = PageFactory(project=self.project, creator=self.user2, title="Project Notes")
        PageMention.objects.create(source_page=page, mentioned_user=temp_user)

        # Verify temp user can see the mention
        self.client.force_login(temp_user)
        response = self.client.get("/api/mentions/")
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(len(data["mentions"]), 1)

        # Revoke org access
        OrgMember.objects.filter(org=self.org, user=temp_user).delete()

        # Verify temp user can NO longer see the mention
        response = self.client.get("/api/mentions/")
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(data["mentions"], [])
        self.assertEqual(data["total"], 0)

    def test_mentions_from_multiple_orgs_filtered_correctly(self):
        """User should only see mentions from orgs they belong to."""
        # Create a second org that the user is NOT a member of
        other_org = OrgFactory()
        OrgMemberFactory(org=other_org, user=self.user2)
        other_project = ProjectFactory(org=other_org, creator=self.user2)

        # Create pages in both orgs
        page_accessible = PageFactory(project=self.project, creator=self.user2, title="My Org Page")
        page_inaccessible = PageFactory(project=other_project, creator=self.user2, title="Other Org Page")

        # Mention user in both pages
        PageMention.objects.create(source_page=page_accessible, mentioned_user=self.user)
        PageMention.objects.create(source_page=page_inaccessible, mentioned_user=self.user)

        response = self.send_api_request(url="/api/mentions/", method="get")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        # Should only see the mention from the org they belong to
        self.assertEqual(len(data["mentions"]), 1)
        self.assertEqual(data["mentions"][0]["page_title"], "My Org Page")
        self.assertEqual(data["total"], 1)


class MentionsPaginationTests(BaseAuthenticatedViewTestCase):
    """Tests for pagination in GET /api/mentions/ endpoint."""

    @classmethod
    def setUpTestData(cls):
        cls.user = UserFactory(username="testuser", email="testuser@example.com")
        cls.user2 = UserFactory(username="pageowner", email="pageowner@example.com")

        cls.org = OrgFactory()
        OrgMemberFactory(org=cls.org, user=cls.user)
        OrgMemberFactory(org=cls.org, user=cls.user2)

        cls.project = ProjectFactory(org=cls.org, creator=cls.user2)

    def test_pagination_default_limit(self):
        """Default limit should be 50."""
        # Create 60 mentions
        for i in range(60):
            page = PageFactory(project=self.project, creator=self.user2, title=f"Page {i}")
            PageMention.objects.create(source_page=page, mentioned_user=self.user)

        response = self.send_api_request(url="/api/mentions/", method="get")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(len(data["mentions"]), 50)
        self.assertEqual(data["total"], 60)
        self.assertTrue(data["has_more"])

    def test_pagination_custom_limit(self):
        """Custom limit should be respected."""
        for i in range(10):
            page = PageFactory(project=self.project, creator=self.user2, title=f"Page {i}")
            PageMention.objects.create(source_page=page, mentioned_user=self.user)

        response = self.send_api_request(url="/api/mentions/?limit=5", method="get")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(len(data["mentions"]), 5)
        self.assertEqual(data["total"], 10)
        self.assertTrue(data["has_more"])

    def test_pagination_offset(self):
        """Offset should skip results correctly."""
        from django.utils import timezone
        from datetime import timedelta

        # Create 5 pages with distinct modified times
        pages = []
        for i in range(5):
            page = PageFactory(project=self.project, creator=self.user2, title=f"Page {i}")
            PageMention.objects.create(source_page=page, mentioned_user=self.user)
            pages.append(page)

        # Set modified times to ensure consistent ordering (newest first)
        for i, page in enumerate(pages):
            Page.objects.filter(pk=page.pk).update(modified=timezone.now() - timedelta(hours=i))

        # Get pages with offset
        response = self.send_api_request(url="/api/mentions/?limit=2&offset=2", method="get")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(len(data["mentions"]), 2)
        self.assertEqual(data["total"], 5)
        self.assertTrue(data["has_more"])  # 2 + 2 < 5
        # Should get pages 2 and 3 (0-indexed after ordering)
        self.assertEqual(data["mentions"][0]["page_title"], "Page 2")
        self.assertEqual(data["mentions"][1]["page_title"], "Page 3")

    def test_pagination_has_more_false_at_end(self):
        """has_more should be false when at end of results."""
        for i in range(3):
            page = PageFactory(project=self.project, creator=self.user2, title=f"Page {i}")
            PageMention.objects.create(source_page=page, mentioned_user=self.user)

        response = self.send_api_request(url="/api/mentions/?limit=5", method="get")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(len(data["mentions"]), 3)
        self.assertEqual(data["total"], 3)
        self.assertFalse(data["has_more"])

    def test_pagination_offset_beyond_results(self):
        """Offset beyond total results should return empty list."""
        for i in range(3):
            page = PageFactory(project=self.project, creator=self.user2, title=f"Page {i}")
            PageMention.objects.create(source_page=page, mentioned_user=self.user)

        response = self.send_api_request(url="/api/mentions/?offset=100", method="get")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(data["mentions"], [])
        self.assertEqual(data["total"], 3)
        self.assertFalse(data["has_more"])
