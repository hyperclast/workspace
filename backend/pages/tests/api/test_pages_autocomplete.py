from http import HTTPStatus

from core.tests.common import BaseAuthenticatedViewTestCase
from pages.tests.factories import PageFactory, ProjectFactory
from users.tests.factories import UserFactory


class TestPagesAutocompleteAPI(BaseAuthenticatedViewTestCase):
    """Test GET /api/pages/autocomplete/ endpoint."""

    def send_autocomplete_request(self, query=""):
        """Helper to send autocomplete request."""
        url = f"/api/pages/autocomplete/?q={query}"
        return self.send_api_request(url=url, method="get")

    def test_autocomplete_with_empty_query_returns_all_pages(self):
        """Test autocomplete with empty query returns all user's pages (up to 10)."""
        # Create 5 pages for the user
        pages = [PageFactory(creator=self.user, title=f"Page {i}") for i in range(5)]

        response = self.send_autocomplete_request("")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("pages", payload)
        self.assertEqual(len(payload["pages"]), 5)

        # Verify all pages are present
        returned_ids = {page["external_id"] for page in payload["pages"]}
        expected_ids = {str(page.external_id) for page in pages}
        self.assertEqual(returned_ids, expected_ids)

    def test_autocomplete_with_query_filters_by_title(self):
        """Test autocomplete filters pages by title (case-insensitive)."""
        # Create pages with different titles
        PageFactory(creator=self.user, title="Python Tutorial")
        PageFactory(creator=self.user, title="JavaScript Guide")
        PageFactory(creator=self.user, title="Python Best Practices")
        PageFactory(creator=self.user, title="Django Documentation")

        response = self.send_autocomplete_request("python")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(len(payload["pages"]), 2)

        # Verify only Python-related pages are returned
        titles = {page["title"] for page in payload["pages"]}
        self.assertEqual(titles, {"Python Tutorial", "Python Best Practices"})

    def test_autocomplete_case_insensitive_search(self):
        """Test autocomplete search is case-insensitive."""
        PageFactory(creator=self.user, title="Meeting Pages")
        PageFactory(creator=self.user, title="MEETING AGENDA")
        PageFactory(creator=self.user, title="Daily Standup")

        # Search with lowercase
        response = self.send_autocomplete_request("meeting")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(len(payload["pages"]), 2)

        titles = {page["title"] for page in payload["pages"]}
        self.assertEqual(titles, {"Meeting Pages", "MEETING AGENDA"})

    def test_autocomplete_limits_results_to_10(self):
        """Test autocomplete returns maximum of 10 results."""
        # Create 15 pages all matching the query
        pages = [PageFactory(creator=self.user, title=f"Project Page {i}") for i in range(15)]

        response = self.send_autocomplete_request("Project")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(len(payload["pages"]), 10)

    def test_autocomplete_orders_by_most_recently_updated(self):
        """Test autocomplete returns pages ordered by most recently updated first."""
        # Create pages with specific update times
        page1 = PageFactory(creator=self.user, title="Old Page")
        page2 = PageFactory(creator=self.user, title="Middle Page")
        page3 = PageFactory(creator=self.user, title="Recent Page")

        # Manually update the 'updated' field to control ordering
        # (Page3 should be most recent)
        Page = page1.__class__
        from django.utils import timezone
        from datetime import timedelta

        now = timezone.now()
        Page.objects.filter(pk=page1.pk).update(updated=now - timedelta(days=2))
        Page.objects.filter(pk=page2.pk).update(updated=now - timedelta(days=1))
        Page.objects.filter(pk=page3.pk).update(updated=now)

        response = self.send_autocomplete_request("")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(len(payload["pages"]), 3)

        # Verify order: most recent first
        returned_ids = [page["external_id"] for page in payload["pages"]]
        self.assertEqual(returned_ids[0], str(page3.external_id))
        self.assertEqual(returned_ids[1], str(page2.external_id))
        self.assertEqual(returned_ids[2], str(page1.external_id))

    def test_autocomplete_only_returns_user_editable_pages(self):
        """Test autocomplete only returns pages the user can edit."""
        # Create pages for current user
        user_page1 = PageFactory(creator=self.user, title="My Page 1")
        user_page2 = PageFactory(creator=self.user, title="My Page 2")

        # Create pages for another user
        other_user = UserFactory()
        other_page = PageFactory(creator=other_user, title="Other User Page")

        response = self.send_autocomplete_request("")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(len(payload["pages"]), 2)

        # Verify only current user's pages are returned
        returned_ids = {page["external_id"] for page in payload["pages"]}
        self.assertEqual(returned_ids, {str(user_page1.external_id), str(user_page2.external_id)})
        self.assertNotIn(str(other_page.external_id), returned_ids)

    def test_autocomplete_includes_shared_pages(self):
        """Test autocomplete includes pages shared with the user (as editor)."""
        # Create a page owned by another user
        other_user = UserFactory()
        shared_page = PageFactory(creator=other_user, title="Shared Page")

        # Add current user as editor
        shared_page.editors.add(self.user)

        # Create a page owned by current user
        own_page = PageFactory(creator=self.user, title="Own Page")

        response = self.send_autocomplete_request("")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(len(payload["pages"]), 2)

        # Verify both own and shared pages are returned
        returned_ids = {page["external_id"] for page in payload["pages"]}
        self.assertEqual(returned_ids, {str(own_page.external_id), str(shared_page.external_id)})

    def test_autocomplete_returns_expected_fields(self):
        """Test autocomplete returns all expected fields for each page."""
        page = PageFactory(creator=self.user, title="Test Page")

        response = self.send_autocomplete_request("")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(len(payload["pages"]), 1)

        page_data = payload["pages"][0]

        # Verify all expected fields are present
        self.assertIn("external_id", page_data)
        self.assertIn("title", page_data)
        self.assertIn("created", page_data)
        self.assertIn("modified", page_data)

        # updated is optional, but should be present in this case
        self.assertIn("updated", page_data)

        # Verify field values
        self.assertEqual(page_data["external_id"], str(page.external_id))
        self.assertEqual(page_data["title"], "Test Page")

    def test_autocomplete_with_no_matching_pages(self):
        """Test autocomplete with query that matches no pages returns empty list."""
        PageFactory(creator=self.user, title="Python Guide")
        PageFactory(creator=self.user, title="Django Tutorial")

        response = self.send_autocomplete_request("JavaScript")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("pages", payload)
        self.assertEqual(len(payload["pages"]), 0)

    def test_autocomplete_with_partial_match(self):
        """Test autocomplete matches partial title strings."""
        PageFactory(creator=self.user, title="Project Management Best Practices")
        PageFactory(creator=self.user, title="Time Management")
        PageFactory(creator=self.user, title="Project Planning")

        response = self.send_autocomplete_request("manage")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(len(payload["pages"]), 2)

        titles = {page["title"] for page in payload["pages"]}
        self.assertEqual(titles, {"Project Management Best Practices", "Time Management"})

    def test_unauthenticated_request_returns_401(self):
        """Test that unauthenticated requests are rejected."""
        self.client.logout()

        response = self.send_autocomplete_request("test")

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)

    def test_autocomplete_excludes_pages_from_deleted_projects(self):
        """Test autocomplete excludes pages from soft-deleted projects.

        BUG FIX: When a project is soft-deleted, its pages should not appear
        in autocomplete results even if the pages themselves are not deleted.
        """
        project = ProjectFactory(creator=self.user)
        project.org.members.add(self.user)

        page_in_deleted = PageFactory(creator=self.user, project=project, title="Page in Deleted Project")
        active_page = PageFactory(creator=self.user, title="Active Page")

        project.is_deleted = True
        project.save()

        response = self.send_autocomplete_request("")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        returned_ids = {page["external_id"] for page in payload["pages"]}
        self.assertNotIn(str(page_in_deleted.external_id), returned_ids)
        self.assertIn(str(active_page.external_id), returned_ids)
