from datetime import timedelta
from http import HTTPStatus

from django.utils import timezone

from core.tests.common import BaseAuthenticatedViewTestCase
from pages.models import Page
from pages.tests.factories import PageFactory, ProjectFactory
from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory


class TestPagesAutocompleteAPI(BaseAuthenticatedViewTestCase):
    """Test GET /api/pages/autocomplete/ endpoint."""

    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def send_autocomplete_request(self, query=""):
        """Helper to send autocomplete request."""
        url = f"/api/pages/autocomplete/?q={query}"
        return self.send_api_request(url=url, method="get")

    def test_autocomplete_with_empty_query_returns_all_pages(self):
        """Test autocomplete with empty query returns all user's pages (up to 10)."""
        pages = [PageFactory(project=self.project, creator=self.user, title=f"Page {i}") for i in range(5)]

        response = self.send_autocomplete_request("")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("pages", payload)
        self.assertEqual(len(payload["pages"]), 5)

        returned_ids = {page["external_id"] for page in payload["pages"]}
        expected_ids = {str(page.external_id) for page in pages}
        self.assertEqual(returned_ids, expected_ids)

    def test_autocomplete_with_query_filters_by_title(self):
        """Test autocomplete filters pages by title (case-insensitive)."""
        PageFactory(project=self.project, creator=self.user, title="Python Tutorial")
        PageFactory(project=self.project, creator=self.user, title="JavaScript Guide")
        PageFactory(project=self.project, creator=self.user, title="Python Best Practices")
        PageFactory(project=self.project, creator=self.user, title="Django Documentation")

        response = self.send_autocomplete_request("python")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(len(payload["pages"]), 2)

        titles = {page["title"] for page in payload["pages"]}
        self.assertEqual(titles, {"Python Tutorial", "Python Best Practices"})

    def test_autocomplete_case_insensitive_search(self):
        """Test autocomplete search is case-insensitive."""
        PageFactory(project=self.project, creator=self.user, title="Meeting Pages")
        PageFactory(project=self.project, creator=self.user, title="MEETING AGENDA")
        PageFactory(project=self.project, creator=self.user, title="Daily Standup")

        response = self.send_autocomplete_request("meeting")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(len(payload["pages"]), 2)

        titles = {page["title"] for page in payload["pages"]}
        self.assertEqual(titles, {"Meeting Pages", "MEETING AGENDA"})

    def test_autocomplete_limits_results_to_10(self):
        """Test autocomplete returns maximum of 10 results."""
        for i in range(15):
            PageFactory(project=self.project, creator=self.user, title=f"Project Page {i}")

        response = self.send_autocomplete_request("Project")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(len(payload["pages"]), 10)

    def test_autocomplete_orders_by_most_recently_updated(self):
        """Test autocomplete returns pages ordered by most recently updated first."""
        page1 = PageFactory(project=self.project, creator=self.user, title="Old Page")
        page2 = PageFactory(project=self.project, creator=self.user, title="Middle Page")
        page3 = PageFactory(project=self.project, creator=self.user, title="Recent Page")

        now = timezone.now()
        Page.objects.filter(pk=page1.pk).update(updated=now - timedelta(days=2))
        Page.objects.filter(pk=page2.pk).update(updated=now - timedelta(days=1))
        Page.objects.filter(pk=page3.pk).update(updated=now)

        response = self.send_autocomplete_request("")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(len(payload["pages"]), 3)

        returned_ids = [page["external_id"] for page in payload["pages"]]
        self.assertEqual(returned_ids[0], str(page3.external_id))
        self.assertEqual(returned_ids[1], str(page2.external_id))
        self.assertEqual(returned_ids[2], str(page1.external_id))

    def test_autocomplete_only_returns_user_accessible_pages(self):
        """Test autocomplete only returns pages the user can edit."""
        user_page1 = PageFactory(project=self.project, creator=self.user, title="My Page 1")
        user_page2 = PageFactory(project=self.project, creator=self.user, title="My Page 2")

        other_org = OrgFactory()
        other_user = UserFactory()
        OrgMemberFactory(org=other_org, user=other_user)
        other_project = ProjectFactory(org=other_org, creator=other_user)
        other_page = PageFactory(project=other_project, creator=other_user, title="Other User Page")

        response = self.send_autocomplete_request("")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(len(payload["pages"]), 2)

        returned_ids = {page["external_id"] for page in payload["pages"]}
        self.assertEqual(returned_ids, {str(user_page1.external_id), str(user_page2.external_id)})
        self.assertNotIn(str(other_page.external_id), returned_ids)

    def test_autocomplete_includes_project_shared_pages(self):
        """Test autocomplete includes pages in projects shared with the user."""
        other_org = OrgFactory()
        other_user = UserFactory()
        OrgMemberFactory(org=other_org, user=other_user)
        shared_project = ProjectFactory(org=other_org, creator=other_user)
        shared_project.editors.add(self.user)
        shared_page = PageFactory(project=shared_project, creator=other_user, title="Shared Page")

        own_page = PageFactory(project=self.project, creator=self.user, title="Own Page")

        response = self.send_autocomplete_request("")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(len(payload["pages"]), 2)

        returned_ids = {page["external_id"] for page in payload["pages"]}
        self.assertEqual(returned_ids, {str(own_page.external_id), str(shared_page.external_id)})

    def test_autocomplete_returns_expected_fields(self):
        """Test autocomplete returns all expected fields for each page."""
        page = PageFactory(project=self.project, creator=self.user, title="Test Page")

        response = self.send_autocomplete_request("")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(len(payload["pages"]), 1)

        page_data = payload["pages"][0]

        self.assertIn("external_id", page_data)
        self.assertIn("title", page_data)
        self.assertIn("created", page_data)
        self.assertIn("modified", page_data)
        self.assertIn("updated", page_data)

        self.assertEqual(page_data["external_id"], str(page.external_id))
        self.assertEqual(page_data["title"], "Test Page")

    def test_autocomplete_with_no_matching_pages(self):
        """Test autocomplete with query that matches no pages returns empty list."""
        PageFactory(project=self.project, creator=self.user, title="Python Guide")
        PageFactory(project=self.project, creator=self.user, title="Django Tutorial")

        response = self.send_autocomplete_request("JavaScript")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("pages", payload)
        self.assertEqual(len(payload["pages"]), 0)

    def test_autocomplete_with_partial_match(self):
        """Test autocomplete matches partial title strings."""
        PageFactory(project=self.project, creator=self.user, title="Project Management Best Practices")
        PageFactory(project=self.project, creator=self.user, title="Time Management")
        PageFactory(project=self.project, creator=self.user, title="Project Planning")

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
        """Test autocomplete excludes pages from soft-deleted projects."""
        page_in_deleted = PageFactory(project=self.project, creator=self.user, title="Page in Deleted Project")

        other_project = ProjectFactory(org=self.org, creator=self.user)
        active_page = PageFactory(project=other_project, creator=self.user, title="Active Page")

        self.project.is_deleted = True
        self.project.save()

        response = self.send_autocomplete_request("")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        returned_ids = {page["external_id"] for page in payload["pages"]}
        self.assertNotIn(str(page_in_deleted.external_id), returned_ids)
        self.assertIn(str(active_page.external_id), returned_ids)

    def test_autocomplete_org_filter_restricts_to_named_org(self):
        """When org_id is supplied, only pages in that org come back."""
        org_a_page = PageFactory(project=self.project, creator=self.user, title="Alpha")

        org_b = OrgFactory()
        OrgMemberFactory(org=org_b, user=self.user)
        org_b_project = ProjectFactory(org=org_b, creator=self.user)
        org_b_page = PageFactory(project=org_b_project, creator=self.user, title="Alpha")

        url = f"/api/pages/autocomplete/?q=Alpha&org_id={self.org.external_id}"
        response = self.send_api_request(url=url, method="get")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        returned_ids = {page["external_id"] for page in payload["pages"]}
        self.assertIn(str(org_a_page.external_id), returned_ids)
        self.assertNotIn(str(org_b_page.external_id), returned_ids)

    def test_autocomplete_org_filter_for_non_member_returns_empty(self):
        """Passing an org_id the user isn't a member of yields no results.

        The boundary check is implicit via get_user_accessible_pages — a non-
        member sees zero pages from that org, so combining with org_id is
        always safe and never leaks page metadata.
        """
        PageFactory(project=self.project, creator=self.user, title="Visible")

        # An org the user doesn't belong to, with a page they shouldn't see.
        outsider = UserFactory()
        outsider_org = OrgFactory()
        OrgMemberFactory(org=outsider_org, user=outsider)
        outsider_project = ProjectFactory(org=outsider_org, creator=outsider)
        outsider_page = PageFactory(project=outsider_project, creator=outsider, title="Secret")

        url = f"/api/pages/autocomplete/?q=&org_id={outsider_org.external_id}"
        response = self.send_api_request(url=url, method="get")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(payload["pages"], [])
        returned_ids = {page["external_id"] for page in payload["pages"]}
        self.assertNotIn(str(outsider_page.external_id), returned_ids)

    def test_autocomplete_without_org_id_still_returns_cross_org(self):
        """Backwards compatibility: omitting org_id keeps the old behavior.

        Callers that haven't been upgraded yet must keep working. The
        boundary is enforced by callers passing org_id, not by the endpoint
        flipping its default.
        """
        org_a_page = PageFactory(project=self.project, creator=self.user, title="Alpha")

        org_b = OrgFactory()
        OrgMemberFactory(org=org_b, user=self.user)
        org_b_project = ProjectFactory(org=org_b, creator=self.user)
        org_b_page = PageFactory(project=org_b_project, creator=self.user, title="Alpha")

        response = self.send_autocomplete_request("Alpha")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        returned_ids = {page["external_id"] for page in payload["pages"]}
        self.assertIn(str(org_a_page.external_id), returned_ids)
        self.assertIn(str(org_b_page.external_id), returned_ids)
