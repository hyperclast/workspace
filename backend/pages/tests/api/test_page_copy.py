from http import HTTPStatus

from core.tests.common import BaseAuthenticatedViewTestCase
from pages.models import Page
from pages.tests.factories import PageFactory, ProjectFactory
from users.constants import OrgMemberRole
from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory


class TestPageCopyFeature(BaseAuthenticatedViewTestCase):
    """Test POST /api/pages/ with copy_from parameter."""

    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def send_create_page_request(self, title, project_id=None, copy_from=None):
        url = "/api/pages/"
        if project_id is None:
            project_id = self.project.external_id
        data = {"title": title, "project_id": project_id}
        if copy_from is not None:
            data["copy_from"] = copy_from
        return self.send_api_request(url=url, method="post", data=data)

    def test_create_page_with_copy_from_copies_content(self):
        """Test creating a page with copy_from copies content from source page."""
        source_content = "# Template Content\n\nThis is template text."
        source_page = PageFactory(
            project=self.project,
            creator=self.user,
            title="Template Page",
            details={"content": source_content, "filetype": "md", "schema_version": 1},
        )

        response = self.send_create_page_request(
            title="New Page From Template",
            copy_from=source_page.external_id,
        )
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        self.assertEqual(payload["title"], "New Page From Template")

        new_page = Page.objects.get(external_id=payload["external_id"])
        self.assertEqual(new_page.details.get("content"), source_content)

    def test_create_page_with_copy_from_copies_filetype(self):
        """Test creating a page with copy_from copies filetype from source page."""
        source_page = PageFactory(
            project=self.project,
            creator=self.user,
            title="Text Template",
            details={"content": "Plain text content", "filetype": "txt", "schema_version": 1},
        )

        response = self.send_create_page_request(
            title="New Text Page",
            copy_from=source_page.external_id,
        )
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.CREATED)

        new_page = Page.objects.get(external_id=payload["external_id"])
        self.assertEqual(new_page.details.get("filetype"), "txt")

    def test_create_page_with_copy_from_does_not_copy_title(self):
        """Test creating a page with copy_from uses provided title, not source title."""
        source_page = PageFactory(
            project=self.project,
            creator=self.user,
            title="Source Title",
            details={"content": "Content to copy", "filetype": "md"},
        )

        response = self.send_create_page_request(
            title="My Custom Title",
            copy_from=source_page.external_id,
        )
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        self.assertEqual(payload["title"], "My Custom Title")
        self.assertNotEqual(payload["title"], "Source Title")

    def test_create_page_with_copy_from_invalid_page_creates_blank_page(self):
        """Test creating a page with invalid copy_from creates a blank page."""
        response = self.send_create_page_request(
            title="New Page",
            copy_from="nonexistent-page-id",
        )
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.CREATED)

        new_page = Page.objects.get(external_id=payload["external_id"])
        self.assertEqual(new_page.details.get("content"), "")

    def test_create_page_with_copy_from_different_project_creates_blank_page(self):
        """Test that copy_from only works for pages in the same project."""
        other_project = ProjectFactory(org=self.org, creator=self.user)
        source_page = PageFactory(
            project=other_project,
            creator=self.user,
            title="Page in Other Project",
            details={"content": "Should not be copied", "filetype": "md"},
        )

        response = self.send_create_page_request(
            title="New Page",
            copy_from=source_page.external_id,
        )
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.CREATED)

        new_page = Page.objects.get(external_id=payload["external_id"])
        self.assertEqual(new_page.details.get("content"), "")

    def test_create_page_with_copy_from_deleted_page_creates_blank_page(self):
        """Test that copy_from ignores deleted source pages."""
        source_page = PageFactory(
            project=self.project,
            creator=self.user,
            title="Deleted Template",
            details={"content": "Deleted content", "filetype": "md"},
            is_deleted=True,
        )

        response = self.send_create_page_request(
            title="New Page",
            copy_from=source_page.external_id,
        )
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.CREATED)

        new_page = Page.objects.get(external_id=payload["external_id"])
        self.assertEqual(new_page.details.get("content"), "")

    def test_create_page_without_copy_from_creates_blank_page(self):
        """Test creating a page without copy_from creates a blank page."""
        response = self.send_create_page_request(title="Blank Page")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.CREATED)

        new_page = Page.objects.get(external_id=payload["external_id"])
        self.assertEqual(new_page.details.get("content"), "")
        self.assertEqual(new_page.details.get("filetype"), "md")

    def test_create_page_with_copy_from_empty_string_creates_blank_page(self):
        """Test creating a page with empty copy_from string creates blank page."""
        response = self.send_create_page_request(
            title="Blank Page",
            copy_from="",
        )
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.CREATED)

        new_page = Page.objects.get(external_id=payload["external_id"])
        self.assertEqual(new_page.details.get("content"), "")

    def test_create_page_with_copy_from_preserves_schema_version(self):
        """Test that new page gets schema_version 1 regardless of source."""
        source_page = PageFactory(
            project=self.project,
            creator=self.user,
            details={"content": "Content", "filetype": "md", "schema_version": 99},
        )

        response = self.send_create_page_request(
            title="New Page",
            copy_from=source_page.external_id,
        )
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.CREATED)

        new_page = Page.objects.get(external_id=payload["external_id"])
        self.assertEqual(new_page.details.get("schema_version"), 1)


class TestPageCopyAccessControl(BaseAuthenticatedViewTestCase):
    """Test access control for page copy feature."""

    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def send_create_page_request(self, title, project_id, copy_from=None):
        url = "/api/pages/"
        data = {"title": title, "project_id": project_id}
        if copy_from is not None:
            data["copy_from"] = copy_from
        return self.send_api_request(url=url, method="post", data=data)

    def test_project_editor_can_copy_from_page_in_shared_project(self):
        """Test that project editors can copy from pages in projects shared with them."""
        other_org = OrgFactory()
        other_user = UserFactory()
        OrgMemberFactory(org=other_org, user=other_user, role=OrgMemberRole.MEMBER.value)
        other_project = ProjectFactory(org=other_org, creator=other_user)

        other_project.editors.add(self.user)

        source_page = PageFactory(
            project=other_project,
            creator=other_user,
            title="Shared Template",
            details={"content": "Shared content", "filetype": "md"},
        )

        response = self.send_create_page_request(
            title="New Page From Shared",
            project_id=other_project.external_id,
            copy_from=source_page.external_id,
        )
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.CREATED)

        new_page = Page.objects.get(external_id=payload["external_id"])
        self.assertEqual(new_page.details.get("content"), "Shared content")

    def test_user_cannot_copy_from_page_they_cannot_access(self):
        """Test that users cannot copy from pages in projects they don't have access to."""
        other_org = OrgFactory()
        other_user = UserFactory()
        OrgMemberFactory(org=other_org, user=other_user, role=OrgMemberRole.MEMBER.value)
        other_project = ProjectFactory(org=other_org, creator=other_user)

        source_page = PageFactory(
            project=other_project,
            creator=other_user,
            title="Inaccessible Template",
            details={"content": "Secret content", "filetype": "md"},
        )

        response = self.send_create_page_request(
            title="New Page",
            project_id=self.project.external_id,
            copy_from=source_page.external_id,
        )
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.CREATED)

        new_page = Page.objects.get(external_id=payload["external_id"])
        self.assertEqual(new_page.details.get("content"), "")
