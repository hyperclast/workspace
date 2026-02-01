from http import HTTPStatus

from core.tests.common import BaseAuthenticatedViewTestCase, BaseViewTestCase
from filehub.constants import FileUploadStatus
from filehub.models import FileUpload
from pages.tests.factories import ProjectFactory
from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory


class TestStorageAPI(BaseAuthenticatedViewTestCase):
    """Tests for the storage summary endpoint."""

    def send_storage_request(self):
        return self.send_api_request(url="/api/users/storage/", method="get")

    def test_storage_returns_zero_when_no_files(self):
        """Storage should return 0 when user has no files."""
        response = self.send_storage_request()
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(payload["total_bytes"], 0)
        self.assertEqual(payload["file_count"], 0)

    def test_storage_returns_sum_of_available_files(self):
        """Storage should return sum of expected_size for AVAILABLE files."""
        # Create org and add user as member
        org = OrgFactory()
        OrgMemberFactory(org=org, user=self.user)
        project = ProjectFactory(org=org, creator=self.user)

        # Create files with different statuses
        FileUpload.objects.create(
            uploaded_by=self.user,
            project=project,
            filename="file1.txt",
            content_type="text/plain",
            expected_size=1000,
            status=FileUploadStatus.AVAILABLE,
        )
        FileUpload.objects.create(
            uploaded_by=self.user,
            project=project,
            filename="file2.txt",
            content_type="text/plain",
            expected_size=2000,
            status=FileUploadStatus.AVAILABLE,
        )
        # This file should not be counted (not AVAILABLE)
        FileUpload.objects.create(
            uploaded_by=self.user,
            project=project,
            filename="file3.txt",
            content_type="text/plain",
            expected_size=5000,
            status=FileUploadStatus.PENDING_URL,
        )

        response = self.send_storage_request()
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(payload["total_bytes"], 3000)  # 1000 + 2000
        self.assertEqual(payload["file_count"], 2)  # Only AVAILABLE files

    def test_storage_only_counts_own_files(self):
        """Storage should only count files uploaded by the current user."""
        other_user = UserFactory()

        # Create org and add both users as members
        org = OrgFactory()
        OrgMemberFactory(org=org, user=self.user)
        OrgMemberFactory(org=org, user=other_user)
        project = ProjectFactory(org=org, creator=self.user)

        # Current user's file
        FileUpload.objects.create(
            uploaded_by=self.user,
            project=project,
            filename="my_file.txt",
            content_type="text/plain",
            expected_size=1000,
            status=FileUploadStatus.AVAILABLE,
        )
        # Other user's file (should not be counted)
        FileUpload.objects.create(
            uploaded_by=other_user,
            project=project,
            filename="other_file.txt",
            content_type="text/plain",
            expected_size=9000,
            status=FileUploadStatus.AVAILABLE,
        )

        response = self.send_storage_request()
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(payload["total_bytes"], 1000)
        self.assertEqual(payload["file_count"], 1)

    def test_storage_counts_files_across_multiple_projects(self):
        """Storage should count files from all projects the user has uploaded to."""
        # Create two orgs with projects
        org1 = OrgFactory()
        org2 = OrgFactory()
        OrgMemberFactory(org=org1, user=self.user)
        OrgMemberFactory(org=org2, user=self.user)
        project1 = ProjectFactory(org=org1, creator=self.user)
        project2 = ProjectFactory(org=org2, creator=self.user)

        # Files in different projects
        FileUpload.objects.create(
            uploaded_by=self.user,
            project=project1,
            filename="file_in_project1.txt",
            content_type="text/plain",
            expected_size=1000,
            status=FileUploadStatus.AVAILABLE,
        )
        FileUpload.objects.create(
            uploaded_by=self.user,
            project=project2,
            filename="file_in_project2.txt",
            content_type="text/plain",
            expected_size=2500,
            status=FileUploadStatus.AVAILABLE,
        )

        response = self.send_storage_request()
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(payload["total_bytes"], 3500)  # 1000 + 2500
        self.assertEqual(payload["file_count"], 2)

    def test_storage_counts_files_in_deleted_projects(self):
        """Storage should still count files even if the project is soft-deleted."""
        org = OrgFactory()
        OrgMemberFactory(org=org, user=self.user)
        project = ProjectFactory(org=org, creator=self.user)

        # Create file in project
        FileUpload.objects.create(
            uploaded_by=self.user,
            project=project,
            filename="file_in_deleted_project.txt",
            content_type="text/plain",
            expected_size=5000,
            status=FileUploadStatus.AVAILABLE,
        )

        # Soft-delete the project
        project.is_deleted = True
        project.save()

        response = self.send_storage_request()
        payload = response.json()

        # Files should still be counted for storage purposes
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(payload["total_bytes"], 5000)
        self.assertEqual(payload["file_count"], 1)


class TestStorageAPIUnauthenticated(BaseViewTestCase):
    """Test storage endpoint without authentication."""

    def test_storage_requires_authentication(self):
        response = self.send_api_request(url="/api/users/storage/", method="get")

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)
