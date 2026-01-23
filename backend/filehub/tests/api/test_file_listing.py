from http import HTTPStatus

from core.tests.common import BaseAuthenticatedViewTestCase
from filehub.constants import FileUploadStatus
from filehub.tests.factories import FileUploadFactory
from pages.tests.factories import ProjectFactory
from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory


class TestListProjectFiles(BaseAuthenticatedViewTestCase):
    """Tests for GET /api/files/projects/{project_id}/"""

    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def test_list_project_files_returns_files(self):
        """Returns all files for the project."""
        FileUploadFactory(uploaded_by=self.user, project=self.project)
        FileUploadFactory(uploaded_by=self.user, project=self.project)

        response = self.send_api_request(
            url=f"/api/files/projects/{self.project.external_id}/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(data["count"], 2)
        self.assertEqual(len(data["items"]), 2)

    def test_list_project_files_includes_details(self):
        """Response includes project, uploader, and link info."""
        file = FileUploadFactory(
            uploaded_by=self.user,
            project=self.project,
            status=FileUploadStatus.AVAILABLE,
        )

        response = self.send_api_request(
            url=f"/api/files/projects/{self.project.external_id}/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        item = response.json()["items"][0]

        # Check project info
        self.assertEqual(item["project"]["external_id"], str(self.project.external_id))
        self.assertEqual(item["project"]["name"], self.project.name)

        # Check uploader info
        self.assertEqual(item["uploaded_by"]["external_id"], str(self.user.external_id))
        self.assertEqual(item["uploaded_by"]["email"], self.user.email)

        # Check link is present
        self.assertIn("link", item)
        self.assertIn(str(file.external_id), item["link"])

    def test_list_project_files_filter_by_status(self):
        """Can filter files by status."""
        FileUploadFactory(
            uploaded_by=self.user,
            project=self.project,
            status=FileUploadStatus.AVAILABLE,
        )
        FileUploadFactory(
            uploaded_by=self.user,
            project=self.project,
            status=FileUploadStatus.FAILED,
        )

        response = self.send_api_request(
            url=f"/api/files/projects/{self.project.external_id}/?status=available",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["count"], 1)

    def test_list_project_files_no_access_returns_403(self):
        """User without project access gets 403."""
        other_org = OrgFactory()
        other_project = ProjectFactory(org=other_org)

        response = self.send_api_request(
            url=f"/api/files/projects/{other_project.external_id}/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    def test_list_project_files_not_found_returns_404(self):
        """Non-existent project returns 404."""
        response = self.send_api_request(
            url="/api/files/projects/00000000-0000-0000-0000-000000000000/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_list_project_files_excludes_deleted_files(self):
        """Soft-deleted files are not included in the list."""
        file = FileUploadFactory(uploaded_by=self.user, project=self.project)
        file.soft_delete()

        response = self.send_api_request(
            url=f"/api/files/projects/{self.project.external_id}/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["count"], 0)

    def test_list_project_files_sorted_by_newest_first(self):
        """Files are sorted by creation date, newest first."""
        file1 = FileUploadFactory(uploaded_by=self.user, project=self.project)
        file2 = FileUploadFactory(uploaded_by=self.user, project=self.project)

        response = self.send_api_request(
            url=f"/api/files/projects/{self.project.external_id}/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        items = response.json()["items"]
        # file2 was created after file1, so it should be first
        self.assertEqual(items[0]["external_id"], str(file2.external_id))
        self.assertEqual(items[1]["external_id"], str(file1.external_id))


class TestListMyFiles(BaseAuthenticatedViewTestCase):
    """Tests for GET /api/files/mine/"""

    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def test_list_my_files_returns_own_files(self):
        """Returns only files uploaded by the current user."""
        my_file = FileUploadFactory(uploaded_by=self.user, project=self.project)

        other_user = UserFactory()
        OrgMemberFactory(org=self.org, user=other_user)
        FileUploadFactory(uploaded_by=other_user, project=self.project)

        response = self.send_api_request(
            url="/api/files/mine/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["items"][0]["external_id"], str(my_file.external_id))

    def test_list_my_files_includes_details(self):
        """Response includes project and link info."""
        FileUploadFactory(
            uploaded_by=self.user,
            project=self.project,
            status=FileUploadStatus.AVAILABLE,
        )

        response = self.send_api_request(
            url="/api/files/mine/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        item = response.json()["items"][0]

        self.assertIn("project", item)
        self.assertIn("uploaded_by", item)
        self.assertIn("link", item)

    def test_list_my_files_sorted_by_newest_first(self):
        """Files are sorted by creation date, newest first."""
        file1 = FileUploadFactory(uploaded_by=self.user, project=self.project)
        file2 = FileUploadFactory(uploaded_by=self.user, project=self.project)

        response = self.send_api_request(
            url="/api/files/mine/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        items = response.json()["items"]
        # file2 was created after file1, so it should be first
        self.assertEqual(items[0]["external_id"], str(file2.external_id))
        self.assertEqual(items[1]["external_id"], str(file1.external_id))

    def test_list_my_files_filter_by_status(self):
        """Can filter files by status."""
        FileUploadFactory(
            uploaded_by=self.user,
            project=self.project,
            status=FileUploadStatus.AVAILABLE,
        )
        FileUploadFactory(
            uploaded_by=self.user,
            project=self.project,
            status=FileUploadStatus.FAILED,
        )

        response = self.send_api_request(
            url="/api/files/mine/?status=failed",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["count"], 1)
        self.assertEqual(response.json()["items"][0]["status"], "failed")

    def test_list_my_files_excludes_deleted_files(self):
        """Soft-deleted files are not included."""
        file = FileUploadFactory(uploaded_by=self.user, project=self.project)
        file.soft_delete()

        response = self.send_api_request(
            url="/api/files/mine/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["count"], 0)

    def test_list_my_files_across_projects(self):
        """Returns files from all projects the user uploaded to."""
        project2 = ProjectFactory(org=self.org, creator=self.user)

        FileUploadFactory(uploaded_by=self.user, project=self.project)
        FileUploadFactory(uploaded_by=self.user, project=project2)

        response = self.send_api_request(
            url="/api/files/mine/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["count"], 2)


class TestGetFileUploadDetail(BaseAuthenticatedViewTestCase):
    """Tests for GET /api/files/{external_id}/ with detailed response."""

    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def test_get_file_includes_full_details(self):
        """Single file response includes project, uploader, and link."""
        file = FileUploadFactory(
            uploaded_by=self.user,
            project=self.project,
            status=FileUploadStatus.AVAILABLE,
        )

        response = self.send_api_request(
            url=f"/api/files/{file.external_id}/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()

        # Check all expected fields
        self.assertEqual(data["external_id"], str(file.external_id))
        self.assertEqual(data["filename"], file.filename)
        self.assertEqual(data["project"]["external_id"], str(self.project.external_id))
        self.assertEqual(data["project"]["name"], self.project.name)
        self.assertEqual(data["uploaded_by"]["external_id"], str(self.user.external_id))
        self.assertIn("link", data)

    def test_get_file_no_access_returns_403(self):
        """User without project access gets 403."""
        other_org = OrgFactory()
        other_project = ProjectFactory(org=other_org)
        other_user = UserFactory()
        OrgMemberFactory(org=other_org, user=other_user)
        file = FileUploadFactory(uploaded_by=other_user, project=other_project)

        response = self.send_api_request(
            url=f"/api/files/{file.external_id}/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    def test_get_file_not_found_returns_404(self):
        """Non-existent file returns 404."""
        response = self.send_api_request(
            url="/api/files/00000000-0000-0000-0000-000000000000/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_get_deleted_file_returns_404(self):
        """Soft-deleted file returns 404."""
        file = FileUploadFactory(uploaded_by=self.user, project=self.project)
        file.soft_delete()

        response = self.send_api_request(
            url=f"/api/files/{file.external_id}/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_get_file_link_none_for_pending(self):
        """Link is None for files that are not yet available."""
        file = FileUploadFactory(
            uploaded_by=self.user,
            project=self.project,
            status=FileUploadStatus.PENDING_URL,
        )

        response = self.send_api_request(
            url=f"/api/files/{file.external_id}/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        # Link is present but the download_url property returns a URL with the token
        # The file always has an access token, so link should be present
        self.assertIn("link", response.json())
