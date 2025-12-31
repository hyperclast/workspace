"""
Comprehensive tests for page update modes (append, prepend, overwrite).

These tests cover the CLI-driven page update functionality that allows
piping content to existing pages with different merge strategies.
"""

from http import HTTPStatus

from django.test import override_settings

from core.tests.common import BaseAuthenticatedViewTestCase
from pages.tests.factories import PageFactory


@override_settings(ASK_FEATURE_ENABLED=False)
class TestPageUpdateModeAppend(BaseAuthenticatedViewTestCase):
    """Tests for append mode - adding content at the end of existing content."""

    def send_update_request(self, page, content, mode="append", title=None):
        url = f"/api/pages/{page.external_id}/"
        data = {
            "title": title or page.title,
            "details": {"content": content},
            "mode": mode,
        }
        return self.send_api_request(url=url, method="put", data=data)

    def test_append_adds_content_at_end(self):
        """Basic append adds new content after existing content."""
        page = PageFactory(
            creator=self.user,
            details={"content": "Line 1", "filetype": "txt"},
        )

        response = self.send_update_request(page, "\nLine 2")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        page.refresh_from_db()
        self.assertEqual(page.details["content"], "Line 1\nLine 2")

    def test_append_to_empty_content(self):
        """Appending to empty content works correctly."""
        page = PageFactory(
            creator=self.user,
            details={"content": "", "filetype": "txt"},
        )

        response = self.send_update_request(page, "First content")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        page.refresh_from_db()
        self.assertEqual(page.details["content"], "First content")

    def test_append_to_page_with_empty_details(self):
        """Appending to a page with empty details dict works."""
        page = PageFactory(creator=self.user, details={})

        response = self.send_update_request(page, "New content")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        page.refresh_from_db()
        self.assertEqual(page.details["content"], "New content")

    def test_append_empty_content_is_noop(self):
        """Appending empty string doesn't change existing content."""
        page = PageFactory(
            creator=self.user,
            details={"content": "Original", "filetype": "txt"},
        )

        response = self.send_update_request(page, "")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        page.refresh_from_db()
        self.assertEqual(page.details["content"], "Original")

    def test_multiple_sequential_appends(self):
        """Multiple appends accumulate content correctly."""
        page = PageFactory(
            creator=self.user,
            details={"content": "Start", "filetype": "txt"},
        )

        self.send_update_request(page, " -> Middle")
        page.refresh_from_db()
        self.assertEqual(page.details["content"], "Start -> Middle")

        self.send_update_request(page, " -> End")
        page.refresh_from_db()
        self.assertEqual(page.details["content"], "Start -> Middle -> End")

    def test_append_preserves_filetype(self):
        """Append mode preserves the existing filetype."""
        page = PageFactory(
            creator=self.user,
            details={"content": "# Markdown", "filetype": "md"},
        )

        response = self.send_update_request(page, "\n\n## New Section")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        page.refresh_from_db()
        self.assertEqual(page.details["filetype"], "md")

    def test_append_preserves_schema_version(self):
        """Append mode preserves schema_version."""
        page = PageFactory(
            creator=self.user,
            details={"content": "test", "filetype": "txt", "schema_version": 1},
        )

        response = self.send_update_request(page, " more")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        page.refresh_from_db()
        self.assertEqual(page.details["schema_version"], 1)

    def test_append_with_unicode_content(self):
        """Append works correctly with unicode characters."""
        page = PageFactory(
            creator=self.user,
            details={"content": "Hello 世界", "filetype": "txt"},
        )

        response = self.send_update_request(page, " 🚀 émojis")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        page.refresh_from_db()
        self.assertEqual(page.details["content"], "Hello 世界 🚀 émojis")

    def test_append_with_newlines_and_whitespace(self):
        """Append preserves newlines and whitespace exactly."""
        page = PageFactory(
            creator=self.user,
            details={"content": "Line 1\n", "filetype": "txt"},
        )

        response = self.send_update_request(page, "\nLine 2\n\nLine 3")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        page.refresh_from_db()
        self.assertEqual(page.details["content"], "Line 1\n\nLine 2\n\nLine 3")

    def test_append_large_content(self):
        """Append handles large content correctly."""
        page = PageFactory(
            creator=self.user,
            details={"content": "Start\n", "filetype": "txt"},
        )
        large_content = "x" * 100000  # 100KB

        response = self.send_update_request(page, large_content)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        page.refresh_from_db()
        self.assertEqual(len(page.details["content"]), 100006)  # "Start\n" + 100000


@override_settings(ASK_FEATURE_ENABLED=False)
class TestPageUpdateModePrepend(BaseAuthenticatedViewTestCase):
    """Tests for prepend mode - adding content at the beginning of existing content."""

    def send_update_request(self, page, content, mode="prepend", title=None):
        url = f"/api/pages/{page.external_id}/"
        data = {
            "title": title or page.title,
            "details": {"content": content},
            "mode": mode,
        }
        return self.send_api_request(url=url, method="put", data=data)

    def test_prepend_adds_content_at_beginning(self):
        """Basic prepend adds new content before existing content."""
        page = PageFactory(
            creator=self.user,
            details={"content": "Line 2", "filetype": "txt"},
        )

        response = self.send_update_request(page, "Line 1\n")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        page.refresh_from_db()
        self.assertEqual(page.details["content"], "Line 1\nLine 2")

    def test_prepend_to_empty_content(self):
        """Prepending to empty content works correctly."""
        page = PageFactory(
            creator=self.user,
            details={"content": "", "filetype": "txt"},
        )

        response = self.send_update_request(page, "First content")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        page.refresh_from_db()
        self.assertEqual(page.details["content"], "First content")

    def test_prepend_to_page_with_empty_details(self):
        """Prepending to a page with empty details dict works."""
        page = PageFactory(creator=self.user, details={})

        response = self.send_update_request(page, "New content")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        page.refresh_from_db()
        self.assertEqual(page.details["content"], "New content")

    def test_prepend_empty_content_is_noop(self):
        """Prepending empty string doesn't change existing content."""
        page = PageFactory(
            creator=self.user,
            details={"content": "Original", "filetype": "txt"},
        )

        response = self.send_update_request(page, "")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        page.refresh_from_db()
        self.assertEqual(page.details["content"], "Original")

    def test_multiple_sequential_prepends(self):
        """Multiple prepends accumulate content correctly (LIFO order)."""
        page = PageFactory(
            creator=self.user,
            details={"content": "End", "filetype": "txt"},
        )

        self.send_update_request(page, "Middle -> ")
        page.refresh_from_db()
        self.assertEqual(page.details["content"], "Middle -> End")

        self.send_update_request(page, "Start -> ")
        page.refresh_from_db()
        self.assertEqual(page.details["content"], "Start -> Middle -> End")

    def test_prepend_preserves_filetype(self):
        """Prepend mode preserves the existing filetype."""
        page = PageFactory(
            creator=self.user,
            details={"content": "## Section", "filetype": "md"},
        )

        response = self.send_update_request(page, "# Title\n\n")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        page.refresh_from_db()
        self.assertEqual(page.details["filetype"], "md")

    def test_prepend_for_header_metadata(self):
        """Common use case: prepending header/metadata to logs."""
        page = PageFactory(
            creator=self.user,
            details={"content": "error: something failed\ninfo: retrying...", "filetype": "txt"},
        )

        header = "=== Build Log ===\nTimestamp: 2025-12-30\n\n"
        response = self.send_update_request(page, header)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        page.refresh_from_db()
        expected = "=== Build Log ===\nTimestamp: 2025-12-30\n\nerror: something failed\ninfo: retrying..."
        self.assertEqual(page.details["content"], expected)


@override_settings(ASK_FEATURE_ENABLED=False)
class TestPageUpdateModeOverwrite(BaseAuthenticatedViewTestCase):
    """Tests for overwrite mode - replacing all existing content."""

    def send_update_request(self, page, content, mode="overwrite", title=None):
        url = f"/api/pages/{page.external_id}/"
        data = {
            "title": title or page.title,
            "details": {"content": content},
            "mode": mode,
        }
        return self.send_api_request(url=url, method="put", data=data)

    def test_overwrite_replaces_all_content(self):
        """Overwrite mode replaces all existing content."""
        page = PageFactory(
            creator=self.user,
            details={"content": "Old content that should be gone", "filetype": "txt"},
        )

        response = self.send_update_request(page, "Completely new content")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        page.refresh_from_db()
        self.assertEqual(page.details["content"], "Completely new content")

    def test_overwrite_can_clear_content(self):
        """Overwrite with empty string clears content."""
        page = PageFactory(
            creator=self.user,
            details={"content": "Some content", "filetype": "txt"},
        )

        response = self.send_update_request(page, "")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        page.refresh_from_db()
        self.assertEqual(page.details["content"], "")

    def test_overwrite_on_empty_page(self):
        """Overwrite on page with no content works."""
        page = PageFactory(
            creator=self.user,
            details={"content": "", "filetype": "txt"},
        )

        response = self.send_update_request(page, "New content")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        page.refresh_from_db()
        self.assertEqual(page.details["content"], "New content")

    def test_no_mode_defaults_to_append(self):
        """When no mode is specified, behavior defaults to append."""
        page = PageFactory(
            creator=self.user,
            details={"content": "Original", "filetype": "txt"},
        )

        url = f"/api/pages/{page.external_id}/"
        data = {
            "title": page.title,
            "details": {"content": " appended"},
            # Note: no mode specified
        }
        response = self.send_api_request(url=url, method="put", data=data)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        page.refresh_from_db()
        self.assertEqual(page.details["content"], "Original appended")


@override_settings(ASK_FEATURE_ENABLED=False)
class TestPageUpdateModeMixedOperations(BaseAuthenticatedViewTestCase):
    """Tests for mixed append/prepend/overwrite operations."""

    def send_update_request(self, page, content, mode, title=None):
        url = f"/api/pages/{page.external_id}/"
        data = {
            "title": title or page.title,
            "details": {"content": content},
            "mode": mode,
        }
        return self.send_api_request(url=url, method="put", data=data)

    def test_append_then_prepend(self):
        """Append followed by prepend produces correct order."""
        page = PageFactory(
            creator=self.user,
            details={"content": "Middle", "filetype": "txt"},
        )

        self.send_update_request(page, " End", "append")
        page.refresh_from_db()
        self.assertEqual(page.details["content"], "Middle End")

        self.send_update_request(page, "Start ", "prepend")
        page.refresh_from_db()
        self.assertEqual(page.details["content"], "Start Middle End")

    def test_prepend_then_append(self):
        """Prepend followed by append produces correct order."""
        page = PageFactory(
            creator=self.user,
            details={"content": "Middle", "filetype": "txt"},
        )

        self.send_update_request(page, "Start ", "prepend")
        page.refresh_from_db()
        self.assertEqual(page.details["content"], "Start Middle")

        self.send_update_request(page, " End", "append")
        page.refresh_from_db()
        self.assertEqual(page.details["content"], "Start Middle End")

    def test_overwrite_after_appends(self):
        """Overwrite clears accumulated append content."""
        page = PageFactory(
            creator=self.user,
            details={"content": "Base", "filetype": "txt"},
        )

        self.send_update_request(page, " + append1", "append")
        self.send_update_request(page, " + append2", "append")
        page.refresh_from_db()
        self.assertEqual(page.details["content"], "Base + append1 + append2")

        self.send_update_request(page, "Fresh start", "overwrite")
        page.refresh_from_db()
        self.assertEqual(page.details["content"], "Fresh start")

    def test_log_accumulation_pattern(self):
        """Simulates CLI log accumulation use case."""
        page = PageFactory(
            creator=self.user,
            title="Build Log",
            details={"content": "", "filetype": "txt"},
        )

        # Simulate multiple log entries being appended over time
        self.send_update_request(page, "[10:00] Build started\n", "append")
        self.send_update_request(page, "[10:01] Compiling...\n", "append")
        self.send_update_request(page, "[10:02] Tests running...\n", "append")
        self.send_update_request(page, "[10:03] Build complete\n", "append")

        page.refresh_from_db()
        expected = (
            "[10:00] Build started\n" "[10:01] Compiling...\n" "[10:02] Tests running...\n" "[10:03] Build complete\n"
        )
        self.assertEqual(page.details["content"], expected)


@override_settings(ASK_FEATURE_ENABLED=False)
class TestPageUpdateModeValidation(BaseAuthenticatedViewTestCase):
    """Tests for mode validation and error handling."""

    def test_invalid_mode_returns_422(self):
        """Invalid mode value returns 422 Unprocessable Entity."""
        page = PageFactory(creator=self.user)

        url = f"/api/pages/{page.external_id}/"
        data = {
            "title": page.title,
            "details": {"content": "test"},
            "mode": "invalid",
        }
        response = self.send_api_request(url=url, method="put", data=data)

        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)

    def test_mode_is_case_sensitive(self):
        """Mode must be lowercase - uppercase variants are rejected."""
        page = PageFactory(creator=self.user)

        for invalid_mode in ["APPEND", "Append", "PREPEND", "Prepend", "OVERWRITE", "Overwrite"]:
            url = f"/api/pages/{page.external_id}/"
            data = {
                "title": page.title,
                "details": {"content": "test"},
                "mode": invalid_mode,
            }
            response = self.send_api_request(url=url, method="put", data=data)
            self.assertEqual(
                response.status_code,
                HTTPStatus.UNPROCESSABLE_ENTITY,
                f"Mode '{invalid_mode}' should be rejected",
            )

    def test_mode_with_null_details_is_noop(self):
        """Mode with null details doesn't crash."""
        page = PageFactory(
            creator=self.user,
            details={"content": "Original", "filetype": "txt"},
        )

        url = f"/api/pages/{page.external_id}/"
        data = {
            "title": page.title,
            "details": None,
            "mode": "append",
        }
        response = self.send_api_request(url=url, method="put", data=data)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        page.refresh_from_db()
        # Content should remain unchanged since details is None
        self.assertEqual(page.details["content"], "Original")

    def test_mode_with_details_missing_content_key(self):
        """Mode with details that has no content key doesn't crash."""
        page = PageFactory(
            creator=self.user,
            details={"content": "Original", "filetype": "txt"},
        )

        url = f"/api/pages/{page.external_id}/"
        data = {
            "title": page.title,
            "details": {"filetype": "md"},  # No content key
            "mode": "append",
        }
        response = self.send_api_request(url=url, method="put", data=data)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        page.refresh_from_db()
        # Filetype should be updated, content unchanged
        self.assertEqual(page.details["filetype"], "md")


@override_settings(ASK_FEATURE_ENABLED=False)
class TestPageUpdateModePermissions(BaseAuthenticatedViewTestCase):
    """Tests for permissions with update modes."""

    def test_cannot_append_to_page_not_owned(self):
        """Users cannot append to pages they don't own."""
        page = PageFactory(details={"content": "Secret", "filetype": "txt"})  # Different owner

        url = f"/api/pages/{page.external_id}/"
        data = {
            "title": page.title,
            "details": {"content": "Hacked!"},
            "mode": "append",
        }
        response = self.send_api_request(url=url, method="put", data=data)

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        page.refresh_from_db()
        self.assertEqual(page.details["content"], "Secret")

    def test_cannot_prepend_to_page_not_owned(self):
        """Users cannot prepend to pages they don't own."""
        page = PageFactory(details={"content": "Secret", "filetype": "txt"})

        url = f"/api/pages/{page.external_id}/"
        data = {
            "title": page.title,
            "details": {"content": "Hacked!"},
            "mode": "prepend",
        }
        response = self.send_api_request(url=url, method="put", data=data)

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        page.refresh_from_db()
        self.assertEqual(page.details["content"], "Secret")

    def test_cannot_overwrite_page_not_owned(self):
        """Users cannot overwrite pages they don't own."""
        page = PageFactory(details={"content": "Secret", "filetype": "txt"})

        url = f"/api/pages/{page.external_id}/"
        data = {
            "title": page.title,
            "details": {"content": "Hacked!"},
            "mode": "overwrite",
        }
        response = self.send_api_request(url=url, method="put", data=data)

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        page.refresh_from_db()
        self.assertEqual(page.details["content"], "Secret")


@override_settings(ASK_FEATURE_ENABLED=False)
class TestPageUpdateModeWithTitleChange(BaseAuthenticatedViewTestCase):
    """Tests for updating both title and content with modes."""

    def test_append_with_title_change(self):
        """Can append content and change title in same request."""
        page = PageFactory(
            creator=self.user,
            title="Old Title",
            details={"content": "Content", "filetype": "txt"},
        )

        url = f"/api/pages/{page.external_id}/"
        data = {
            "title": "New Title",
            "details": {"content": " appended"},
            "mode": "append",
        }
        response = self.send_api_request(url=url, method="put", data=data)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        page.refresh_from_db()
        self.assertEqual(page.title, "New Title")
        self.assertEqual(page.details["content"], "Content appended")

    def test_prepend_with_title_change(self):
        """Can prepend content and change title in same request."""
        page = PageFactory(
            creator=self.user,
            title="Old Title",
            details={"content": "Content", "filetype": "txt"},
        )

        url = f"/api/pages/{page.external_id}/"
        data = {
            "title": "New Title",
            "details": {"content": "prepended "},
            "mode": "prepend",
        }
        response = self.send_api_request(url=url, method="put", data=data)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        page.refresh_from_db()
        self.assertEqual(page.title, "New Title")
        self.assertEqual(page.details["content"], "prepended Content")
