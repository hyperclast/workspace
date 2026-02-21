import io
import zipfile
from http import HTTPStatus
from unittest.mock import patch

from core.tests.common import BaseAuthenticatedViewTestCase
from imports.constants import ImportJobStatus, ImportProvider
from imports.models import ImportArchive, ImportedPage, ImportJob
from imports.tests.factories import ImportedPageFactory, ImportJobFactory
from pages.constants import PageEditorRole, ProjectEditorRole
from pages.tests.factories import PageEditorFactory, PageFactory, ProjectEditorFactory, ProjectFactory
from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory


def create_test_zip() -> bytes:
    """Create a minimal test zip file."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("Test Page abc123def456789012.md", "# Test Page\n\nContent.")
    return buffer.getvalue()


class TestListImportJobsAPI(BaseAuthenticatedViewTestCase):
    """Test GET /api/imports/ endpoint."""

    def test_list_import_jobs_returns_user_jobs(self):
        """User should only see their own import jobs."""
        # Create jobs for current user
        project = ProjectFactory(creator=self.user)
        job1 = ImportJobFactory(user=self.user, project=project)
        job2 = ImportJobFactory(user=self.user, project=project)

        # Create job for another user
        other_user = UserFactory()
        other_project = ProjectFactory(creator=other_user)
        ImportJobFactory(user=other_user, project=other_project)

        response = self.send_api_request(url="/api/imports/", method="get")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        payload = response.json()

        self.assertEqual(payload["count"], 2)
        job_ids = [item["external_id"] for item in payload["items"]]
        self.assertIn(str(job1.external_id), job_ids)
        self.assertIn(str(job2.external_id), job_ids)

    def test_list_import_jobs_empty(self):
        """User with no import jobs should see empty list."""
        response = self.send_api_request(url="/api/imports/", method="get")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        payload = response.json()
        self.assertEqual(payload["count"], 0)
        self.assertEqual(payload["items"], [])

    def test_list_import_jobs_filter_by_status(self):
        """Can filter import jobs by status."""
        project = ProjectFactory(creator=self.user)
        ImportJobFactory(user=self.user, project=project, status=ImportJobStatus.PENDING)
        job_completed = ImportJobFactory(user=self.user, project=project, status=ImportJobStatus.COMPLETED)

        response = self.send_api_request(url="/api/imports/", method="get", query_params={"status": "completed"})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["items"][0]["external_id"], str(job_completed.external_id))

    def test_list_import_jobs_filter_by_provider(self):
        """Can filter import jobs by provider."""
        project = ProjectFactory(creator=self.user)
        job_notion = ImportJobFactory(user=self.user, project=project, provider=ImportProvider.NOTION)

        response = self.send_api_request(url="/api/imports/", method="get", query_params={"provider": "notion"})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["items"][0]["external_id"], str(job_notion.external_id))


class TestStartNotionImportAPI(BaseAuthenticatedViewTestCase):
    """Test POST /api/imports/notion/ endpoint."""

    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)
        self.test_zip = create_test_zip()

    @patch("imports.api.imports.process_notion_import")
    def test_start_notion_import_succeeds(self, mock_task):
        """Can start a Notion import job with file upload."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import TestCase

        file = SimpleUploadedFile("notion_export.zip", self.test_zip, content_type="application/zip")

        # Use captureOnCommitCallbacks to execute on_commit callbacks in tests
        # This is needed because Django's TestCase wraps tests in a transaction that never commits
        with TestCase.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                "/api/imports/notion/",
                data={
                    "project_id": str(self.project.external_id),
                    "file": file,
                },
                format="multipart",
            )

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        payload = response.json()

        self.assertIn("job", payload)
        self.assertIn("message", payload)
        self.assertEqual(payload["job"]["provider"], "notion")
        self.assertEqual(payload["job"]["status"], "pending")

        # Verify database record
        import_job = ImportJob.objects.get(external_id=payload["job"]["external_id"])
        self.assertEqual(import_job.user, self.user)
        self.assertEqual(import_job.project, self.project)
        self.assertEqual(import_job.provider, ImportProvider.NOTION)
        self.assertEqual(import_job.status, ImportJobStatus.PENDING)

        # Verify archive was created with temp file path
        self.assertTrue(hasattr(import_job, "archive"))
        self.assertIsNotNone(import_job.archive.temp_file_path)
        self.assertEqual(import_job.archive.filename, "notion_export.zip")

        # Verify enqueue was called with only import_job_id
        mock_task.enqueue.assert_called_once()
        call_kwargs = mock_task.enqueue.call_args.kwargs
        self.assertEqual(call_kwargs["import_job_id"], import_job.id)

    def test_start_notion_import_requires_file(self):
        """File is required."""
        response = self.client.post(
            "/api/imports/notion/",
            data={
                "project_id": str(self.project.external_id),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)

    def test_start_notion_import_requires_project_id(self):
        """Project ID is required."""
        from django.core.files.uploadedfile import SimpleUploadedFile

        file = SimpleUploadedFile("notion_export.zip", self.test_zip, content_type="application/zip")

        response = self.client.post(
            "/api/imports/notion/",
            data={"file": file},
            format="multipart",
        )

        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)

    @patch("imports.api.imports.process_notion_import")
    def test_start_notion_import_project_not_found(self, mock_task):
        """Returns 404 for non-existent project."""
        from django.core.files.uploadedfile import SimpleUploadedFile

        file = SimpleUploadedFile("notion_export.zip", self.test_zip, content_type="application/zip")

        response = self.client.post(
            "/api/imports/notion/",
            data={
                "project_id": "00000000-0000-0000-0000-000000000000",
                "file": file,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    @patch("imports.api.imports.process_notion_import")
    def test_start_notion_import_forbidden_for_inaccessible_project(self, mock_task):
        """Returns 403 for project user doesn't have access to."""
        from django.core.files.uploadedfile import SimpleUploadedFile

        other_org = OrgFactory()
        other_project = ProjectFactory(org=other_org)
        file = SimpleUploadedFile("notion_export.zip", self.test_zip, content_type="application/zip")

        response = self.client.post(
            "/api/imports/notion/",
            data={
                "project_id": str(other_project.external_id),
                "file": file,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    @patch("imports.api.imports.process_notion_import")
    def test_start_notion_import_forbidden_for_viewer_project_editor(self, mock_task):
        """Viewer project editors should NOT be able to start imports.

        Imports create pages, which requires editor (write) permission.
        Viewers have read-only access and should not be able to create pages.
        """
        from django.core.files.uploadedfile import SimpleUploadedFile

        # Create a project owned by another user
        other_org = OrgFactory()
        other_user = UserFactory()
        OrgMemberFactory(org=other_org, user=other_user)
        other_project = ProjectFactory(org=other_org, creator=other_user)

        # Add current user as a VIEWER project editor (read-only access)
        ProjectEditorFactory(
            project=other_project,
            user=self.user,
            role=ProjectEditorRole.VIEWER.value,
        )

        file = SimpleUploadedFile("notion_export.zip", self.test_zip, content_type="application/zip")

        response = self.client.post(
            "/api/imports/notion/",
            data={
                "project_id": str(other_project.external_id),
                "file": file,
            },
            format="multipart",
        )

        # Viewer should be forbidden from starting imports
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        payload = response.json()
        self.assertEqual(payload["error"], "forbidden")

        # No import job should be created
        self.assertFalse(ImportJob.objects.filter(project=other_project).exists())

    @patch("imports.api.imports.process_notion_import")
    def test_start_notion_import_allowed_for_editor_project_editor(self, mock_task):
        """Editor project editors should be able to start imports.

        Editors have write permission and can create pages via imports.
        """
        from django.core.files.uploadedfile import SimpleUploadedFile

        # Create a project owned by another user
        other_org = OrgFactory()
        other_user = UserFactory()
        OrgMemberFactory(org=other_org, user=other_user)
        other_project = ProjectFactory(org=other_org, creator=other_user)

        # Add current user as an EDITOR project editor (write access)
        ProjectEditorFactory(
            project=other_project,
            user=self.user,
            role=ProjectEditorRole.EDITOR.value,
        )

        file = SimpleUploadedFile("notion_export.zip", self.test_zip, content_type="application/zip")

        response = self.client.post(
            "/api/imports/notion/",
            data={
                "project_id": str(other_project.external_id),
                "file": file,
            },
            format="multipart",
        )

        # Editor should be allowed to start imports
        self.assertEqual(response.status_code, HTTPStatus.CREATED)

        # Import job should be created
        self.assertTrue(ImportJob.objects.filter(project=other_project, user=self.user).exists())

    @patch("imports.api.imports.process_notion_import")
    def test_start_notion_import_deleted_project(self, mock_task):
        """Returns 404 for deleted project."""
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.project.is_deleted = True
        self.project.save()
        file = SimpleUploadedFile("notion_export.zip", self.test_zip, content_type="application/zip")

        response = self.client.post(
            "/api/imports/notion/",
            data={
                "project_id": str(self.project.external_id),
                "file": file,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_start_notion_import_invalid_content_type(self):
        """Returns 400 for invalid file type."""
        from django.core.files.uploadedfile import SimpleUploadedFile

        file = SimpleUploadedFile("test.txt", b"not a zip", content_type="text/plain")

        response = self.client.post(
            "/api/imports/notion/",
            data={
                "project_id": str(self.project.external_id),
                "file": file,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        payload = response.json()
        self.assertEqual(payload["error"], "invalid_content_type")

    @patch("imports.api.imports.should_block_user", return_value=(False, ""))
    @patch("imports.api.imports.process_notion_import")
    def test_start_notion_import_with_spoofed_content_type_succeeds(self, mock_task, mock_block):
        """File with spoofed content-type but valid zip content should succeed.

        Content-type is client-provided and can be spoofed, but we rely on
        the zipfile library to validate the actual content. This test verifies
        that a valid zip with a spoofed application/zip content-type works.
        """
        from django.core.files.uploadedfile import SimpleUploadedFile

        # Create a valid zip but claim it's application/zip (which is normal)
        file = SimpleUploadedFile("notion_export.zip", self.test_zip, content_type="application/zip")

        response = self.client.post(
            "/api/imports/notion/",
            data={
                "project_id": str(self.project.external_id),
                "file": file,
            },
            format="multipart",
        )

        # Should succeed since content is actually a valid zip
        self.assertEqual(response.status_code, HTTPStatus.CREATED)

    @patch("imports.api.imports.should_block_user", return_value=(False, ""))
    @patch("imports.api.imports.process_notion_import")
    def test_start_notion_import_with_x_zip_compressed_content_type_succeeds(self, mock_task, mock_block):
        """File with application/x-zip-compressed content-type should succeed.

        Some systems use application/x-zip-compressed instead of application/zip.
        """
        from django.core.files.uploadedfile import SimpleUploadedFile

        file = SimpleUploadedFile("notion_export.zip", self.test_zip, content_type="application/x-zip-compressed")

        response = self.client.post(
            "/api/imports/notion/",
            data={
                "project_id": str(self.project.external_id),
                "file": file,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, HTTPStatus.CREATED)


class TestGetImportJobAPI(BaseAuthenticatedViewTestCase):
    """Test GET /api/imports/{external_id}/ endpoint."""

    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def test_get_import_job_succeeds(self):
        """Can get details of own import job."""
        job = ImportJobFactory(
            user=self.user,
            project=self.project,
            status=ImportJobStatus.COMPLETED,
            total_pages=10,
            pages_imported_count=8,
            pages_failed_count=2,
        )

        response = self.send_api_request(
            url=f"/api/imports/{job.external_id}/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        payload = response.json()

        self.assertEqual(payload["external_id"], str(job.external_id))
        self.assertEqual(payload["provider"], "notion")
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["total_pages"], 10)
        self.assertEqual(payload["pages_imported_count"], 8)
        self.assertEqual(payload["pages_failed_count"], 2)
        self.assertEqual(payload["project"]["external_id"], str(self.project.external_id))
        self.assertEqual(payload["project"]["name"], self.project.name)

    def test_get_import_job_not_found(self):
        """Returns 404 for non-existent import job."""
        response = self.send_api_request(
            url="/api/imports/00000000-0000-0000-0000-000000000000/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_get_import_job_forbidden_for_other_user(self):
        """Returns 403 for another user's import job."""
        other_user = UserFactory()
        other_project = ProjectFactory(creator=other_user)
        other_job = ImportJobFactory(user=other_user, project=other_project)

        response = self.send_api_request(
            url=f"/api/imports/{other_job.external_id}/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)


class TestListImportedPagesAPI(BaseAuthenticatedViewTestCase):
    """Test GET /api/imports/{external_id}/pages/ endpoint."""

    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def test_list_imported_pages_succeeds(self):
        """Can list pages created by an import job."""
        job = ImportJobFactory(user=self.user, project=self.project)
        page1 = PageFactory(project=self.project, creator=self.user, title="Page One")
        page2 = PageFactory(project=self.project, creator=self.user, title="Page Two")
        imported1 = ImportedPageFactory(import_job=job, page=page1, original_path="Folder/Page One abc123.md")
        imported2 = ImportedPageFactory(import_job=job, page=page2, original_path="Page Two def456.md")

        response = self.send_api_request(
            url=f"/api/imports/{job.external_id}/pages/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        payload = response.json()

        self.assertEqual(payload["count"], 2)
        titles = [item["title"] for item in payload["items"]]
        self.assertIn("Page One", titles)
        self.assertIn("Page Two", titles)

        paths = [item["original_path"] for item in payload["items"]]
        self.assertIn("Folder/Page One abc123.md", paths)
        self.assertIn("Page Two def456.md", paths)

    def test_list_imported_pages_empty(self):
        """Returns empty list for job with no imported pages."""
        job = ImportJobFactory(user=self.user, project=self.project)

        response = self.send_api_request(
            url=f"/api/imports/{job.external_id}/pages/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        payload = response.json()
        self.assertEqual(payload["count"], 0)
        self.assertEqual(payload["items"], [])

    def test_list_imported_pages_forbidden_for_other_user(self):
        """Returns 403 for another user's import job."""
        other_user = UserFactory()
        other_project = ProjectFactory(creator=other_user)
        other_job = ImportJobFactory(user=other_user, project=other_project)

        response = self.send_api_request(
            url=f"/api/imports/{other_job.external_id}/pages/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)


class TestStartNotionImportMultipleRequests(BaseAuthenticatedViewTestCase):
    """Test multiple import request handling for same project."""

    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)
        self.test_zip = create_test_zip()

    @patch("imports.api.imports.process_notion_import")
    def test_multiple_imports_for_same_project_all_succeed(self, mock_task):
        """Multiple import requests for the same project should all succeed.

        This tests that sequential requests don't interfere with each other,
        since each creates a separate ImportJob and temp file. This is important
        for users who want to import multiple Notion exports into the same project.
        """
        from django.core.files.uploadedfile import SimpleUploadedFile

        responses = []

        # Make 3 sequential requests
        for i in range(3):
            file = SimpleUploadedFile(f"notion_export_{i}.zip", self.test_zip, content_type="application/zip")

            response = self.client.post(
                "/api/imports/notion/",
                data={
                    "project_id": str(self.project.external_id),
                    "file": file,
                },
                format="multipart",
            )
            responses.append(response)

        # All should succeed
        for response in responses:
            self.assertEqual(response.status_code, HTTPStatus.CREATED)

        # Should have created 3 distinct import jobs
        self.assertEqual(ImportJob.objects.filter(project=self.project).count(), 3)

        # Each job should have its own archive
        self.assertEqual(ImportArchive.objects.filter(import_job__project=self.project).count(), 3)

        # Each job should have a unique external_id
        external_ids = set(ImportJob.objects.filter(project=self.project).values_list("external_id", flat=True))
        self.assertEqual(len(external_ids), 3)


class TestDeleteImportJobAPI(BaseAuthenticatedViewTestCase):
    """Test DELETE /api/imports/{external_id}/ endpoint."""

    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def test_delete_import_job_succeeds(self):
        """Can delete own import job."""
        job = ImportJobFactory(user=self.user, project=self.project)
        job_id = job.id

        response = self.send_api_request(
            url=f"/api/imports/{job.external_id}/",
            method="delete",
        )

        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)
        self.assertFalse(ImportJob.objects.filter(id=job_id).exists())

    def test_delete_import_job_not_found(self):
        """Returns 404 for non-existent import job."""
        response = self.send_api_request(
            url="/api/imports/00000000-0000-0000-0000-000000000000/",
            method="delete",
        )

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_delete_import_job_forbidden_for_other_user(self):
        """Returns 403 for another user's import job."""
        other_user = UserFactory()
        other_project = ProjectFactory(creator=other_user)
        other_job = ImportJobFactory(user=other_user, project=other_project)

        response = self.send_api_request(
            url=f"/api/imports/{other_job.external_id}/",
            method="delete",
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        # Job should still exist
        self.assertTrue(ImportJob.objects.filter(id=other_job.id).exists())

    def test_delete_import_job_preserves_imported_pages(self):
        """Deleting import job does not delete the imported pages."""
        job = ImportJobFactory(user=self.user, project=self.project)
        page = PageFactory(project=self.project, creator=self.user)
        ImportedPageFactory(import_job=job, page=page)
        page_id = page.id

        response = self.send_api_request(
            url=f"/api/imports/{job.external_id}/",
            method="delete",
        )

        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)
        # Page should still exist
        from pages.models import Page

        self.assertTrue(Page.objects.filter(id=page_id).exists())


class TestPageLevelAccessImport(BaseAuthenticatedViewTestCase):
    """Test that page-only access (Tier 3) does NOT grant import permissions.

    Imports create pages in a project, which requires project-level write access.
    Users with only page-level access should not be able to start imports.
    """

    def setUp(self):
        super().setUp()
        self.project_owner = UserFactory()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.project_owner)
        self.project = ProjectFactory(org=self.org, creator=self.project_owner)
        self.project.org_members_can_access = False
        self.project.save()

        # Give self.user page-level access only (not project or org access)
        self.page = PageFactory(project=self.project, creator=self.project_owner)
        PageEditorFactory(page=self.page, user=self.user, role=PageEditorRole.EDITOR.value)

        self.test_zip = create_test_zip()

    @patch("imports.api.imports.process_notion_import")
    def test_page_editor_cannot_start_import(self, mock_task):
        """User with only page-level access cannot start an import into the project."""
        from django.core.files.uploadedfile import SimpleUploadedFile

        file = SimpleUploadedFile("notion_export.zip", self.test_zip, content_type="application/zip")

        response = self.client.post(
            "/api/imports/notion/",
            data={
                "project_id": str(self.project.external_id),
                "file": file,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

        # No import job should be created
        self.assertFalse(ImportJob.objects.filter(project=self.project, user=self.user).exists())
