"""Tests for run_ai_reply task."""

from unittest.mock import patch

from django.core.cache import cache

from core.tests.common import BaseAuthenticatedViewTestCase
from pages.models import Comment
from pages.tasks import run_ai_reply
from pages.tests.factories import CommentFactory, PageFactory, ProjectFactory
from users.constants import OrgMemberRole
from users.tests.factories import OrgFactory, OrgMemberFactory


class TestRunAIReplyTask(BaseAuthenticatedViewTestCase):
    """Integration tests for run_ai_reply task."""

    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)
        self.project = ProjectFactory(org=self.org, creator=self.user)
        self.page = PageFactory(project=self.project, creator=self.user)
        self.page.details["content"] = "We need a scalable solution for the backend."
        self.page.save(update_fields=["details", "modified"])

        # AI persona leaves a root comment
        self.ai_comment = CommentFactory(
            page=self.page,
            author=None,
            ai_persona="socrates",
            requester=self.user,
            body="What do you mean by scalable?",
        )
        # User replies to the AI comment
        self.user_reply = CommentFactory(
            page=self.page,
            author=self.user,
            parent=self.ai_comment,
            root=self.ai_comment,
            body="I mean it should handle 10x traffic.",
        )

    def tearDown(self):
        cache.clear()
        super().tearDown()

    @patch("collab.utils.notify_comments_updated")
    @patch("ask.helpers.llm.create_chat_completion")
    def test_creates_reply_comment(self, mock_llm, mock_broadcast):
        mock_llm.return_value = {
            "choices": [{"message": {"content": "Can you define what 10x means in concrete numbers?"}}]
        }

        run_ai_reply(self.user_reply.id, "socrates", self.user.id)

        ai_replies = Comment.objects.filter(parent=self.user_reply, ai_persona="socrates")
        self.assertEqual(ai_replies.count(), 1)

        reply = ai_replies.first()
        self.assertIsNone(reply.author_id)
        self.assertEqual(reply.ai_persona, "socrates")
        self.assertEqual(reply.requester_id, self.user.id)
        self.assertEqual(reply.body, "Can you define what 10x means in concrete numbers?")
        self.assertEqual(reply.parent_id, self.user_reply.id)
        self.assertEqual(reply.root_id, self.ai_comment.id)
        self.assertEqual(reply.page_id, self.page.id)
        mock_broadcast.assert_called_once_with(str(self.page.external_id))

    @patch("collab.utils.notify_comments_updated")
    @patch("ask.helpers.llm.create_chat_completion")
    def test_works_with_empty_page_content(self, mock_llm, mock_broadcast):
        """Thread context alone is sufficient — empty page content should not block reply."""
        self.page.details["content"] = ""
        self.page.save(update_fields=["details", "modified"])

        mock_llm.return_value = {"choices": [{"message": {"content": "Tell me more."}}]}

        run_ai_reply(self.user_reply.id, "socrates", self.user.id)

        self.assertEqual(Comment.objects.filter(parent=self.user_reply).count(), 1)
        mock_broadcast.assert_called_once()

    @patch("ask.helpers.llm.create_chat_completion")
    def test_llm_failure_clears_cache_no_comment(self, mock_llm):
        mock_llm.side_effect = Exception("API error")
        cache_key = f"ai_reply:{self.user_reply.id}"
        cache.set(cache_key, 1, 300)

        run_ai_reply(self.user_reply.id, "socrates", self.user.id)

        self.assertIsNone(cache.get(cache_key))
        self.assertEqual(Comment.objects.filter(parent=self.user_reply).count(), 0)

    @patch("ask.helpers.llm.create_chat_completion")
    def test_empty_llm_response_clears_cache_no_comment(self, mock_llm):
        mock_llm.return_value = {"choices": [{"message": {"content": "   "}}]}

        run_ai_reply(self.user_reply.id, "socrates", self.user.id)

        self.assertEqual(Comment.objects.filter(parent=self.user_reply).count(), 0)

    def test_unknown_persona_creates_no_comment(self):
        run_ai_reply(self.user_reply.id, "plato", self.user.id)
        self.assertEqual(Comment.objects.filter(parent=self.user_reply).count(), 0)

    def test_missing_comment_clears_cache(self):
        cache_key = "ai_reply:999999"
        cache.set(cache_key, 1, 300)

        run_ai_reply(999999, "socrates", self.user.id)

        self.assertIsNone(cache.get(cache_key))

    def test_missing_user_clears_cache(self):
        cache_key = f"ai_reply:{self.user_reply.id}"
        cache.set(cache_key, 1, 300)

        run_ai_reply(self.user_reply.id, "socrates", 999999)

        self.assertIsNone(cache.get(cache_key))

    @patch("collab.utils.notify_comments_updated")
    @patch("ask.helpers.llm.create_chat_completion")
    def test_includes_anchor_text_in_prompt(self, mock_llm, mock_broadcast):
        mock_llm.return_value = {"choices": [{"message": {"content": "Interesting."}}]}

        run_ai_reply(self.user_reply.id, "socrates", self.user.id)

        # The LLM should receive the root comment's anchor_text in the prompt
        call_args = mock_llm.call_args
        messages = call_args[1]["messages"] if "messages" in call_args[1] else call_args[0][0]
        user_message = next(m for m in messages if m["role"] == "user")
        self.assertIn(self.ai_comment.anchor_text, user_message["content"])

    @patch("collab.utils.notify_comments_updated")
    @patch("ask.helpers.llm.create_chat_completion")
    def test_includes_thread_conversation_in_prompt(self, mock_llm, mock_broadcast):
        mock_llm.return_value = {"choices": [{"message": {"content": "Follow-up."}}]}

        run_ai_reply(self.user_reply.id, "socrates", self.user.id)

        call_args = mock_llm.call_args
        messages = call_args[1]["messages"] if "messages" in call_args[1] else call_args[0][0]
        user_message = next(m for m in messages if m["role"] == "user")
        # Both the AI's original comment and the user's reply should be in the prompt
        self.assertIn("What do you mean by scalable?", user_message["content"])
        self.assertIn("I mean it should handle 10x traffic.", user_message["content"])

    @patch("collab.utils.notify_comments_updated")
    @patch("ask.helpers.llm.create_chat_completion")
    def test_deep_thread_chain(self, mock_llm, mock_broadcast):
        """AI reply works correctly in a deeper thread (AI -> User -> AI -> User)."""
        # Simulate AI's first reply
        ai_reply_1 = CommentFactory(
            page=self.page,
            author=None,
            ai_persona="socrates",
            requester=self.user,
            parent=self.user_reply,
            root=self.ai_comment,
            body="Can you give me numbers?",
        )
        # User replies again
        user_reply_2 = CommentFactory(
            page=self.page,
            author=self.user,
            parent=ai_reply_1,
            root=self.ai_comment,
            body="About 50k requests per second.",
        )

        mock_llm.return_value = {"choices": [{"message": {"content": "That helps clarify things."}}]}

        run_ai_reply(user_reply_2.id, "socrates", self.user.id)

        ai_reply_2 = Comment.objects.filter(parent=user_reply_2, ai_persona="socrates").first()
        self.assertIsNotNone(ai_reply_2)
        self.assertEqual(ai_reply_2.root_id, self.ai_comment.id)

        # Verify the full chain was included in the prompt
        call_args = mock_llm.call_args
        messages = call_args[1]["messages"] if "messages" in call_args[1] else call_args[0][0]
        user_message = next(m for m in messages if m["role"] == "user")
        self.assertIn("What do you mean by scalable?", user_message["content"])
        self.assertIn("50k requests per second", user_message["content"])
