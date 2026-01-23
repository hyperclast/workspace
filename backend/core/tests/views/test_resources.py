from http import HTTPStatus
from pathlib import Path
from unittest.mock import mock_open, patch

from django.conf import settings
from django.shortcuts import reverse
from django.test import override_settings

from core.tests.common import BaseViewTestCase


class TestApiDocsView(BaseViewTestCase):
    """Test cases for API documentation views."""

    def test_ok_api_docs_index_defaults_to_overview(self):
        """Test that /dev/api/ defaults to overview documentation."""
        response = self.send_request(reverse("core:api_docs_index"))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, "core/docs/api_docs.html")
        self.assertEqual(response.context["doc_name"], "overview")
        self.assertEqual(response.context["page_title"], "API Documentation - Overview")

    def test_ok_api_docs_overview(self):
        """Test that overview documentation renders correctly."""
        response = self.send_request(reverse("core:api_docs", kwargs={"doc_name": "overview"}))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, "core/docs/api_docs.html")
        self.assertEqual(response.context["doc_name"], "overview")
        self.assertIn("content", response.context)
        # Verify markdown was processed to HTML
        self.assertIn("<h1", response.context["content"])

    def test_ok_api_docs_pages(self):
        """Test that pages documentation renders correctly."""
        response = self.send_request(reverse("core:api_docs", kwargs={"doc_name": "pages"}))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, "core/docs/api_docs.html")
        self.assertEqual(response.context["doc_name"], "pages")
        self.assertEqual(response.context["page_title"], "API Documentation - Pages")
        self.assertIn("content", response.context)

    def test_ok_api_docs_users(self):
        """Test that users documentation renders correctly."""
        response = self.send_request(reverse("core:api_docs", kwargs={"doc_name": "users"}))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, "core/docs/api_docs.html")
        self.assertEqual(response.context["doc_name"], "users")
        self.assertEqual(response.context["page_title"], "API Documentation - Users")
        self.assertIn("content", response.context)

    def test_ok_api_docs_ask(self):
        """Test that ask documentation renders correctly."""
        response = self.send_request(reverse("core:api_docs", kwargs={"doc_name": "ask"}))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, "core/docs/api_docs.html")
        self.assertEqual(response.context["doc_name"], "ask")
        self.assertEqual(response.context["page_title"], "API Documentation - Ask")
        self.assertIn("content", response.context)

    def test_404_invalid_doc_name(self):
        """Test that requesting an invalid doc name returns 404."""
        response = self.send_request(reverse("core:api_docs", kwargs={"doc_name": "invalid"}))

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_404_nonexistent_doc_file(self):
        """Test that a missing markdown file returns 404."""
        # Mock open to raise FileNotFoundError
        with patch("builtins.open", side_effect=FileNotFoundError):
            response = self.send_request(reverse("core:api_docs", kwargs={"doc_name": "overview"}))

            self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_markdown_processing_with_code_blocks(self):
        """Test that markdown with code blocks is processed correctly."""
        markdown_content = """
# Test Heading

```python
def hello():
    return "world"
```
"""
        docs_path = Path(settings.BASE_DIR) / "core" / "docs" / "api" / "overview.md"

        with patch("builtins.open", mock_open(read_data=markdown_content)):
            with patch("pathlib.Path.__truediv__", return_value=docs_path):
                response = self.send_request(reverse("core:api_docs", kwargs={"doc_name": "overview"}))

                self.assertEqual(response.status_code, HTTPStatus.OK)
                content = response.context["content"]
                # Check that code block was processed
                self.assertIn("<pre>", content)
                self.assertIn("<code", content)

    def test_markdown_processing_with_tables(self):
        """Test that markdown with tables is processed correctly."""
        markdown_content = """
| Header 1 | Header 2 |
|----------|----------|
| Cell 1   | Cell 2   |
"""
        docs_path = Path(settings.BASE_DIR) / "core" / "docs" / "api" / "overview.md"

        with patch("builtins.open", mock_open(read_data=markdown_content)):
            with patch("pathlib.Path.__truediv__", return_value=docs_path):
                response = self.send_request(reverse("core:api_docs", kwargs={"doc_name": "overview"}))

                self.assertEqual(response.status_code, HTTPStatus.OK)
                content = response.context["content"]
                # Check that table was processed
                self.assertIn("<table>", content)
                self.assertIn("<thead>", content)
                self.assertIn("<tbody>", content)

    def test_context_variables(self):
        """Test that all expected context variables are present."""
        response = self.send_request(reverse("core:api_docs", kwargs={"doc_name": "pages"}))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("content", response.context)
        self.assertIn("doc_name", response.context)
        self.assertIn("page_title", response.context)
        self.assertEqual(response.context["doc_name"], "pages")
        self.assertEqual(response.context["page_title"], "API Documentation - Pages")

    def test_allowed_docs_validation(self):
        """Test that only allowed doc names are accepted."""
        # These docs should always be accessible regardless of feature flags
        always_allowed_docs = ["overview", "ask", "pages", "users", "orgs", "projects", "mentions"]

        for doc_name in always_allowed_docs:
            response = self.send_request(reverse("core:api_docs", kwargs={"doc_name": doc_name}))
            self.assertEqual(
                response.status_code,
                HTTPStatus.OK,
                f"Doc '{doc_name}' should be allowed but returned {response.status_code}",
            )

        # Test disallowed doc names (simple strings that can be URL-encoded)
        disallowed_docs = ["admin", "secret", "test", "config", "internal"]

        for doc_name in disallowed_docs:
            response = self.send_request(reverse("core:api_docs", kwargs={"doc_name": doc_name}))
            self.assertEqual(
                response.status_code,
                HTTPStatus.NOT_FOUND,
                f"Doc '{doc_name}' should not be allowed but returned {response.status_code}",
            )


class TestFilesDocsFeatureFlag(BaseViewTestCase):
    """Test cases for files documentation feature flag behavior."""

    @override_settings(FILEHUB_FEATURE_ENABLED=True)
    def test_files_docs_accessible_when_feature_enabled(self):
        """Files documentation should be accessible when filehub feature is enabled."""
        response = self.send_request(reverse("core:api_docs", kwargs={"doc_name": "files"}))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, "core/docs/api_docs.html")
        self.assertEqual(response.context["doc_name"], "files")
        self.assertEqual(response.context["page_title"], "API Documentation - Files")

    @override_settings(FILEHUB_FEATURE_ENABLED=False)
    def test_files_docs_returns_404_when_feature_disabled(self):
        """Files documentation should return 404 when filehub feature is disabled."""
        response = self.send_request(reverse("core:api_docs", kwargs={"doc_name": "files"}))

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    @override_settings(FILEHUB_FEATURE_ENABLED=True)
    def test_filehub_enabled_context_variable_true(self):
        """Context should have filehub_enabled=True when feature is enabled."""
        response = self.send_request(reverse("core:api_docs", kwargs={"doc_name": "overview"}))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTrue(response.context["filehub_enabled"])

    @override_settings(FILEHUB_FEATURE_ENABLED=False)
    def test_filehub_enabled_context_variable_false(self):
        """Context should have filehub_enabled=False when feature is disabled."""
        response = self.send_request(reverse("core:api_docs", kwargs={"doc_name": "overview"}))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertFalse(response.context["filehub_enabled"])

    @override_settings(FILEHUB_FEATURE_ENABLED=True)
    def test_dev_index_has_filehub_enabled_context(self):
        """Dev index page should have filehub_enabled in context."""
        response = self.send_request(reverse("core:dev_index"))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTrue(response.context["filehub_enabled"])

    @override_settings(FILEHUB_FEATURE_ENABLED=False)
    def test_dev_index_filehub_disabled_context(self):
        """Dev index page should have filehub_enabled=False when feature is disabled."""
        response = self.send_request(reverse("core:dev_index"))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertFalse(response.context["filehub_enabled"])

    @override_settings(FILEHUB_FEATURE_ENABLED=False)
    def test_other_docs_accessible_when_filehub_disabled(self):
        """Other documentation should still be accessible when filehub is disabled."""
        other_docs = ["overview", "ask", "orgs", "projects", "pages", "users"]

        for doc_name in other_docs:
            response = self.send_request(reverse("core:api_docs", kwargs={"doc_name": doc_name}))
            self.assertEqual(
                response.status_code,
                HTTPStatus.OK,
                f"Doc '{doc_name}' should be accessible when filehub is disabled",
            )
