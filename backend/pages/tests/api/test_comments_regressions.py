"""
Regression tests for comments API hardening.

Covers: base64 validation, body/anchor_text limits, cache-based AI review dedup,
rate limiting, and query param limit enforcement.
"""

from http import HTTPStatus
from unittest.mock import patch

from django.core.cache import cache
from django.test import override_settings

from core.tests.common import BaseAuthenticatedViewTestCase
from pages.api.comments import (
    COMMENT_ANCHOR_B64_MAX_LENGTH,
    COMMENT_ANCHOR_TEXT_MAX_LENGTH,
    COMMENT_BODY_MAX_LENGTH,
    COMMENTS_PAGE_SIZE_MAX,
)
from pages.models import Comment
from pages.tests.factories import CommentFactory, PageFactory, ProjectFactory
from users.constants import OrgMemberRole
from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory


class CommentsRegressionMixin:
    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)
        self.project = ProjectFactory(org=self.org, creator=self.user)
        self.page = PageFactory(project=self.project, creator=self.user)

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def url(self, page=None, comment_id=None):
        page = page or self.page
        base = f"/api/pages/{page.external_id}/comments/"
        if comment_id:
            return f"{base}{comment_id}/"
        return base


class TestBase64Validation(CommentsRegressionMixin, BaseAuthenticatedViewTestCase):
    """#3: Invalid base64 should return 400, not crash with 500."""

    @patch("pages.api.comments.notify_comments_updated")
    def test_create_with_invalid_base64_anchor_from(self, _mock):
        data = {
            "body": "Comment.",
            "anchor_text": "some text",
            "anchor_from_b64": "!!!invalid!!!",
            "anchor_to_b64": "dGVzdA==",
        }
        response = self.send_api_request(url=self.url(), method="post", data=data)
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIn("base64", response.json()["detail"].lower())

    @patch("pages.api.comments.notify_comments_updated")
    def test_create_with_invalid_base64_anchor_to(self, _mock):
        data = {
            "body": "Comment.",
            "anchor_text": "some text",
            "anchor_from_b64": "dGVzdA==",
            "anchor_to_b64": "not-base64!!",
        }
        response = self.send_api_request(url=self.url(), method="post", data=data)
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)

    @patch("pages.api.comments.notify_comments_updated")
    def test_update_with_invalid_base64(self, _mock):
        comment = CommentFactory(page=self.page, author=self.user, anchor_text="text")

        data = {"anchor_from_b64": "~~~bad~~~", "anchor_to_b64": "dGVzdA=="}
        response = self.send_api_request(url=self.url(comment_id=comment.external_id), method="patch", data=data)
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIn("base64", response.json()["detail"].lower())


class TestBodyAndAnchorLimits(CommentsRegressionMixin, BaseAuthenticatedViewTestCase):
    """#7/#8: Body and anchor_text must be size-limited."""

    def test_body_exceeding_max_length_rejected(self):
        data = {
            "body": "x" * (COMMENT_BODY_MAX_LENGTH + 1),
            "anchor_text": "some text",
        }
        response = self.send_api_request(url=self.url(), method="post", data=data)
        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)

    @patch("pages.api.comments.notify_comments_updated")
    def test_body_at_max_length_accepted(self, _mock):
        data = {
            "body": "x" * COMMENT_BODY_MAX_LENGTH,
            "anchor_text": "some text",
        }
        response = self.send_api_request(url=self.url(), method="post", data=data)
        self.assertEqual(response.status_code, HTTPStatus.CREATED)

    def test_update_body_exceeding_max_length_rejected(self):
        comment = CommentFactory(page=self.page, author=self.user, anchor_text="text")

        data = {"body": "x" * (COMMENT_BODY_MAX_LENGTH + 1)}
        response = self.send_api_request(url=self.url(comment_id=comment.external_id), method="patch", data=data)
        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)

    @patch("pages.api.comments.notify_comments_updated")
    def test_update_body_at_max_length_accepted(self, _mock):
        comment = CommentFactory(page=self.page, author=self.user, anchor_text="text")

        data = {"body": "x" * COMMENT_BODY_MAX_LENGTH}
        response = self.send_api_request(url=self.url(comment_id=comment.external_id), method="patch", data=data)
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_anchor_text_exceeding_max_length_rejected(self):
        data = {
            "body": "Comment.",
            "anchor_text": "x" * (COMMENT_ANCHOR_TEXT_MAX_LENGTH + 1),
        }
        response = self.send_api_request(url=self.url(), method="post", data=data)
        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)

    def test_create_anchor_from_b64_exceeding_max_length_rejected(self):
        data = {
            "body": "Comment.",
            "anchor_text": "some text",
            "anchor_from_b64": "A" * (COMMENT_ANCHOR_B64_MAX_LENGTH + 1),
            "anchor_to_b64": "dGVzdA==",
        }
        response = self.send_api_request(url=self.url(), method="post", data=data)
        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)

    def test_create_anchor_to_b64_exceeding_max_length_rejected(self):
        data = {
            "body": "Comment.",
            "anchor_text": "some text",
            "anchor_from_b64": "dGVzdA==",
            "anchor_to_b64": "A" * (COMMENT_ANCHOR_B64_MAX_LENGTH + 1),
        }
        response = self.send_api_request(url=self.url(), method="post", data=data)
        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)

    def test_update_anchor_b64_exceeding_max_length_rejected(self):
        comment = CommentFactory(page=self.page, author=self.user, anchor_text="text")

        data = {"anchor_from_b64": "A" * (COMMENT_ANCHOR_B64_MAX_LENGTH + 1), "anchor_to_b64": "dGVzdA=="}
        response = self.send_api_request(url=self.url(comment_id=comment.external_id), method="patch", data=data)
        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)


class TestQueryParamLimitEnforcement(CommentsRegressionMixin, BaseAuthenticatedViewTestCase):
    """#3 review: limit query param must be capped."""

    def test_limit_over_max_rejected(self):
        response = self.send_api_request(url=f"{self.url()}?limit={COMMENTS_PAGE_SIZE_MAX + 1}")
        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)

    def test_limit_at_max_accepted(self):
        response = self.send_api_request(url=f"{self.url()}?limit={COMMENTS_PAGE_SIZE_MAX}")
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_negative_offset_rejected(self):
        response = self.send_api_request(url=f"{self.url()}?offset=-1")
        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)

    def test_offset_at_zero_accepted(self):
        response = self.send_api_request(url=f"{self.url()}?offset=0")
        self.assertEqual(response.status_code, HTTPStatus.OK)


class TestAIReviewCacheDedup(CommentsRegressionMixin, BaseAuthenticatedViewTestCase):
    """AI review dedup uses atomic cache flag, not DB query."""

    def ai_review_url(self):
        return f"/api/pages/{self.page.external_id}/comments/ai-review/"

    @patch("pages.api.comments.run_ai_review")
    @patch("collab.tasks.sync_snapshot_with_page")
    def test_first_request_accepted(self, _mock_sync, mock_task):
        mock_task.enqueue = lambda *args, **kwargs: None

        response = self.send_api_request(url=self.ai_review_url(), method="post", data={"persona": "socrates"})
        self.assertEqual(response.status_code, HTTPStatus.ACCEPTED)

    @patch("pages.api.comments.run_ai_review")
    @patch("collab.tasks.sync_snapshot_with_page")
    def test_duplicate_request_returns_409(self, _mock_sync, mock_task):
        mock_task.enqueue = lambda *args, **kwargs: None

        # First request — accepted
        self.send_api_request(url=self.ai_review_url(), method="post", data={"persona": "socrates"})

        # Second request — blocked by cache flag
        response = self.send_api_request(url=self.ai_review_url(), method="post", data={"persona": "socrates"})
        self.assertEqual(response.status_code, HTTPStatus.CONFLICT)
        self.assertIn("already reviewing", response.json()["detail"])

    @patch("pages.api.comments.run_ai_review")
    @patch("collab.tasks.sync_snapshot_with_page")
    def test_different_persona_not_blocked(self, _mock_sync, mock_task):
        mock_task.enqueue = lambda *args, **kwargs: None

        # Socrates in progress
        self.send_api_request(url=self.ai_review_url(), method="post", data={"persona": "socrates"})

        # Einstein should still be accepted
        response = self.send_api_request(url=self.ai_review_url(), method="post", data={"persona": "einstein"})
        self.assertEqual(response.status_code, HTTPStatus.ACCEPTED)

    @patch("pages.api.comments.run_ai_review")
    @patch("collab.tasks.sync_snapshot_with_page")
    def test_flag_cleared_allows_retry(self, _mock_sync, mock_task):
        mock_task.enqueue = lambda *args, **kwargs: None

        # First request — sets cache flag
        self.send_api_request(url=self.ai_review_url(), method="post", data={"persona": "socrates"})

        # Simulate job completion clearing the flag
        cache.delete(f"ai_review:{self.page.id}:socrates")

        # Retry should be accepted
        response = self.send_api_request(url=self.ai_review_url(), method="post", data={"persona": "socrates"})
        self.assertEqual(response.status_code, HTTPStatus.ACCEPTED)


class TestCommentCreationThrottling(CommentsRegressionMixin, BaseAuthenticatedViewTestCase):
    """Comment creation is rate-limited per user."""

    @override_settings(WS_COMMENTS_RATE_LIMIT_REQUESTS=1, WS_COMMENTS_RATE_LIMIT_WINDOW_SECONDS=60)
    @patch("pages.api.comments.notify_comments_updated")
    def test_second_create_within_window_throttled(self, _mock):
        data = {"body": "First.", "anchor_text": "text", "parent_id": None}
        self.send_api_request(url=self.url(), method="post", data=data)

        data["body"] = "Second."
        response = self.send_api_request(url=self.url(), method="post", data=data)
        self.assertEqual(response.status_code, HTTPStatus.TOO_MANY_REQUESTS)


class TestAIReviewThrottling(CommentsRegressionMixin, BaseAuthenticatedViewTestCase):
    """AI review trigger is rate-limited per user."""

    def ai_review_url(self):
        return f"/api/pages/{self.page.external_id}/comments/ai-review/"

    @override_settings(
        WS_AI_REVIEW_RATE_LIMIT_REQUESTS=1,
        WS_AI_REVIEW_RATE_LIMIT_WINDOW_SECONDS=60,
    )
    @patch("pages.api.comments.run_ai_review")
    @patch("collab.tasks.sync_snapshot_with_page")
    def test_second_ai_review_within_window_throttled(self, _mock_sync, mock_task):
        mock_task.enqueue = lambda *args, **kwargs: None

        self.send_api_request(url=self.ai_review_url(), method="post", data={"persona": "socrates"})
        response = self.send_api_request(url=self.ai_review_url(), method="post", data={"persona": "einstein"})
        self.assertEqual(response.status_code, HTTPStatus.TOO_MANY_REQUESTS)


class TestSyncFailureLogsWarning(CommentsRegressionMixin, BaseAuthenticatedViewTestCase):
    """#9: Sync failure should log warning, not silently pass."""

    @patch("pages.api.comments.run_ai_review")
    @patch("pages.api.comments.log_warning")
    @patch(
        "collab.tasks.sync_snapshot_with_page",
        side_effect=Exception("sync failed"),
    )
    def test_sync_failure_logs_and_continues(self, _mock_sync, mock_log, mock_task):
        mock_task.enqueue = lambda *args, **kwargs: None

        url = f"/api/pages/{self.page.external_id}/comments/ai-review/"
        response = self.send_api_request(url=url, method="post", data={"persona": "socrates"})

        # Request should still succeed (sync failure is non-fatal)
        self.assertEqual(response.status_code, HTTPStatus.ACCEPTED)
        # But a warning should have been logged
        mock_log.assert_called_once()
        self.assertIn("Failed to sync", mock_log.call_args[0][0])
