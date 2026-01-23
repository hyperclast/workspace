import zipfile
from http import HTTPStatus
from io import BytesIO

from core.tests.common import BaseAuthenticatedViewTestCase
from pages.tests.factories import PageFactory, ProjectFactory
from users.constants import OrgMemberRole
from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory


class TestPageDownloadAPI(BaseAuthenticatedViewTestCase):
    """Test GET /api/pages/{external_id}/download/ endpoint."""

    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def send_download_request(self, external_id):
        url = f"/api/pages/{external_id}/download/"
        return self.client.get(url)

    # ========================================
    # Basic Functionality Tests
    # ========================================

    def test_download_page_returns_markdown_file(self):
        """Test downloading a page returns a markdown file with correct content."""
        page = PageFactory(
            project=self.project,
            creator=self.user,
            title="My Test Page",
            details={"content": "This is the page content."},
        )

        response = self.send_download_request(page.external_id)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response["Content-Type"], "text/markdown; charset=utf-8")
        self.assertIn('attachment; filename="My-Test-Page.md"', response["Content-Disposition"])

        content = response.content.decode("utf-8")
        self.assertIn("# My Test Page", content)
        self.assertIn("This is the page content.", content)

    def test_download_page_with_empty_content(self):
        """Test downloading a page with empty content still works."""
        page = PageFactory(
            project=self.project,
            creator=self.user,
            title="Empty Page",
            details={"content": ""},
        )

        response = self.send_download_request(page.external_id)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        content = response.content.decode("utf-8")
        self.assertIn("# Empty Page", content)

    def test_download_page_with_missing_content_key(self):
        """Test downloading a page where details dict has no 'content' key still works."""
        page = PageFactory(
            project=self.project,
            creator=self.user,
            title="Missing Content Key Page",
            details={},
        )

        response = self.send_download_request(page.external_id)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        content = response.content.decode("utf-8")
        self.assertIn("# Missing Content Key Page", content)

    # ========================================
    # Filename Sanitization Tests (Adversarial)
    # ========================================

    def test_download_page_sanitizes_special_characters_in_filename(self):
        """Test that special characters in title are sanitized for filename."""
        page = PageFactory(
            project=self.project,
            creator=self.user,
            title='File/With\\Special:Chars*?"<>|',
            details={"content": "Test content"},
        )

        response = self.send_download_request(page.external_id)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        # All special chars should be replaced with dashes
        self.assertNotIn("/", response["Content-Disposition"])
        self.assertNotIn("\\", response["Content-Disposition"])
        self.assertNotIn(":", response["Content-Disposition"])
        self.assertNotIn("*", response["Content-Disposition"])
        self.assertNotIn("?", response["Content-Disposition"])
        self.assertNotIn('"', response["Content-Disposition"].replace('filename="', "").replace('.md"', ""))
        self.assertNotIn("<", response["Content-Disposition"])
        self.assertNotIn(">", response["Content-Disposition"])
        self.assertNotIn("|", response["Content-Disposition"])

    def test_download_page_with_spaces_in_title(self):
        """Test that spaces in title are handled properly."""
        page = PageFactory(
            project=self.project,
            creator=self.user,
            title="Page With Multiple   Spaces",
            details={"content": "Test content"},
        )

        response = self.send_download_request(page.external_id)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        # Multiple spaces should be collapsed
        self.assertIn(".md", response["Content-Disposition"])

    def test_download_page_with_only_special_characters_title(self):
        """Test that a title with only special characters falls back to 'Untitled'."""
        page = PageFactory(
            project=self.project,
            creator=self.user,
            title="???***",
            details={"content": "Test content"},
        )

        response = self.send_download_request(page.external_id)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        # Should fall back to Untitled after sanitization
        self.assertIn('filename="', response["Content-Disposition"])

    def test_download_page_with_unicode_title(self):
        """Test downloading a page with unicode characters in title."""
        page = PageFactory(
            project=self.project,
            creator=self.user,
            title="日本語タイトル",
            details={"content": "Japanese content 日本語"},
        )

        response = self.send_download_request(page.external_id)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        content = response.content.decode("utf-8")
        self.assertIn("# 日本語タイトル", content)
        self.assertIn("Japanese content 日本語", content)

    def test_download_page_with_emoji_title(self):
        """Test downloading a page with emoji in title."""
        page = PageFactory(
            project=self.project,
            creator=self.user,
            title="My Page 🚀",
            details={"content": "Content with emoji 😀"},
        )

        response = self.send_download_request(page.external_id)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        content = response.content.decode("utf-8")
        self.assertIn("🚀", content)
        self.assertIn("😀", content)

    def test_download_page_with_leading_trailing_dots(self):
        """Test that leading/trailing dots are stripped from filename."""
        page = PageFactory(
            project=self.project,
            creator=self.user,
            title="...My Page...",
            details={"content": "Test"},
        )

        response = self.send_download_request(page.external_id)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        # Dots should be stripped
        self.assertIn(".md", response["Content-Disposition"])

    def test_download_page_with_very_long_title(self):
        """Test downloading a page with a very long title."""
        long_title = "A" * 100  # Max title length
        page = PageFactory(
            project=self.project,
            creator=self.user,
            title=long_title,
            details={"content": "Test"},
        )

        response = self.send_download_request(page.external_id)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        content = response.content.decode("utf-8")
        self.assertIn(f"# {long_title}", content)

    # ========================================
    # Authorization Tests (Adversarial)
    # ========================================

    def test_download_page_requires_authentication(self):
        """Test that unauthenticated users cannot download pages."""
        page = PageFactory(project=self.project, creator=self.user)
        self.client.logout()

        response = self.send_download_request(page.external_id)

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)

    def test_download_page_user_has_no_access_returns_404(self):
        """Test that users without access cannot download pages."""
        # Create page in a different org
        other_org = OrgFactory()
        other_project = ProjectFactory(org=other_org)
        page = PageFactory(project=other_project)

        response = self.send_download_request(page.external_id)

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_download_nonexistent_page_returns_404(self):
        """Test that downloading a non-existent page returns 404."""
        response = self.send_download_request("nonexistent123")

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_download_deleted_page_returns_404(self):
        """Test that downloading a soft-deleted page returns 404."""
        page = PageFactory(project=self.project, creator=self.user)
        page.is_deleted = True
        page.save()

        response = self.send_download_request(page.external_id)

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_org_member_can_download_org_page(self):
        """Test that org members can download pages in org projects."""
        # Create page by another org member
        other_member = UserFactory()
        OrgMemberFactory(org=self.org, user=other_member, role=OrgMemberRole.MEMBER.value)
        page = PageFactory(project=self.project, creator=other_member)

        response = self.send_download_request(page.external_id)

        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_project_editor_can_download_project_page(self):
        """Test that project editors can download pages in shared projects."""
        # Create org and project that user is NOT an org member of
        other_org = OrgFactory()
        other_project = ProjectFactory(org=other_org)
        page = PageFactory(project=other_project)

        # Add user as project editor
        other_project.editors.add(self.user)

        response = self.send_download_request(page.external_id)

        self.assertEqual(response.status_code, HTTPStatus.OK)


class TestProjectDownloadAPI(BaseAuthenticatedViewTestCase):
    """Test GET /api/projects/{external_id}/download/ endpoint."""

    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def send_download_request(self, external_id):
        url = f"/api/projects/{external_id}/download/"
        return self.client.get(url)

    def extract_zip_contents(self, response):
        """Helper to extract ZIP contents from response."""
        zip_buffer = BytesIO(response.content)
        with zipfile.ZipFile(zip_buffer, "r") as zf:
            return {name: zf.read(name).decode("utf-8") for name in zf.namelist()}

    # ========================================
    # Basic Functionality Tests
    # ========================================

    def test_download_project_returns_zip_file(self):
        """Test downloading a project returns a ZIP file."""
        PageFactory(project=self.project, creator=self.user, title="Page 1")
        PageFactory(project=self.project, creator=self.user, title="Page 2")

        response = self.send_download_request(self.project.external_id)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response["Content-Type"], "application/zip")
        self.assertIn(".zip", response["Content-Disposition"])

    def test_download_project_contains_all_pages_in_folder(self):
        """Test that downloaded ZIP contains all project pages inside a project folder."""
        self.project.name = "My Project"
        self.project.save()
        PageFactory(
            project=self.project,
            creator=self.user,
            title="First Page",
            details={"content": "First content"},
        )
        PageFactory(
            project=self.project,
            creator=self.user,
            title="Second Page",
            details={"content": "Second content"},
        )

        response = self.send_download_request(self.project.external_id)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        contents = self.extract_zip_contents(response)

        self.assertEqual(len(contents), 2)
        # Files should be inside project folder
        self.assertIn("My-Project/First-Page.md", contents)
        self.assertIn("My-Project/Second-Page.md", contents)
        self.assertIn("# First Page", contents["My-Project/First-Page.md"])
        self.assertIn("First content", contents["My-Project/First-Page.md"])
        self.assertIn("# Second Page", contents["My-Project/Second-Page.md"])
        self.assertIn("Second content", contents["My-Project/Second-Page.md"])

    def test_download_empty_project_returns_empty_zip(self):
        """Test downloading a project with no pages returns empty ZIP."""
        response = self.send_download_request(self.project.external_id)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        contents = self.extract_zip_contents(response)
        self.assertEqual(len(contents), 0)

    def test_download_project_excludes_deleted_pages(self):
        """Test that deleted pages are not included in the ZIP."""
        self.project.name = "Test Project"
        self.project.save()
        page1 = PageFactory(project=self.project, creator=self.user, title="Active Page")
        page2 = PageFactory(project=self.project, creator=self.user, title="Deleted Page")
        page2.is_deleted = True
        page2.save()

        response = self.send_download_request(self.project.external_id)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        contents = self.extract_zip_contents(response)

        self.assertEqual(len(contents), 1)
        self.assertIn("Test-Project/Active-Page.md", contents)
        self.assertNotIn("Test-Project/Deleted-Page.md", contents)

    # ========================================
    # Duplicate Title Handling Tests (Adversarial)
    # ========================================

    def test_download_project_handles_duplicate_titles(self):
        """Test that duplicate page titles get unique filenames."""
        self.project.name = "TestProj"
        self.project.save()
        PageFactory(
            project=self.project,
            creator=self.user,
            title="Same Title",
            details={"content": "First"},
        )
        PageFactory(
            project=self.project,
            creator=self.user,
            title="Same Title",
            details={"content": "Second"},
        )
        PageFactory(
            project=self.project,
            creator=self.user,
            title="Same Title",
            details={"content": "Third"},
        )

        response = self.send_download_request(self.project.external_id)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        contents = self.extract_zip_contents(response)

        self.assertEqual(len(contents), 3)
        # First one gets no suffix, subsequent ones get - 2, - 3
        self.assertIn("TestProj/Same-Title.md", contents)
        self.assertIn("TestProj/Same-Title - 2.md", contents)
        self.assertIn("TestProj/Same-Title - 3.md", contents)

    def test_download_project_handles_titles_that_become_same_after_sanitization(self):
        """Test that titles which become identical after sanitization get unique names."""
        PageFactory(
            project=self.project,
            creator=self.user,
            title="Test/Page",
            details={"content": "First"},
        )
        PageFactory(
            project=self.project,
            creator=self.user,
            title="Test:Page",
            details={"content": "Second"},
        )
        PageFactory(
            project=self.project,
            creator=self.user,
            title="Test*Page",
            details={"content": "Third"},
        )

        response = self.send_download_request(self.project.external_id)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        contents = self.extract_zip_contents(response)

        # All sanitize to "Test-Page", so should get unique suffixes
        self.assertEqual(len(contents), 3)

    # ========================================
    # Filename Sanitization Tests (Adversarial)
    # ========================================

    def test_download_project_sanitizes_project_name(self):
        """Test that project name is sanitized for ZIP filename."""
        self.project.name = 'Project/With\\Special:Chars*?"<>|'
        self.project.save()

        response = self.send_download_request(self.project.external_id)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        # Special chars should be sanitized
        disposition = response["Content-Disposition"]
        self.assertNotIn("/", disposition.split("=")[1])
        self.assertNotIn("\\", disposition)
        self.assertNotIn(":", disposition.split("=")[1])

    def test_download_project_with_unicode_names(self):
        """Test downloading project with unicode in project and page names."""
        self.project.name = "プロジェクト"
        self.project.save()
        PageFactory(
            project=self.project,
            creator=self.user,
            title="日本語ページ",
            details={"content": "内容"},
        )

        response = self.send_download_request(self.project.external_id)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        contents = self.extract_zip_contents(response)
        self.assertEqual(len(contents), 1)

        # Check content is properly encoded
        for filename, content in contents.items():
            self.assertIn("日本語ページ", content)
            self.assertIn("内容", content)

    # ========================================
    # Authorization Tests (Adversarial)
    # ========================================

    def test_download_project_requires_authentication(self):
        """Test that unauthenticated users cannot download projects."""
        self.client.logout()

        response = self.send_download_request(self.project.external_id)

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)

    def test_download_project_user_has_no_access_returns_404(self):
        """Test that users without access cannot download projects."""
        other_org = OrgFactory()
        other_project = ProjectFactory(org=other_org)

        response = self.send_download_request(other_project.external_id)

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_download_nonexistent_project_returns_404(self):
        """Test that downloading a non-existent project returns 404."""
        response = self.send_download_request("nonexistent123")

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_download_deleted_project_returns_404(self):
        """Test that downloading a soft-deleted project returns 404."""
        self.project.is_deleted = True
        self.project.save()

        response = self.send_download_request(self.project.external_id)

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_org_member_can_download_org_project(self):
        """Test that org members can download projects in their org."""
        # Create page by another org member
        other_member = UserFactory()
        OrgMemberFactory(org=self.org, user=other_member, role=OrgMemberRole.MEMBER.value)
        other_project = ProjectFactory(org=self.org, creator=other_member)
        PageFactory(project=other_project, creator=other_member, title="Test Page")

        response = self.send_download_request(other_project.external_id)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        contents = self.extract_zip_contents(response)
        self.assertEqual(len(contents), 1)

    def test_project_editor_can_download_shared_project(self):
        """Test that project editors can download shared projects."""
        # Create org and project that user is NOT an org member of
        other_org = OrgFactory()
        other_project = ProjectFactory(org=other_org)
        PageFactory(project=other_project, title="Shared Page")

        # Add user as project editor
        other_project.editors.add(self.user)

        response = self.send_download_request(other_project.external_id)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        contents = self.extract_zip_contents(response)
        self.assertEqual(len(contents), 1)

    # ========================================
    # Large Data Tests (Adversarial)
    # ========================================

    def test_download_project_with_many_pages(self):
        """Test downloading a project with many pages."""
        for i in range(50):
            PageFactory(
                project=self.project,
                creator=self.user,
                title=f"Page {i}",
                details={"content": f"Content for page {i}"},
            )

        response = self.send_download_request(self.project.external_id)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        contents = self.extract_zip_contents(response)
        self.assertEqual(len(contents), 50)

    def test_download_project_with_large_page_content(self):
        """Test downloading a project with pages containing large content."""
        self.project.name = "LargeProj"
        self.project.save()
        large_content = "A" * 100000  # 100KB of content
        PageFactory(
            project=self.project,
            creator=self.user,
            title="Large Page",
            details={"content": large_content},
        )

        response = self.send_download_request(self.project.external_id)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        contents = self.extract_zip_contents(response)
        self.assertIn("LargeProj/Large-Page.md", contents)
        self.assertIn(large_content, contents["LargeProj/Large-Page.md"])


class TestDownloadFilenameEdgeCases(BaseAuthenticatedViewTestCase):
    """Test edge cases for filename sanitization."""

    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def test_page_title_with_newlines(self):
        """Test that newlines in title are handled."""
        page = PageFactory(
            project=self.project,
            creator=self.user,
            title="Title\nWith\nNewlines",
            details={"content": "Test"},
        )

        response = self.client.get(f"/api/pages/{page.external_id}/download/")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        # Should not have newlines in filename
        self.assertNotIn("\n", response["Content-Disposition"])

    def test_page_title_with_tabs(self):
        """Test that tabs in title are handled."""
        page = PageFactory(
            project=self.project,
            creator=self.user,
            title="Title\tWith\tTabs",
            details={"content": "Test"},
        )

        response = self.client.get(f"/api/pages/{page.external_id}/download/")

        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_page_title_starting_with_dash(self):
        """Test that titles starting with dash are handled."""
        page = PageFactory(
            project=self.project,
            creator=self.user,
            title="- My Page",
            details={"content": "Test"},
        )

        response = self.client.get(f"/api/pages/{page.external_id}/download/")

        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_page_title_with_only_whitespace(self):
        """Test that whitespace-only title is handled."""
        page = PageFactory(
            project=self.project,
            creator=self.user,
            title="   ",
            details={"content": "Test"},
        )

        response = self.client.get(f"/api/pages/{page.external_id}/download/")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        # Should fall back to some default
        self.assertIn('filename="', response["Content-Disposition"])


class TestContentDispositionHeaderSecurity(BaseAuthenticatedViewTestCase):
    """Test that Content-Disposition headers are properly secured against injection attacks.

    These tests verify that Django's content_disposition_header utility is being used
    to properly encode filenames, preventing header injection vulnerabilities.
    """

    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)
        self.project = ProjectFactory(org=self.org, creator=self.user, name="TestProject")

    # ========================================
    # Page Download Header Injection Tests
    # ========================================

    def test_page_download_sanitizes_double_quotes_in_filename(self):
        """Test that double quotes in filename are sanitized to prevent header injection.

        Double quotes are removed by sanitize_filename() before reaching the header,
        which is the first line of defense. content_disposition_header() provides
        defense-in-depth for any characters that might slip through.
        """
        page = PageFactory(
            project=self.project,
            creator=self.user,
            title='File"With"Quotes',
            details={"content": "Test"},
        )

        response = self.client.get(f"/api/pages/{page.external_id}/download/")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        disposition = response["Content-Disposition"]
        # Quotes are sanitized out, so the filename should be clean
        # The header should have exactly 2 quotes (surrounding the filename)
        # or use RFC 5987 encoding (filename*=)
        self.assertIn("attachment", disposition)
        # Verify no unescaped quotes could break out of the filename attribute
        # After the opening quote, there should be no raw quote until the closing one
        if 'filename="' in disposition:
            # Extract the filename value and verify it's safe
            # The quotes are removed by sanitize_filename, so filename should be "File-With-Quotes.md"
            self.assertIn("File-With-Quotes.md", disposition)

    def test_page_download_encodes_newlines_in_filename(self):
        """Test that newlines are encoded to prevent HTTP response splitting."""
        page = PageFactory(
            project=self.project,
            creator=self.user,
            title="File\nWith\nNewlines",
            details={"content": "Test"},
        )

        response = self.client.get(f"/api/pages/{page.external_id}/download/")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        disposition = response["Content-Disposition"]
        # Raw newlines must NOT appear in the header (would allow response splitting)
        self.assertNotIn("\n", disposition)
        self.assertNotIn("\r", disposition)

    def test_page_download_encodes_carriage_returns_in_filename(self):
        """Test that carriage returns are encoded to prevent HTTP response splitting."""
        page = PageFactory(
            project=self.project,
            creator=self.user,
            title="File\rWith\rCR",
            details={"content": "Test"},
        )

        response = self.client.get(f"/api/pages/{page.external_id}/download/")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        disposition = response["Content-Disposition"]
        # Raw carriage returns must NOT appear
        self.assertNotIn("\r", disposition)

    def test_page_download_neutralizes_crlf_injection_attempt(self):
        """Test that CRLF injection attempts are properly neutralized.

        The sanitize_filename() function converts whitespace (including CRLF) to dashes,
        and removes colons. content_disposition_header() provides additional protection.
        The key security property is that raw CRLF cannot appear in the header.
        """
        page = PageFactory(
            project=self.project,
            creator=self.user,
            title="file.txt\r\nX-Injected-Header: malicious",
            details={"content": "Test"},
        )

        response = self.client.get(f"/api/pages/{page.external_id}/download/")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        disposition = response["Content-Disposition"]
        # The critical security check: raw CRLF must NOT appear (would enable response splitting)
        self.assertNotIn("\r\n", disposition)
        self.assertNotIn("\r", disposition)
        self.assertNotIn("\n", disposition)
        # Colons are also sanitized out (prevents header-like syntax)
        self.assertNotIn(":", disposition.split("=", 1)[1])  # Check after the "attachment; filename="

    def test_page_download_handles_unicode_with_rfc5987(self):
        """Test that unicode filenames use RFC 5987 encoding for browser compatibility."""
        page = PageFactory(
            project=self.project,
            creator=self.user,
            title="日本語ファイル",
            details={"content": "Test"},
        )

        response = self.client.get(f"/api/pages/{page.external_id}/download/")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        disposition = response["Content-Disposition"]
        # Unicode should be percent-encoded in filename*= format
        self.assertIn("filename*=utf-8''", disposition)
        # Should contain percent-encoded Japanese characters
        self.assertIn("%", disposition)

    # ========================================
    # Project Download Header Injection Tests
    # ========================================

    def test_project_download_sanitizes_double_quotes_in_filename(self):
        """Test that double quotes in project name are sanitized to prevent header injection.

        Double quotes are removed by sanitize_filename() before reaching the header.
        """
        self.project.name = 'Project"With"Quotes'
        self.project.save()
        PageFactory(project=self.project, creator=self.user, title="Page")

        response = self.client.get(f"/api/projects/{self.project.external_id}/download/")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        disposition = response["Content-Disposition"]
        self.assertIn("attachment", disposition)
        # Quotes are sanitized out, filename should be "Project-With-Quotes.zip"
        if 'filename="' in disposition:
            self.assertIn("Project-With-Quotes.zip", disposition)

    def test_project_download_encodes_newlines_in_filename(self):
        """Test that newlines in project name are encoded."""
        self.project.name = "Project\nWith\nNewlines"
        self.project.save()
        PageFactory(project=self.project, creator=self.user, title="Page")

        response = self.client.get(f"/api/projects/{self.project.external_id}/download/")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        disposition = response["Content-Disposition"]
        self.assertNotIn("\n", disposition)
        self.assertNotIn("\r", disposition)

    def test_project_download_neutralizes_crlf_injection_attempt(self):
        """Test that CRLF injection attempts in project name are neutralized.

        The critical security property is that raw CRLF cannot appear in the header,
        which would enable HTTP response splitting attacks.
        """
        self.project.name = "project.zip\r\nContent-Type: text/html\r\n\r\n<script>alert(1)</script>"
        self.project.save()
        PageFactory(project=self.project, creator=self.user, title="Page")

        response = self.client.get(f"/api/projects/{self.project.external_id}/download/")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        disposition = response["Content-Disposition"]
        # The critical security checks: raw CRLF must NOT appear
        self.assertNotIn("\r\n", disposition)
        self.assertNotIn("\r", disposition)
        self.assertNotIn("\n", disposition)
        # Angle brackets are sanitized out (< and > are in the invalid_chars regex)
        self.assertNotIn("<", disposition)
        self.assertNotIn(">", disposition)

    def test_project_download_handles_unicode_with_rfc5987(self):
        """Test that unicode project names use RFC 5987 encoding."""
        self.project.name = "Projet-Francais-Cafe"
        self.project.save()
        PageFactory(project=self.project, creator=self.user, title="Page")

        response = self.client.get(f"/api/projects/{self.project.external_id}/download/")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        # Should work without issues
        self.assertIn("attachment", response["Content-Disposition"])
