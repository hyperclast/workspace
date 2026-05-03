"""Verify AI flows on PDF-type pages use details.extracted_text."""

from http import HTTPStatus
from unittest.mock import patch

from django.core.cache import cache

from core.tests.common import BaseAuthenticatedViewTestCase
from pages.models import Comment
from pages.tasks import run_ai_review
from pages.tests.factories import CommentFactory, PageFactory, ProjectFactory
from users.constants import OrgMemberRole
from users.tests.factories import OrgFactory, OrgMemberFactory


PDF_DETAILS = {
    "content": "",
    "extracted_text": "We need a scalable solution.",
    "pdf_file_id": "file-1",
    "filetype": "pdf",
    "schema_version": 2,
}


class PdfAITestMixin:
    def setUp(self):
        from ask.constants import AIProvider
        from users.models import AIProviderConfig

        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)
        self.project = ProjectFactory(org=self.org, creator=self.user)
        self.page = PageFactory(project=self.project, creator=self.user, details=PDF_DETAILS.copy())
        AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.OPENAI.value,
            api_key="sk-test-key",
            is_enabled=True,
            is_validated=True,
            is_default=True,
        )

    def tearDown(self):
        cache.clear()
        super().tearDown()


class TestRunAIReviewOnPdfPage(PdfAITestMixin, BaseAuthenticatedViewTestCase):
    @patch("pages.tasks.notify_ai_review_complete")
    @patch("pages.tasks.notify_comments_updated")
    @patch("pages.tasks.create_chat_completion")
    def test_review_uses_extracted_text(self, mock_llm, mock_broadcast, mock_review_complete):
        mock_llm.return_value = {
            "choices": [{"message": {"content": '[{"anchor_text": "scalable", "body": "Define scalable."}]'}}]
        }

        run_ai_review(self.page.id, str(self.page.external_id), "socrates", self.user.id)

        # The LLM was called with the extracted text in the user message
        self.assertEqual(mock_llm.call_count, 1)
        messages = mock_llm.call_args.kwargs.get("messages") or mock_llm.call_args.args[0]
        user_msg = next(m for m in messages if m["role"] == "user")
        self.assertIn("scalable solution", user_msg["content"])

        # And produced a comment as usual
        comments = list(Comment.objects.filter(page=self.page, ai_persona="socrates"))
        self.assertEqual(len(comments), 1)

    @patch("pages.tasks.notify_ai_review_complete")
    @patch("pages.tasks.create_chat_completion")
    def test_review_skips_when_extracted_text_empty(self, mock_llm, mock_review_complete):
        details = PDF_DETAILS.copy()
        details["extracted_text"] = ""
        self.page.details = details
        self.page.save(update_fields=["details", "modified"])

        run_ai_review(self.page.id, str(self.page.external_id), "socrates", self.user.id)

        mock_llm.assert_not_called()


class TestRunAIReviewResolvesPdfAnchor(BaseAuthenticatedViewTestCase):
    """AI review on PDF pages should hydrate `pdf_anchor` so the resulting
    comments are navigable in the inline PDF viewer."""

    def setUp(self):
        from ask.constants import AIProvider
        from users.models import AIProviderConfig

        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)
        self.project = ProjectFactory(org=self.org, creator=self.user)
        AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.OPENAI.value,
            api_key="sk-test-key",
            is_enabled=True,
            is_validated=True,
            is_default=True,
        )

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def _make_multi_page_pdf(self, extracted_text):
        from imports.services.pdf import compute_page_text_offsets

        details = {
            "content": "",
            "extracted_text": extracted_text,
            "page_text_offsets": compute_page_text_offsets(extracted_text),
            "pdf_file_id": "file-1",
            "filetype": "pdf",
            "schema_version": 2,
        }
        return PageFactory(project=self.project, creator=self.user, details=details)

    @patch("pages.tasks.notify_ai_review_complete")
    @patch("pages.tasks.notify_comments_updated")
    @patch("pages.tasks.create_chat_completion")
    def test_resolves_to_correct_page_when_text_found(self, mock_llm, _broadcast, _complete):
        page = self._make_multi_page_pdf("# Page 1\n\nFirst page about cats.\n\n# Page 2\n\nSecond page about dogs.")
        mock_llm.return_value = {
            "choices": [{"message": {"content": '[{"anchor_text": "page about dogs", "body": "Why dogs?"}]'}}]
        }

        run_ai_review(page.id, str(page.external_id), "socrates", self.user.id)

        comment = Comment.objects.get(page=page, ai_persona="socrates")
        self.assertIsNotNone(comment.pdf_anchor)
        self.assertEqual(comment.pdf_anchor["page"], 2)
        self.assertEqual(comment.pdf_anchor["rects"], [])
        self.assertEqual(comment.pdf_anchor["text"], "page about dogs")

    @patch("pages.tasks.notify_ai_review_complete")
    @patch("pages.tasks.notify_comments_updated")
    @patch("pages.tasks.create_chat_completion")
    def test_leaves_anchor_null_when_text_not_found(self, mock_llm, _broadcast, _complete):
        page = self._make_multi_page_pdf("# Page 1\n\nFirst page about cats.")
        mock_llm.return_value = {
            "choices": [{"message": {"content": '[{"anchor_text": "elephants", "body": "Off-topic."}]'}}]
        }

        run_ai_review(page.id, str(page.external_id), "socrates", self.user.id)

        comment = Comment.objects.get(page=page, ai_persona="socrates")
        self.assertIsNone(comment.pdf_anchor)

    @patch("pages.tasks.notify_ai_review_complete")
    @patch("pages.tasks.notify_comments_updated")
    @patch("pages.tasks.create_chat_completion")
    def test_legacy_pdf_without_offsets_skips_resolution(self, mock_llm, _broadcast, _complete):
        """Pages imported before this change have no page_text_offsets;
        anchor resolution should fall back to None rather than crash."""
        details = {
            "content": "",
            "extracted_text": "First page about cats.",
            "pdf_file_id": "file-1",
            "filetype": "pdf",
            "schema_version": 2,
        }
        page = PageFactory(project=self.project, creator=self.user, details=details)
        mock_llm.return_value = {
            "choices": [{"message": {"content": '[{"anchor_text": "cats", "body": "Tell me more."}]'}}]
        }

        run_ai_review(page.id, str(page.external_id), "socrates", self.user.id)

        comment = Comment.objects.get(page=page, ai_persona="socrates")
        self.assertIsNone(comment.pdf_anchor)


class TestGenerateEditBlockedOnPdf(PdfAITestMixin, BaseAuthenticatedViewTestCase):
    def test_generate_edit_returns_400_on_pdf_page(self):
        comment = CommentFactory(
            page=self.page,
            author=None,
            ai_persona="socrates",
            anchor_text="scalable",
            body="Define scalable.",
        )
        url = f"/api/pages/{self.page.external_id}/comments/{comment.external_id}/generate-edit/"
        response = self.send_api_request(url=url, method="post", data={})
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIn("PDF pages", response.json()["detail"])
