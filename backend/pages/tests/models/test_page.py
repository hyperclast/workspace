"""Tests for Page model helpers used as the central PDF dispatch."""

from django.test import TestCase

from pages.tests.factories import PageFactory


class TestPageIsPdf(TestCase):
    def test_is_pdf_true_when_filetype_is_pdf(self):
        page = PageFactory(details={"filetype": "pdf", "content": ""})
        self.assertTrue(page.is_pdf)

    def test_is_pdf_false_for_md(self):
        page = PageFactory(details={"filetype": "md", "content": "hello"})
        self.assertFalse(page.is_pdf)

    def test_is_pdf_false_for_csv(self):
        page = PageFactory(details={"filetype": "csv", "content": "a,b,c"})
        self.assertFalse(page.is_pdf)

    def test_is_pdf_false_for_log(self):
        page = PageFactory(details={"filetype": "log", "content": "..."})
        self.assertFalse(page.is_pdf)

    def test_is_pdf_false_when_filetype_missing(self):
        page = PageFactory(details={"content": "no filetype"})
        self.assertFalse(page.is_pdf)

    def test_is_pdf_false_when_details_is_none(self):
        page = PageFactory(details={})
        page.details = None
        self.assertFalse(page.is_pdf)


class TestPageGetTextContent(TestCase):
    def test_returns_extracted_text_for_pdf(self):
        page = PageFactory(
            details={
                "filetype": "pdf",
                "schema_version": 2,
                "content": "",
                "extracted_text": "Hello from the PDF body.",
                "pdf_file_id": "abc123",
            }
        )
        self.assertEqual(page.get_text_content(), "Hello from the PDF body.")

    def test_returns_empty_string_when_pdf_has_no_extracted_text(self):
        page = PageFactory(details={"filetype": "pdf", "content": ""})
        self.assertEqual(page.get_text_content(), "")

    def test_returns_content_for_md(self):
        page = PageFactory(details={"filetype": "md", "content": "# Hello"})
        self.assertEqual(page.get_text_content(), "# Hello")

    def test_returns_content_for_csv(self):
        page = PageFactory(details={"filetype": "csv", "content": "a,b\n1,2"})
        self.assertEqual(page.get_text_content(), "a,b\n1,2")

    def test_returns_empty_string_when_content_missing(self):
        page = PageFactory(details={"filetype": "md"})
        self.assertEqual(page.get_text_content(), "")

    def test_pdf_ignores_content_field(self):
        # PDF pages may have a stale or empty content field — extracted_text wins.
        page = PageFactory(
            details={
                "filetype": "pdf",
                "content": "should be ignored",
                "extracted_text": "actual pdf body",
            }
        )
        self.assertEqual(page.get_text_content(), "actual pdf body")


class TestPageContentForEmbedding(TestCase):
    def test_uses_extracted_text_for_pdf(self):
        page = PageFactory(
            title="My PDF",
            details={
                "filetype": "pdf",
                "content": "",
                "extracted_text": "First paragraph.\nSecond paragraph.",
            },
        )
        self.assertEqual(
            page.content_for_embedding,
            "My PDF\n\nFirst paragraph.\nSecond paragraph.",
        )

    def test_uses_content_for_markdown(self):
        page = PageFactory(
            title="Notes",
            details={"filetype": "md", "content": "Hello world"},
        )
        self.assertEqual(page.content_for_embedding, "Notes\n\nHello world")

    def test_returns_empty_when_pdf_has_no_extracted_text_and_no_title(self):
        page = PageFactory(title="", details={"filetype": "pdf", "content": ""})
        self.assertEqual(page.content_for_embedding, "")
