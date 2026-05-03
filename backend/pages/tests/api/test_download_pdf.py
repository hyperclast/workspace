"""Verify GET /pages/{id}/download/ on PDF-type pages redirects to filehub."""

from http import HTTPStatus
from unittest.mock import patch

from core.tests.common import BaseAuthenticatedViewTestCase
from filehub.constants import BlobStatus, FileUploadStatus
from filehub.models import Blob, FileUpload
from pages.tests.factories import PageEditorFactory, PageFactory, ProjectFactory
from users.constants import OrgMemberRole
from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory


def _make_pdf_file(project, user):
    file_upload = FileUpload.objects.create(
        uploaded_by=user,
        project=project,
        status=FileUploadStatus.AVAILABLE,
        filename="paper.pdf",
        content_type="application/pdf",
        expected_size=10,
        actual_size=10,
        metadata_json={},
    )
    Blob.objects.create(
        file_upload=file_upload,
        provider="local",
        bucket=None,
        object_key=f"u/{user.external_id}/{file_upload.external_id}/paper.pdf",
        status=BlobStatus.VERIFIED,
        size_bytes=10,
    )
    return file_upload


class TestDownloadPdfPage(BaseAuthenticatedViewTestCase):
    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)
        self.project = ProjectFactory(org=self.org, creator=self.user)
        self.file_upload = _make_pdf_file(self.project, self.user)
        self.page = PageFactory(
            project=self.project,
            creator=self.user,
            title="Paper",
            details={
                "content": "",
                "extracted_text": "Body",
                "pdf_file_id": str(self.file_upload.external_id),
                "filetype": "pdf",
                "schema_version": 2,
            },
        )

    @patch("filehub.services.downloads.get_storage_backend")
    def test_redirects_to_signed_file_url(self, mock_storage_factory):
        mock_storage = mock_storage_factory.return_value
        mock_storage.generate_download_url.return_value = "https://example.com/signed-url"

        url = f"/api/pages/{self.page.external_id}/download/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response["Location"], "https://example.com/signed-url")

    def test_404_when_file_missing(self):
        self.file_upload.delete()  # soft delete

        url = f"/api/pages/{self.page.external_id}/download/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_404_when_file_hard_deleted(self):
        """Hard-deleting the underlying FileUpload row leaves the page intact
        but the download endpoint must surface a 404 instead of redirecting
        to a nonexistent file."""
        FileUpload.all_objects.filter(pk=self.file_upload.pk).hard_delete()

        url = f"/api/pages/{self.page.external_id}/download/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_404_when_pdf_file_id_missing_from_details(self):
        """Defensive: a PDF page whose details dict has no `pdf_file_id` (e.g.
        partially migrated row, manual ORM edit) returns 404 rather than
        crashing on the missing key."""
        details = dict(self.page.details or {})
        details.pop("pdf_file_id", None)
        self.page.details = details
        self.page.save(update_fields=["details", "modified"])

        url = f"/api/pages/{self.page.external_id}/download/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_403_for_page_only_viewer_without_project_access(self):
        # A user with page-only access (Tier 3) — no org membership, no project editor.
        outsider = UserFactory()
        PageEditorFactory(user=outsider, page=self.page)

        self.client.logout()
        self.client.force_login(outsider)

        url = f"/api/pages/{self.page.external_id}/download/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)


class TestAccessCodeBlockedOnPdf(BaseAuthenticatedViewTestCase):
    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)
        self.project = ProjectFactory(org=self.org, creator=self.user)
        self.page = PageFactory(
            project=self.project,
            creator=self.user,
            details={
                "content": "",
                "extracted_text": "Body",
                "pdf_file_id": "f-1",
                "filetype": "pdf",
                "schema_version": 2,
            },
        )

    def test_generate_access_code_returns_400_on_pdf_page(self):
        url = f"/api/pages/{self.page.external_id}/access-code/"
        response = self.client.post(url, data={}, content_type="application/json")
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIn("PDF", response.json()["message"])
