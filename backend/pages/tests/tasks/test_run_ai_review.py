"""Tests for run_ai_review task and _parse_ai_response."""

from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase

from core.tests.common import BaseAuthenticatedViewTestCase
from pages.models import Comment
from pages.tasks import _parse_ai_response, run_ai_review
from pages.tests.factories import PageFactory, ProjectFactory
from users.constants import OrgMemberRole
from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory


class TestParseAIResponse(TestCase):
    """Unit tests for _parse_ai_response — pure function, no mocks."""

    def test_parses_valid_json_array(self):
        text = '[{"anchor_text": "passage one", "body": "Comment one."}]'
        result = _parse_ai_response(text)
        self.assertEqual(result, [{"anchor_text": "passage one", "body": "Comment one."}])

    def test_parses_multiple_comments(self):
        text = """[
            {"anchor_text": "first", "body": "First comment."},
            {"anchor_text": "second", "body": "Second comment."}
        ]"""
        result = _parse_ai_response(text)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["anchor_text"], "first")
        self.assertEqual(result[1]["body"], "Second comment.")

    def test_strips_markdown_code_block(self):
        text = '```json\n[{"anchor_text": "x", "body": "y"}]\n```'
        result = _parse_ai_response(text)
        self.assertEqual(result, [{"anchor_text": "x", "body": "y"}])

    def test_filters_empty_body(self):
        text = '[{"anchor_text": "a", "body": ""}, {"anchor_text": "b", "body": "valid"}]'
        result = _parse_ai_response(text)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["body"], "valid")

    def test_invalid_json_returns_empty_list(self):
        self.assertEqual(_parse_ai_response("not json"), [])
        self.assertEqual(_parse_ai_response("{invalid}"), [])
        self.assertEqual(_parse_ai_response(""), [])

    def test_non_list_json_returns_empty_list(self):
        self.assertEqual(_parse_ai_response('{"anchor_text": "x", "body": "y"}'), [])

    def test_missing_fields_use_empty_string(self):
        text = '[{"body": "only body"}]'
        result = _parse_ai_response(text)
        self.assertEqual(result, [{"anchor_text": "", "body": "only body"}])


class TestRunAIReviewTask(BaseAuthenticatedViewTestCase):
    """Integration tests for run_ai_review task."""

    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)
        self.project = ProjectFactory(org=self.org, creator=self.user)
        self.page = PageFactory(project=self.project, creator=self.user)
        self.page.details["content"] = "We need a scalable solution."
        self.page.save(update_fields=["details", "modified"])

    def tearDown(self):
        cache.clear()
        super().tearDown()

    @patch("pages.tasks.notify_ai_review_complete")
    @patch("pages.tasks.notify_comments_updated")
    @patch("pages.tasks.create_chat_completion")
    def test_creates_comments_from_llm_response(self, mock_llm, mock_broadcast, mock_review_complete):
        mock_llm.return_value = {
            "choices": [
                {
                    "message": {
                        "content": '[{"anchor_text": "We need a scalable solution.", "body": "What do you mean by scalable?"}]'
                    }
                }
            ]
        }

        run_ai_review(self.page.id, "socrates", self.user.id)

        comments = list(Comment.objects.filter(page=self.page, ai_persona="socrates"))
        self.assertEqual(len(comments), 1)
        self.assertEqual(comments[0].anchor_text, "We need a scalable solution.")
        self.assertEqual(comments[0].body, "What do you mean by scalable?")
        self.assertIsNone(comments[0].author_id)
        self.assertEqual(comments[0].requester_id, self.user.id)
        mock_broadcast.assert_called_once_with(str(self.page.external_id))
        mock_review_complete.assert_called_once_with(str(self.page.external_id), "socrates", 1)

    @patch("pages.tasks.notify_ai_review_complete")
    @patch("pages.tasks.create_chat_completion")
    def test_empty_content_skips_gracefully(self, mock_llm, mock_review_complete):
        self.page.details["content"] = ""
        self.page.save(update_fields=["details", "modified"])

        run_ai_review(self.page.id, "socrates", self.user.id)

        mock_llm.assert_not_called()
        self.assertEqual(Comment.objects.filter(page=self.page).count(), 0)
        mock_review_complete.assert_called_once_with(str(self.page.external_id), "socrates", 0)

    @patch("pages.tasks.notify_ai_review_complete")
    @patch("pages.tasks.create_chat_completion")
    def test_llm_failure_clears_cache_and_returns(self, mock_llm, mock_review_complete):
        mock_llm.side_effect = Exception("API error")
        cache_key = f"ai_review:{self.page.id}:socrates"
        cache.set(cache_key, 1, 300)

        run_ai_review(self.page.id, "socrates", self.user.id)

        self.assertIsNone(cache.get(cache_key))
        self.assertEqual(Comment.objects.filter(page=self.page).count(), 0)
        mock_review_complete.assert_called_once_with(str(self.page.external_id), "socrates", 0)

    @patch("pages.tasks.notify_ai_review_complete")
    @patch("pages.tasks.notify_comments_updated")
    @patch("pages.tasks.create_chat_completion")
    def test_unparseable_response_creates_no_comments(self, mock_llm, mock_broadcast, mock_review_complete):
        mock_llm.return_value = {"choices": [{"message": {"content": "I cannot produce JSON."}}]}

        run_ai_review(self.page.id, "socrates", self.user.id)

        self.assertEqual(Comment.objects.filter(page=self.page).count(), 0)
        mock_broadcast.assert_not_called()
        mock_review_complete.assert_called_once_with(str(self.page.external_id), "socrates", 0)
