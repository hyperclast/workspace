from http import HTTPStatus

from core.tests.common import BaseAuthenticatedViewTestCase
from filehub.constants import FileUploadStatus
from filehub.models import FileLink
from filehub.tests.factories import FileUploadFactory
from pages.constants import ProjectEditorRole
from pages.tests.factories import PageFactory, ProjectEditorFactory, ProjectFactory
from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory


class TestGetFileReferencesAPI(BaseAuthenticatedViewTestCase):
    """Test GET /api/files/{external_id}/references/ endpoint."""

    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)
        self.page = PageFactory(project=self.project, creator=self.user)
        self.file = FileUploadFactory(
            uploaded_by=self.user,
            project=self.project,
            status=FileUploadStatus.AVAILABLE,
        )

    def test_get_references_empty(self):
        """File with no references returns empty list."""
        response = self.send_api_request(
            url=f"/api/files/{self.file.external_id}/references/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(data["references"], [])
        self.assertEqual(data["count"], 0)

    def test_get_references_with_data(self):
        """File with references returns list of pages."""
        FileLink.objects.create(
            source_page=self.page,
            target_file=self.file,
            link_text="test image",
        )

        response = self.send_api_request(
            url=f"/api/files/{self.file.external_id}/references/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(len(data["references"]), 1)
        self.assertEqual(data["references"][0]["page_external_id"], self.page.external_id)
        self.assertEqual(data["references"][0]["page_title"], self.page.title)
        self.assertEqual(data["references"][0]["link_text"], "test image")
        self.assertEqual(data["count"], 1)

    def test_get_references_multiple_pages(self):
        """File referenced by multiple pages returns all of them."""
        page2 = PageFactory(project=self.project, creator=self.user, title="Second Page")

        FileLink.objects.create(
            source_page=self.page,
            target_file=self.file,
            link_text="link 1",
        )
        FileLink.objects.create(
            source_page=page2,
            target_file=self.file,
            link_text="link 2",
        )

        response = self.send_api_request(
            url=f"/api/files/{self.file.external_id}/references/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(len(data["references"]), 2)
        self.assertEqual(data["count"], 2)

    def test_get_references_excludes_deleted_pages(self):
        """References from deleted pages are not included."""
        FileLink.objects.create(
            source_page=self.page,
            target_file=self.file,
            link_text="link",
        )

        self.page.is_deleted = True
        self.page.save()

        response = self.send_api_request(
            url=f"/api/files/{self.file.external_id}/references/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(data["references"], [])
        self.assertEqual(data["count"], 0)

    def test_get_references_excludes_pages_from_deleted_projects(self):
        """References from pages in deleted projects are not included."""
        FileLink.objects.create(
            source_page=self.page,
            target_file=self.file,
            link_text="link",
        )

        self.project.is_deleted = True
        self.project.save()

        response = self.send_api_request(
            url=f"/api/files/{self.file.external_id}/references/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(data["references"], [])
        self.assertEqual(data["count"], 0)

    def test_get_references_untitled_page(self):
        """Page without title shows 'Untitled'."""
        self.page.title = ""
        self.page.save()

        FileLink.objects.create(
            source_page=self.page,
            target_file=self.file,
            link_text="link",
        )

        response = self.send_api_request(
            url=f"/api/files/{self.file.external_id}/references/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(data["references"][0]["page_title"], "Untitled")

    def test_get_references_requires_project_access(self):
        """User without project access cannot view references."""
        other_user = UserFactory()
        other_project = ProjectFactory(creator=other_user)
        file_upload = FileUploadFactory(uploaded_by=other_user, project=other_project)

        response = self.send_api_request(
            url=f"/api/files/{file_upload.external_id}/references/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    def test_get_references_project_viewer_can_access(self):
        """Project viewer can view file references."""
        other_project = ProjectFactory(org=self.org, creator=self.user)
        other_project.org_members_can_access = False
        other_project.save()

        viewer = UserFactory()
        ProjectEditorFactory(
            project=other_project,
            user=viewer,
            role=ProjectEditorRole.VIEWER.value,
        )

        file_upload = FileUploadFactory(
            uploaded_by=self.user,
            project=other_project,
            status=FileUploadStatus.AVAILABLE,
        )

        self.client.force_login(viewer)
        response = self.send_api_request(
            url=f"/api/files/{file_upload.external_id}/references/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_get_references_deleted_file_returns_404(self):
        """Deleted file returns 404."""
        self.file.soft_delete()

        response = self.send_api_request(
            url=f"/api/files/{self.file.external_id}/references/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_get_references_nonexistent_file_returns_404(self):
        """Non-existent file returns 404."""
        response = self.send_api_request(
            url="/api/files/00000000-0000-0000-0000-000000000000/references/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_get_references_unauthenticated_returns_401(self):
        """Unauthenticated request returns 401."""
        self.client.logout()

        response = self.send_api_request(
            url=f"/api/files/{self.file.external_id}/references/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)
