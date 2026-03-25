"""
Unit tests for AI review task helpers and the run_ai_review task itself.

Covers:
- _parse_ai_response: JSON parsing with code block stripping, edge cases
- _build_context_pages: Cost guardrail enforcement
- run_ai_review: End-to-end task execution with mocked LLM
"""

import json
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase

from pages.models import Comment
from pages.tasks import (
    MAX_CHARS_PER_PAGE,
    _build_context_pages,
    _parse_ai_response,
    run_ai_review,
)
from pages.tests.factories import PageFactory, ProjectFactory
from users.constants import OrgMemberRole
from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory


# --- _parse_ai_response ---


class TestParseAIResponse(TestCase):
    def test_valid_json_array(self):
        response = json.dumps(
            [
                {"anchor_text": "passage one", "body": "Comment one."},
                {"anchor_text": "passage two", "body": "Comment two."},
            ]
        )
        result = _parse_ai_response(response)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["anchor_text"], "passage one")
        self.assertEqual(result[0]["body"], "Comment one.")
        self.assertEqual(result[1]["anchor_text"], "passage two")

    def test_json_wrapped_in_markdown_code_block(self):
        response = '```json\n[{"anchor_text": "text", "body": "comment"}]\n```'
        result = _parse_ai_response(response)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["body"], "comment")

    def test_json_wrapped_in_plain_code_block(self):
        response = '```\n[{"anchor_text": "text", "body": "comment"}]\n```'
        result = _parse_ai_response(response)
        self.assertEqual(len(result), 1)

    def test_invalid_json_returns_empty(self):
        result = _parse_ai_response("This is not JSON at all.")
        self.assertEqual(result, [])

    def test_empty_string_returns_empty(self):
        result = _parse_ai_response("")
        self.assertEqual(result, [])

    def test_whitespace_only_returns_empty(self):
        result = _parse_ai_response("   \n  ")
        self.assertEqual(result, [])

    def test_json_object_not_array_returns_empty(self):
        response = json.dumps({"anchor_text": "text", "body": "comment"})
        result = _parse_ai_response(response)
        self.assertEqual(result, [])

    def test_filters_items_with_missing_body(self):
        response = json.dumps(
            [
                {"anchor_text": "passage one"},
                {"anchor_text": "passage two", "body": "Has body."},
            ]
        )
        result = _parse_ai_response(response)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["body"], "Has body.")

    def test_filters_items_with_empty_body(self):
        response = json.dumps(
            [
                {"anchor_text": "passage", "body": ""},
                {"anchor_text": "passage two", "body": "Real comment."},
            ]
        )
        result = _parse_ai_response(response)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["body"], "Real comment.")

    def test_missing_anchor_text_defaults_to_empty_string(self):
        response = json.dumps([{"body": "Comment without anchor."}])
        result = _parse_ai_response(response)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["anchor_text"], "")
        self.assertEqual(result[0]["body"], "Comment without anchor.")

    def test_with_leading_trailing_whitespace(self):
        response = '  \n [{"anchor_text": "text", "body": "comment"}] \n  '
        result = _parse_ai_response(response)
        self.assertEqual(len(result), 1)


# --- _build_context_pages ---


class TestBuildContextPages(TestCase):
    def setUp(self):
        self.org = OrgFactory()
        self.user = UserFactory()
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)
        self.project = ProjectFactory(org=self.org, creator=self.user)
        self.page = PageFactory(
            project=self.project,
            creator=self.user,
            details={"content": "Main page content."},
        )

    def test_excludes_current_page(self):
        result = _build_context_pages(self.page)
        self.assertNotIn("Main page content.", result)

    def test_excludes_deleted_pages(self):
        PageFactory(
            project=self.project,
            creator=self.user,
            details={"content": "Deleted page content."},
            is_deleted=True,
        )
        result = _build_context_pages(self.page)
        self.assertNotIn("Deleted page content.", result)

    def test_skips_pages_with_empty_content(self):
        PageFactory(
            project=self.project,
            creator=self.user,
            details={"content": ""},
        )
        PageFactory(
            project=self.project,
            creator=self.user,
            details={},
        )
        result = _build_context_pages(self.page)
        self.assertEqual(result, "")

    def test_includes_other_pages_content(self):
        other = PageFactory(
            project=self.project,
            creator=self.user,
            title="Other Page",
            details={"content": "Other page content."},
        )
        result = _build_context_pages(self.page)
        self.assertIn("Other page content.", result)
        self.assertIn('title="Other Page"', result)

    def test_respects_max_context_pages_limit(self):
        # The module-level constant is read at import time via getattr,
        # so we patch it directly for this test.
        with patch("pages.tasks.MAX_CONTEXT_PAGES", 2):
            for i in range(5):
                PageFactory(
                    project=self.project,
                    creator=self.user,
                    details={"content": f"Page {i} content."},
                )
            result = _build_context_pages(self.page)
            # Should include at most 2 pages
            page_count = result.count("<page title=")
            self.assertLessEqual(page_count, 2)

    def test_respects_max_chars_per_page_truncation(self):
        long_content = "A" * (MAX_CHARS_PER_PAGE + 1000)
        PageFactory(
            project=self.project,
            creator=self.user,
            details={"content": long_content},
        )
        result = _build_context_pages(self.page)
        # Content within the <page> tags should be truncated
        # The result includes the XML wrapper, so check the inner content length
        self.assertLessEqual(len(result), MAX_CHARS_PER_PAGE + 200)  # generous for XML tags

    def test_respects_max_total_context_chars_budget(self):
        with patch("pages.tasks.MAX_TOTAL_CONTEXT_CHARS", 100):
            # Create pages whose content exceeds the budget
            for i in range(5):
                PageFactory(
                    project=self.project,
                    creator=self.user,
                    details={"content": "X" * 60},
                )
            result = _build_context_pages(self.page)
            # Only 1 page should fit (60 chars < 100 budget, 2nd would be 120 > 100)
            page_count = result.count("<page title=")
            self.assertEqual(page_count, 1)

    def test_escapes_special_characters_in_title(self):
        PageFactory(
            project=self.project,
            creator=self.user,
            title='Notes "Q3" <draft> & ideas',
            details={"content": "Some content."},
        )
        result = _build_context_pages(self.page)
        # Quotes, angle brackets, and ampersands should be HTML-escaped
        self.assertIn('title="Notes &quot;Q3&quot; &lt;draft&gt; &amp; ideas"', result)
        self.assertNotIn("<draft>", result)


# --- run_ai_review ---


class TestRunAIReview(TestCase):
    def setUp(self):
        self.org = OrgFactory()
        self.user = UserFactory()
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)
        self.project = ProjectFactory(org=self.org, creator=self.user)
        self.page = PageFactory(
            project=self.project,
            creator=self.user,
            details={"content": "Some document content for AI review."},
        )

    def tearDown(self):
        cache.clear()
        super().tearDown()

    @patch("collab.utils.notify_ai_review_complete")
    @patch("collab.utils.notify_comments_updated")
    @patch("ask.helpers.llm.create_chat_completion")
    def test_successful_review_creates_comments(self, mock_llm, mock_notify, mock_review_complete):
        ai_response = json.dumps(
            [
                {"anchor_text": "Some document", "body": "What does this mean?"},
                {"anchor_text": "content for AI", "body": "Interesting insight."},
            ]
        )
        mock_llm.return_value = {"choices": [{"message": {"content": ai_response}}]}

        run_ai_review(self.page.id, "socrates", self.user.id)

        comments = Comment.objects.filter(page=self.page)
        self.assertEqual(comments.count(), 2)

        comment = comments.first()
        self.assertIsNone(comment.author)
        self.assertEqual(comment.ai_persona, "socrates")
        self.assertEqual(comment.requester, self.user)
        self.assertEqual(comment.anchor_text, "Some document")
        self.assertEqual(comment.body, "What does this mean?")

        mock_notify.assert_called_once_with(str(self.page.external_id))
        mock_review_complete.assert_called_once_with(str(self.page.external_id), "socrates", 2)

    @patch("collab.utils.notify_ai_review_complete")
    @patch("collab.utils.notify_comments_updated")
    @patch("ask.helpers.llm.create_chat_completion")
    def test_successful_review_clears_cache_flag(self, mock_llm, mock_notify, mock_review_complete):
        ai_response = json.dumps(
            [
                {"anchor_text": "text", "body": "comment"},
            ]
        )
        mock_llm.return_value = {"choices": [{"message": {"content": ai_response}}]}

        cache_key = f"ai_review:{self.page.id}:socrates"
        cache.set(cache_key, 1, timeout=300)

        run_ai_review(self.page.id, "socrates", self.user.id)

        self.assertIsNone(cache.get(cache_key))

    @patch("collab.utils.notify_ai_review_complete")
    @patch("ask.helpers.llm.create_chat_completion")
    def test_page_not_found_clears_cache(self, mock_llm, mock_review_complete):
        cache_key = "ai_review:99999:socrates"
        cache.set(cache_key, 1, timeout=300)

        run_ai_review(99999, "socrates", self.user.id)

        mock_llm.assert_not_called()
        self.assertIsNone(cache.get(cache_key))
        # page_eid is None when page not found, so no review_complete notification
        mock_review_complete.assert_not_called()

    @patch("collab.utils.notify_ai_review_complete")
    @patch("ask.helpers.llm.create_chat_completion")
    def test_user_not_found_clears_cache(self, mock_llm, mock_review_complete):
        cache_key = f"ai_review:{self.page.id}:socrates"
        cache.set(cache_key, 1, timeout=300)

        run_ai_review(self.page.id, "socrates", 99999)

        mock_llm.assert_not_called()
        self.assertIsNone(cache.get(cache_key))
        # page was found so page_eid is set — notification should fire
        mock_review_complete.assert_called_once_with(str(self.page.external_id), "socrates", 0)

    @patch("collab.utils.notify_ai_review_complete")
    @patch("ask.helpers.llm.create_chat_completion")
    def test_empty_content_clears_cache(self, mock_llm, mock_review_complete):
        self.page.details = {"content": ""}
        self.page.save(update_fields=["details", "modified"])

        cache_key = f"ai_review:{self.page.id}:socrates"
        cache.set(cache_key, 1, timeout=300)

        run_ai_review(self.page.id, "socrates", self.user.id)

        mock_llm.assert_not_called()
        self.assertIsNone(cache.get(cache_key))
        mock_review_complete.assert_called_once_with(str(self.page.external_id), "socrates", 0)

    @patch("collab.utils.notify_ai_review_complete")
    @patch("ask.helpers.llm.create_chat_completion")
    def test_whitespace_only_content_clears_cache(self, mock_llm, mock_review_complete):
        self.page.details = {"content": "   \n  "}
        self.page.save(update_fields=["details", "modified"])

        cache_key = f"ai_review:{self.page.id}:socrates"
        cache.set(cache_key, 1, timeout=300)

        run_ai_review(self.page.id, "socrates", self.user.id)

        mock_llm.assert_not_called()
        self.assertIsNone(cache.get(cache_key))
        mock_review_complete.assert_called_once_with(str(self.page.external_id), "socrates", 0)

    @patch("collab.utils.notify_ai_review_complete")
    @patch("ask.helpers.llm.create_chat_completion")
    def test_invalid_persona_clears_cache(self, mock_llm, mock_review_complete):
        cache_key = f"ai_review:{self.page.id}:plato"
        cache.set(cache_key, 1, timeout=300)

        run_ai_review(self.page.id, "plato", self.user.id)

        mock_llm.assert_not_called()
        self.assertIsNone(cache.get(cache_key))
        mock_review_complete.assert_called_once_with(str(self.page.external_id), "plato", 0)

    @patch("collab.utils.notify_ai_review_complete")
    @patch("collab.utils.notify_comments_updated")
    @patch("ask.helpers.llm.create_chat_completion")
    def test_llm_failure_clears_cache_no_comments(self, mock_llm, mock_notify, mock_review_complete):
        mock_llm.side_effect = Exception("API timeout")

        cache_key = f"ai_review:{self.page.id}:socrates"
        cache.set(cache_key, 1, timeout=300)

        run_ai_review(self.page.id, "socrates", self.user.id)

        self.assertEqual(Comment.objects.filter(page=self.page).count(), 0)
        self.assertIsNone(cache.get(cache_key))
        mock_notify.assert_not_called()
        mock_review_complete.assert_called_once_with(str(self.page.external_id), "socrates", 0)

    @patch("collab.utils.notify_ai_review_complete")
    @patch("collab.utils.notify_comments_updated")
    @patch("ask.helpers.llm.create_chat_completion")
    def test_unparseable_response_clears_cache_no_comments(self, mock_llm, mock_notify, mock_review_complete):
        mock_llm.return_value = {"choices": [{"message": {"content": "Sorry, I can't do that."}}]}

        cache_key = f"ai_review:{self.page.id}:socrates"
        cache.set(cache_key, 1, timeout=300)

        run_ai_review(self.page.id, "socrates", self.user.id)

        self.assertEqual(Comment.objects.filter(page=self.page).count(), 0)
        self.assertIsNone(cache.get(cache_key))
        mock_notify.assert_not_called()
        mock_review_complete.assert_called_once_with(str(self.page.external_id), "socrates", 0)

    @patch("collab.utils.notify_ai_review_complete")
    @patch("collab.utils.notify_comments_updated")
    @patch("ask.helpers.llm.create_chat_completion")
    def test_deleted_page_not_found(self, mock_llm, mock_notify, mock_review_complete):
        self.page.is_deleted = True
        self.page.save(update_fields=["is_deleted", "modified"])

        cache_key = f"ai_review:{self.page.id}:socrates"
        cache.set(cache_key, 1, timeout=300)

        run_ai_review(self.page.id, "socrates", self.user.id)

        mock_llm.assert_not_called()
        self.assertIsNone(cache.get(cache_key))

    @patch("collab.utils.notify_ai_review_complete")
    @patch("collab.utils.notify_comments_updated")
    @patch("ask.helpers.llm.create_chat_completion")
    def test_current_page_title_escaped_in_prompt(self, mock_llm, mock_notify, mock_review_complete):
        """Page titles with special chars are HTML-escaped in the LLM prompt."""
        self.page.title = 'My "Notes" <v2> & more'
        self.page.save(update_fields=["title", "modified"])

        ai_response = json.dumps([{"anchor_text": "text", "body": "comment"}])
        mock_llm.return_value = {"choices": [{"message": {"content": ai_response}}]}

        run_ai_review(self.page.id, "socrates", self.user.id)

        # Verify the user message sent to LLM has escaped title
        user_message = mock_llm.call_args.kwargs["messages"][1]["content"]
        self.assertIn("My &quot;Notes&quot; &lt;v2&gt; &amp; more", user_message)
        self.assertNotIn("<v2>", user_message)

    @patch("collab.utils.notify_ai_review_complete")
    @patch("collab.utils.notify_comments_updated")
    @patch("ask.helpers.llm.create_chat_completion")
    def test_athena_persona_accepted(self, mock_llm, mock_notify, mock_review_complete):
        """The athena persona is valid and creates comments."""
        ai_response = json.dumps([{"anchor_text": "Some document", "body": "Set a deadline and ship it."}])
        mock_llm.return_value = {"choices": [{"message": {"content": ai_response}}]}

        run_ai_review(self.page.id, "athena", self.user.id)

        comments = Comment.objects.filter(page=self.page, ai_persona="athena")
        self.assertEqual(comments.count(), 1)
        self.assertEqual(comments.first().body, "Set a deadline and ship it.")
        mock_review_complete.assert_called_once_with(str(self.page.external_id), "athena", 1)

    @patch("collab.utils.notify_ai_review_complete")
    @patch("collab.utils.notify_comments_updated")
    @patch("ask.helpers.llm.create_chat_completion")
    def test_empty_json_array_notifies_zero_comments(self, mock_llm, mock_notify, mock_review_complete):
        """When the AI returns an empty array, no comments are created but notification is sent."""
        mock_llm.return_value = {"choices": [{"message": {"content": "[]"}}]}

        run_ai_review(self.page.id, "socrates", self.user.id)

        self.assertEqual(Comment.objects.filter(page=self.page).count(), 0)
        mock_notify.assert_not_called()
        mock_review_complete.assert_called_once_with(str(self.page.external_id), "socrates", 0)
