from http import HTTPStatus
from unittest.mock import patch

from ask.constants import AIProvider
from ask.tasks import index_user_pages
from core.tests.common import BaseAuthenticatedViewTestCase
from pages.tests.factories import PageFactory
from users.models import AIProviderConfig


class TestTriggerIndexingAPI(BaseAuthenticatedViewTestCase):
    """Regression tests for POST /api/ai/indexing/trigger/.

    These specifically guard against the `.delay()` vs `.enqueue()` mistake that
    crashed the endpoint — this project uses django-rq with a custom @task
    decorator, not Celery, so `.enqueue()` is the only correct entry point.
    """

    URL = "/api/ai/indexing/trigger/"

    def _make_validated_provider(self):
        return AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.OPENAI.value,
            api_key="sk-test",
            is_validated=True,
            is_enabled=True,
        )

    def _make_accessible_page(self):
        # PageFactory adds creator as page editor (Tier 3 access).
        return PageFactory(creator=self.user)

    def test_returns_400_when_no_validated_provider(self):
        self._make_accessible_page()

        response = self.send_api_request(url=self.URL, method="post")

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIn("No valid AI provider", response.json()["message"])

    def test_returns_no_op_when_no_pending_pages(self):
        self._make_validated_provider()

        response = self.send_api_request(url=self.URL, method="post")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        payload = response.json()
        self.assertFalse(payload["triggered"])
        self.assertEqual(payload["pages_queued"], 0)

    @patch("ask.tasks.index_user_pages")
    def test_enqueues_task_with_pending_page_ids(self, mock_task):
        """Regression: must call .enqueue (not .delay).

        Mock.assert_called_once_with on the .enqueue attribute fails if any
        other attribute (like .delay) was used instead — Mock auto-creates
        attributes, but the assertion only inspects the one we name.
        """
        self._make_validated_provider()
        page = self._make_accessible_page()

        response = self.send_api_request(url=self.URL, method="post")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        payload = response.json()
        self.assertTrue(payload["triggered"])
        self.assertEqual(payload["pages_queued"], 1)

        mock_task.enqueue.assert_called_once_with(self.user.id, [page.external_id])
        mock_task.delay.assert_not_called()

    def test_index_user_pages_exposes_enqueue_not_delay(self):
        """The @task decorator wraps the function so it has .enqueue but no .delay.

        Anyone who reaches for Celery's `.delay()` API gets an AttributeError
        in production — this assertion makes that contract explicit so the
        regression can't sneak back in via a different call site.
        """
        self.assertTrue(callable(getattr(index_user_pages, "enqueue", None)))
        self.assertFalse(hasattr(index_user_pages, "delay"))
