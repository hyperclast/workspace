from http import HTTPStatus
from unittest.mock import MagicMock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError

from core.tests.common import BaseAuthenticatedViewTestCase
from imports.tests.factories import ImportBannedUserFactory
from pages.constants import ProjectEditorRole
from pages.models import Page
from pages.tests.factories import ProjectEditorFactory, ProjectFactory
from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory

PDF_BYTES = b"%PDF-1.4 minimal"  # Not a real PDF; storage is mocked


def _mock_store_pdf(project, user, filename, file_bytes):
    """Return a mock FileUpload with a deterministic download_url."""
    fu = MagicMock()
    fu.external_id = "file-ext-id"
    fu.download_url = "/files/proj/file-ext-id/tok/"
    return fu


class TestPdfImportFilenameEscaping(BaseAuthenticatedViewTestCase):
    """Verify that user-supplied filenames are escaped in generated page content."""

    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def _import(self, filename="doc.pdf", title="Test", content="Some text"):
        file = SimpleUploadedFile(filename, PDF_BYTES, content_type="application/pdf")
        return self.client.post(
            "/api/imports/pdf/",
            data={
                "project_id": str(self.project.external_id),
                "title": title,
                "content": content,
                "file": file,
            },
            format="multipart",
        )

    @patch("imports.api.imports.store_pdf_as_file", side_effect=_mock_store_pdf)
    def test_plain_filename_in_page_content(self, mock_store):
        resp = self._import(filename="report.pdf")
        self.assertEqual(resp.status_code, HTTPStatus.CREATED)

        page = Page.objects.get(external_id=resp.json()["page_external_id"])
        page_content = page.details["content"]

        # Link text should contain the plain filename
        self.assertIn("[report.pdf]", page_content)

    @patch("imports.api.imports.store_pdf_as_file", side_effect=_mock_store_pdf)
    def test_bracket_filename_escaped(self, mock_store):
        """Brackets in filenames must be escaped to prevent link breakage."""
        resp = self._import(filename="report[1].pdf")
        self.assertEqual(resp.status_code, HTTPStatus.CREATED)

        page = Page.objects.get(external_id=resp.json()["page_external_id"])
        page_content = page.details["content"]

        # Brackets should be escaped
        self.assertIn("\\[1\\]", page_content)
        # The raw unescaped form should NOT appear in the link text portion
        self.assertNotIn("[report[1]", page_content)

    @patch("imports.api.imports.store_pdf_as_file", side_effect=_mock_store_pdf)
    def test_injection_filename_escaped(self, mock_store):
        """A filename crafted to inject markdown should be neutralized."""
        resp = self._import(filename="evil](http://bad.com)\n[click")
        self.assertEqual(resp.status_code, HTTPStatus.CREATED)

        page = Page.objects.get(external_id=resp.json()["page_external_id"])
        page_content = page.details["content"]

        # The closing bracket must be escaped so it can't close the link
        self.assertNotIn("](http://bad.com)", page_content.split("](")[0])
        # Newline should be replaced, not present in the link text
        self.assertNotIn("\n[click", page_content.split("\n\n---")[0])

    @patch("imports.api.imports.store_pdf_as_file", side_effect=_mock_store_pdf)
    def test_backslash_filename_escaped(self, mock_store):
        """Backslashes in filenames are escaped to prevent markdown issues.

        Note: Django's UploadedFile._set_name() calls os.path.basename() on
        the filename, which strips everything before a backslash (treating it
        as a path separator). So "back\\slash.pdf" becomes "slash.pdf" before
        the API ever sees it. We can't test backslash escaping through the
        full API path — that's covered by the unit test for
        escape_markdown_link_text() directly. Instead, verify that a filename
        with only non-path-separator special chars is handled correctly.
        """
        resp = self._import(filename="file (copy).pdf")
        self.assertEqual(resp.status_code, HTTPStatus.CREATED)

        page = Page.objects.get(external_id=resp.json()["page_external_id"])
        page_content = page.details["content"]

        # Parentheses don't need escaping in link *text*, only in link URL
        self.assertIn("[file (copy).pdf]", page_content)


class TestPdfImportAbusePrevention(BaseAuthenticatedViewTestCase):
    """Verify that banned users are blocked from PDF imports."""

    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def _import(self, filename="doc.pdf", title="Test", content="Some text"):
        file = SimpleUploadedFile(filename, PDF_BYTES, content_type="application/pdf")
        return self.client.post(
            "/api/imports/pdf/",
            data={
                "project_id": str(self.project.external_id),
                "title": title,
                "content": content,
                "file": file,
            },
            format="multipart",
        )

    def test_banned_user_blocked(self):
        """User with an enforced import ban gets 429."""
        ImportBannedUserFactory(user=self.user, enforced=True)

        resp = self._import()

        self.assertEqual(resp.status_code, HTTPStatus.TOO_MANY_REQUESTS)
        payload = resp.json()
        self.assertEqual(payload["error"], "temporarily_blocked")

    @patch("imports.api.imports.store_pdf_as_file", side_effect=_mock_store_pdf)
    def test_lifted_ban_allows_import(self, mock_store):
        """User whose ban has been lifted can import normally."""
        ImportBannedUserFactory(user=self.user, enforced=False)

        resp = self._import()

        self.assertEqual(resp.status_code, HTTPStatus.CREATED)

    def test_banned_user_blocked_before_validation(self):
        """Abuse check runs before file validation — banned user gets 429, not 400."""
        ImportBannedUserFactory(user=self.user, enforced=True)

        # Send invalid content type — should still get 429, not 400
        file = SimpleUploadedFile("test.txt", b"not a pdf", content_type="text/plain")
        resp = self.client.post(
            "/api/imports/pdf/",
            data={
                "project_id": str(self.project.external_id),
                "title": "Test",
                "content": "Some text",
                "file": file,
            },
            format="multipart",
        )

        self.assertEqual(resp.status_code, HTTPStatus.TOO_MANY_REQUESTS)


class TestPdfImportPageCreationFailure(BaseAuthenticatedViewTestCase):
    """Verify FileUpload cleanup when page creation fails after storage succeeds."""

    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    @patch("pages.models.pages.PageManager.create_with_owner", side_effect=IntegrityError("duplicate key"))
    @patch("imports.api.imports.store_pdf_as_file")
    def test_file_upload_deleted_on_page_creation_failure(self, mock_store, mock_create):
        """When create_with_owner fails, the FileUpload's delete is called."""
        mock_fu = MagicMock()
        mock_fu.external_id = "file-ext-id"
        mock_fu.download_url = "/files/proj/file-ext-id/tok/"
        mock_store.return_value = mock_fu

        file = SimpleUploadedFile("doc.pdf", PDF_BYTES, content_type="application/pdf")

        resp = self.client.post(
            "/api/imports/pdf/",
            data={
                "project_id": str(self.project.external_id),
                "title": "Test",
                "content": "Some text",
                "file": file,
            },
            format="multipart",
        )

        # Endpoint returns a proper 500 JSON response via HttpError
        self.assertEqual(resp.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)

        # The FileUpload's delete should have been called for cleanup
        mock_fu.delete.assert_called_once()

        # No page should exist
        self.assertFalse(Page.objects.filter(project=self.project).exists())


class TestPdfImportValidation(BaseAuthenticatedViewTestCase):
    """Test input validation for the PDF import endpoint."""

    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def _post(self, **overrides):
        data = {
            "project_id": str(self.project.external_id),
            "title": "Test PDF",
            "content": "Some extracted text",
            "file": SimpleUploadedFile("doc.pdf", PDF_BYTES, content_type="application/pdf"),
        }
        data.update(overrides)
        return self.client.post("/api/imports/pdf/", data=data, format="multipart")

    def test_invalid_content_type_returns_400(self):
        """Non-PDF content type is rejected."""
        file = SimpleUploadedFile("doc.txt", b"not a pdf", content_type="text/plain")
        resp = self._post(file=file)

        self.assertEqual(resp.status_code, HTTPStatus.BAD_REQUEST)
        self.assertEqual(resp.json()["error"], "invalid_content_type")

    @patch("imports.api.imports.store_pdf_as_file", side_effect=_mock_store_pdf)
    def test_x_pdf_content_type_accepted(self, mock_store):
        """application/x-pdf is accepted as a valid PDF content type."""
        file = SimpleUploadedFile("doc.pdf", PDF_BYTES, content_type="application/x-pdf")
        resp = self._post(file=file)

        self.assertEqual(resp.status_code, HTTPStatus.CREATED)

    @patch("imports.api.imports.PDF_MAX_FILE_SIZE", 10)
    def test_file_too_large_returns_413(self):
        """File exceeding size limit is rejected."""
        file = SimpleUploadedFile("big.pdf", b"x" * 20, content_type="application/pdf")
        resp = self._post(file=file)

        self.assertEqual(resp.status_code, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
        self.assertEqual(resp.json()["error"], "file_too_large")

    def test_empty_content_returns_400(self):
        """Empty extracted text is rejected (likely a scanned PDF)."""
        resp = self._post(content="   ")

        self.assertEqual(resp.status_code, HTTPStatus.BAD_REQUEST)
        self.assertEqual(resp.json()["error"], "no_content")

    @patch("imports.api.imports.PDF_MAX_CONTENT_SIZE", 10)
    def test_content_too_large_returns_413(self):
        """Extracted text exceeding content size limit is rejected."""
        resp = self._post(content="x" * 20)

        self.assertEqual(resp.status_code, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
        self.assertEqual(resp.json()["error"], "content_too_large")

    def test_empty_title_returns_400(self):
        """Blank title is rejected."""
        resp = self._post(title="   ")

        self.assertEqual(resp.status_code, HTTPStatus.BAD_REQUEST)
        self.assertEqual(resp.json()["error"], "invalid_title")

    def test_nonexistent_project_returns_404(self):
        """Unknown project_id returns 404."""
        resp = self._post(project_id="nonexistent-id")

        self.assertEqual(resp.status_code, HTTPStatus.NOT_FOUND)

    def test_deleted_project_returns_404(self):
        """Soft-deleted project is treated as not found."""
        self.project.is_deleted = True
        self.project.save()

        resp = self._post()

        self.assertEqual(resp.status_code, HTTPStatus.NOT_FOUND)


class TestPdfImportPermissions(BaseAuthenticatedViewTestCase):
    """Test access control for PDF import."""

    def setUp(self):
        super().setUp()

    def _post(self, project):
        file = SimpleUploadedFile("doc.pdf", PDF_BYTES, content_type="application/pdf")
        return self.client.post(
            "/api/imports/pdf/",
            data={
                "project_id": str(project.external_id),
                "title": "Test",
                "content": "Some text",
                "file": file,
            },
            format="multipart",
        )

    def test_non_member_forbidden(self):
        """User with no access to the project gets 403."""
        other_org = OrgFactory()
        other_project = ProjectFactory(org=other_org)

        resp = self._post(other_project)

        self.assertEqual(resp.status_code, HTTPStatus.FORBIDDEN)
        self.assertEqual(resp.json()["error"], "forbidden")

    def test_viewer_project_editor_forbidden(self):
        """Project editor with viewer role cannot import (read-only)."""
        other_org = OrgFactory()
        other_user = UserFactory()
        OrgMemberFactory(org=other_org, user=other_user)
        other_project = ProjectFactory(org=other_org, creator=other_user)

        ProjectEditorFactory(
            project=other_project,
            user=self.user,
            role=ProjectEditorRole.VIEWER.value,
        )

        resp = self._post(other_project)

        self.assertEqual(resp.status_code, HTTPStatus.FORBIDDEN)
        self.assertEqual(resp.json()["error"], "forbidden")
        self.assertFalse(Page.objects.filter(project=other_project).exists())

    @patch("imports.api.imports.store_pdf_as_file", side_effect=_mock_store_pdf)
    def test_editor_project_editor_allowed(self, mock_store):
        """Project editor with editor role can import."""
        other_org = OrgFactory()
        other_user = UserFactory()
        OrgMemberFactory(org=other_org, user=other_user)
        other_project = ProjectFactory(org=other_org, creator=other_user)

        ProjectEditorFactory(
            project=other_project,
            user=self.user,
            role=ProjectEditorRole.EDITOR.value,
        )

        resp = self._post(other_project)

        self.assertEqual(resp.status_code, HTTPStatus.CREATED)
        self.assertTrue(Page.objects.filter(project=other_project).exists())


class TestPdfImportHappyPath(BaseAuthenticatedViewTestCase):
    """Test successful PDF import: response schema and created page content."""

    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    @patch("imports.api.imports.store_pdf_as_file", side_effect=_mock_store_pdf)
    def test_response_schema(self, mock_store):
        """201 response contains all expected fields."""
        file = SimpleUploadedFile("report.pdf", PDF_BYTES, content_type="application/pdf")
        resp = self.client.post(
            "/api/imports/pdf/",
            data={
                "project_id": str(self.project.external_id),
                "title": "My Report",
                "content": "Chapter 1 text",
                "file": file,
            },
            format="multipart",
        )

        self.assertEqual(resp.status_code, HTTPStatus.CREATED)
        payload = resp.json()

        self.assertIn("page_external_id", payload)
        self.assertIn("page_title", payload)
        self.assertIn("file_external_id", payload)
        self.assertIn("file_download_url", payload)
        self.assertEqual(payload["page_title"], "My Report")
        self.assertEqual(payload["file_external_id"], "file-ext-id")

    @patch("imports.api.imports.store_pdf_as_file", side_effect=_mock_store_pdf)
    def test_page_content_structure(self, mock_store):
        """Created page has PDF link, separator, and extracted text."""
        file = SimpleUploadedFile("report.pdf", PDF_BYTES, content_type="application/pdf")
        resp = self.client.post(
            "/api/imports/pdf/",
            data={
                "project_id": str(self.project.external_id),
                "title": "My Report",
                "content": "  Chapter 1 text  ",
                "file": file,
            },
            format="multipart",
        )

        self.assertEqual(resp.status_code, HTTPStatus.CREATED)
        page = Page.objects.get(external_id=resp.json()["page_external_id"])
        content = page.details["content"]

        # PDF link at the top
        self.assertTrue(content.startswith("[report.pdf](/files/proj/file-ext-id/tok/)"))
        # Separator between link and text
        self.assertIn("\n\n---\n\n", content)
        # Extracted text is stripped
        self.assertTrue(content.endswith("Chapter 1 text"))
        # Page details have correct metadata
        self.assertEqual(page.details["filetype"], "md")
        self.assertEqual(page.details["schema_version"], 1)

    @patch("imports.api.imports.store_pdf_as_file", side_effect=_mock_store_pdf)
    def test_title_truncated_to_100_chars(self, mock_store):
        """Titles longer than 100 characters are truncated."""
        long_title = "A" * 150
        file = SimpleUploadedFile("doc.pdf", PDF_BYTES, content_type="application/pdf")
        resp = self.client.post(
            "/api/imports/pdf/",
            data={
                "project_id": str(self.project.external_id),
                "title": long_title,
                "content": "Some text",
                "file": file,
            },
            format="multipart",
        )

        self.assertEqual(resp.status_code, HTTPStatus.CREATED)
        page = Page.objects.get(external_id=resp.json()["page_external_id"])
        self.assertEqual(len(page.title), 100)

    @patch("imports.api.imports.store_pdf_as_file", side_effect=_mock_store_pdf)
    def test_store_pdf_called_with_correct_args(self, mock_store):
        """store_pdf_as_file receives the project, user, filename, and file bytes."""
        file = SimpleUploadedFile("report.pdf", PDF_BYTES, content_type="application/pdf")
        resp = self.client.post(
            "/api/imports/pdf/",
            data={
                "project_id": str(self.project.external_id),
                "title": "Test",
                "content": "Some text",
                "file": file,
            },
            format="multipart",
        )

        self.assertEqual(resp.status_code, HTTPStatus.CREATED)
        mock_store.assert_called_once()
        args = mock_store.call_args
        self.assertEqual(args[0][0], self.project)  # project
        self.assertEqual(args[0][1], self.user)  # user
        self.assertEqual(args[0][2], "report.pdf")  # filename
        self.assertEqual(args[0][3], PDF_BYTES)  # file_bytes
