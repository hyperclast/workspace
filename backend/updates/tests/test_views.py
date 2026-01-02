from http import HTTPStatus
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from users.tests.factories import UserFactory

from .factories import UpdateFactory, UnpublishedUpdateFactory


class TestUpdateListView(TestCase):
    def test_list_view_shows_published_updates(self):
        update1 = UpdateFactory(title="First Update")
        update2 = UpdateFactory(title="Second Update")
        UnpublishedUpdateFactory(title="Draft Update")

        response = self.client.get(reverse("updates:list"))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertContains(response, "First Update")
        self.assertContains(response, "Second Update")
        self.assertNotContains(response, "Draft Update")

    def test_list_view_shows_empty_state(self):
        response = self.client.get(reverse("updates:list"))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertContains(response, "No updates yet")

    def test_list_view_accessible_without_auth(self):
        UpdateFactory(title="Public Update")

        response = self.client.get(reverse("updates:list"))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertContains(response, "Public Update")

    def test_list_view_shows_breadcrumb(self):
        response = self.client.get(reverse("updates:list"))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertContains(response, 'aria-label="Breadcrumb"')
        self.assertContains(response, ">Home</a>")
        self.assertContains(response, "breadcrumb-current")
        self.assertContains(response, ">Updates</span>")

    def test_list_view_navbar_shows_user_dropdown_when_authenticated(self):
        user = UserFactory()
        self.client.force_login(user)

        response = self.client.get(reverse("updates:list"))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertContains(response, 'id="logout-btn"')
        self.assertContains(response, 'id="user-avatar"')
        self.assertContains(response, user.email)

    def test_list_view_navbar_shows_login_link_when_anonymous(self):
        response = self.client.get(reverse("updates:list"))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertContains(response, 'href="/login/"')
        self.assertContains(response, 'href="/signup/"')
        self.assertContains(response, ">Home</a>")

    def test_list_view_includes_logout_csrf_script_when_authenticated(self):
        user = UserFactory()
        self.client.force_login(user)

        response = self.client.get(reverse("updates:list"))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertContains(response, "X-CSRFToken")
        self.assertContains(response, 'method: "DELETE"')


class TestUpdateDetailView(TestCase):
    def test_detail_view_shows_published_update(self):
        update = UpdateFactory(title="My Update", content="Update content here")

        response = self.client.get(reverse("updates:detail", args=[update.slug]))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertContains(response, "My Update")
        self.assertContains(response, "Update content here")

    def test_detail_view_renders_markdown(self):
        update = UpdateFactory(title="Markdown Test", content="**Bold text** and *italic*")

        response = self.client.get(reverse("updates:detail", args=[update.slug]))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertContains(response, "<strong>Bold text</strong>")
        self.assertContains(response, "<em>italic</em>")

    def test_detail_view_404_for_unpublished_when_anonymous(self):
        update = UnpublishedUpdateFactory(title="Draft")

        response = self.client.get(reverse("updates:detail", args=[update.slug]))

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_detail_view_shows_unpublished_to_superuser(self):
        superuser = UserFactory(is_superuser=True)
        self.client.force_login(superuser)

        update = UnpublishedUpdateFactory(title="Draft Update")

        response = self.client.get(reverse("updates:detail", args=[update.slug]))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertContains(response, "Draft Update")

    def test_detail_view_shows_admin_panel_to_superuser(self):
        superuser = UserFactory(is_superuser=True)
        self.client.force_login(superuser)

        update = UpdateFactory(title="Test Update")

        response = self.client.get(reverse("updates:detail", args=[update.slug]))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertContains(response, "Admin Panel")

    def test_detail_view_hides_admin_panel_from_regular_user(self):
        user = UserFactory()
        self.client.force_login(user)

        update = UpdateFactory(title="Test Update")

        response = self.client.get(reverse("updates:detail", args=[update.slug]))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertNotContains(response, "Admin Panel")

    def test_detail_view_shows_email_sent_status(self):
        superuser = UserFactory(is_superuser=True)
        self.client.force_login(superuser)

        update = UpdateFactory(title="Sent Update", emailed_at=timezone.now())

        response = self.client.get(reverse("updates:detail", args=[update.slug]))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertContains(response, "Email sent on")
        self.assertContains(response, "Already Sent")

    def test_detail_view_shows_image_when_present(self):
        update = UpdateFactory(title="Update with Image", image_url="https://example.com/image.png")

        response = self.client.get(reverse("updates:detail", args=[update.slug]))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertContains(response, "https://example.com/image.png")

    def test_detail_view_navbar_shows_user_dropdown_when_authenticated(self):
        user = UserFactory()
        self.client.force_login(user)
        update = UpdateFactory(title="Test Update")

        response = self.client.get(reverse("updates:detail", args=[update.slug]))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertContains(response, 'id="logout-btn"')
        self.assertContains(response, 'id="user-avatar"')

    def test_detail_view_navbar_shows_login_link_when_anonymous(self):
        update = UpdateFactory(title="Test Update")

        response = self.client.get(reverse("updates:detail", args=[update.slug]))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertContains(response, 'href="/login/"')
        self.assertContains(response, 'href="/signup/"')

    def test_detail_view_shows_breadcrumb(self):
        update = UpdateFactory(title="My Test Update")

        response = self.client.get(reverse("updates:detail", args=[update.slug]))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertContains(response, 'aria-label="Breadcrumb"')
        self.assertContains(response, ">Home</a>")
        self.assertContains(response, ">Updates</a>")
        self.assertContains(response, "My Test Update")

    def test_detail_view_includes_logout_csrf_script_when_authenticated(self):
        user = UserFactory()
        self.client.force_login(user)
        update = UpdateFactory(title="Test Update")

        response = self.client.get(reverse("updates:detail", args=[update.slug]))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertContains(response, "X-CSRFToken")
        self.assertContains(response, 'method: "DELETE"')


class TestSendUpdateEmail(TestCase):
    def setUp(self):
        self.superuser = UserFactory(is_superuser=True)
        self.update = UpdateFactory(title="Test Update")

    def test_send_email_requires_superuser(self):
        user = UserFactory()
        self.client.force_login(user)

        response = self.client.post(reverse("updates:send_email", args=[self.update.slug]))

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    def test_send_email_requires_authentication(self):
        response = self.client.post(reverse("updates:send_email", args=[self.update.slug]))

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    @patch("updates.views.django_rq.get_queue")
    def test_send_email_enqueues_task(self, mock_get_queue):
        self.client.force_login(self.superuser)
        mock_queue = mock_get_queue.return_value

        response = self.client.post(reverse("updates:send_email", args=[self.update.slug]))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertTrue(data["success"])
        mock_queue.enqueue.assert_called_once_with("updates.tasks.send_update_to_subscribers", self.update.id)

    def test_send_email_prevents_double_send(self):
        self.client.force_login(self.superuser)
        self.update.emailed_at = timezone.now()
        self.update.save()

        response = self.client.post(reverse("updates:send_email", args=[self.update.slug]))

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        data = response.json()
        self.assertIn("already sent", data["error"].lower())

    def test_send_email_404_for_nonexistent_update(self):
        self.client.force_login(self.superuser)

        response = self.client.post(reverse("updates:send_email", args=["nonexistent-slug"]))

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)


class TestSendTestUpdateEmail(TestCase):
    def setUp(self):
        self.superuser = UserFactory(is_superuser=True)
        self.update = UpdateFactory(title="Test Update")

    def test_send_test_email_requires_superuser(self):
        user = UserFactory()
        self.client.force_login(user)

        response = self.client.post(reverse("updates:send_test_email", args=[self.update.slug]))

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    def test_send_test_email_requires_authentication(self):
        response = self.client.post(reverse("updates:send_test_email", args=[self.update.slug]))

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    @patch("updates.tasks.send_broadcast_email")
    def test_send_test_email_calls_task(self, mock_send):
        self.client.force_login(self.superuser)
        mock_send.return_value = "test-message-id"

        response = self.client.post(reverse("updates:send_test_email", args=[self.update.slug]))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertIn("test@example.com", data["message"])
        mock_send.assert_called_once()

    @patch("updates.tasks.send_broadcast_email")
    @override_settings(UPDATES_TEST_EMAIL="custom@example.org")
    def test_send_test_email_uses_configured_email(self, mock_send):
        self.client.force_login(self.superuser)
        mock_send.return_value = None

        response = self.client.post(reverse("updates:send_test_email", args=[self.update.slug]))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertIn("custom@example.org", data["message"])
        call_kwargs = mock_send.call_args.kwargs
        self.assertEqual(call_kwargs["to_email"], "custom@example.org")

    @patch("updates.tasks.send_broadcast_email")
    def test_send_test_email_works_even_after_real_send(self, mock_send):
        self.client.force_login(self.superuser)
        self.update.emailed_at = timezone.now()
        self.update.save()
        mock_send.return_value = None

        response = self.client.post(reverse("updates:send_test_email", args=[self.update.slug]))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertTrue(data["success"])

    @patch("updates.tasks.send_broadcast_email")
    def test_send_test_email_does_not_set_emailed_at(self, mock_send):
        self.client.force_login(self.superuser)
        mock_send.return_value = None

        self.assertIsNone(self.update.emailed_at)

        response = self.client.post(reverse("updates:send_test_email", args=[self.update.slug]))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.update.refresh_from_db()
        self.assertIsNone(self.update.emailed_at)

    def test_send_test_email_404_for_nonexistent_update(self):
        self.client.force_login(self.superuser)

        response = self.client.post(reverse("updates:send_test_email", args=["nonexistent-slug"]))

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_detail_view_shows_test_button_to_superuser(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("updates:detail", args=[self.update.slug]))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertContains(response, "Send Test")
        self.assertContains(response, "sendTestEmail()")

    def test_detail_view_shows_test_button_even_after_real_send(self):
        self.client.force_login(self.superuser)
        self.update.emailed_at = timezone.now()
        self.update.save()

        response = self.client.get(reverse("updates:detail", args=[self.update.slug]))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertContains(response, "Send Test")
        self.assertContains(response, "sendTestEmail()")
        self.assertContains(response, "Already Sent")


class TestCheckSpamScoreView(TestCase):
    """Tests for the check spam score endpoint."""

    def setUp(self):
        self.superuser = UserFactory(is_superuser=True)
        self.update = UpdateFactory(title="Test Update")

    def test_check_spam_requires_superuser(self):
        user = UserFactory()
        self.client.force_login(user)

        response = self.client.post(reverse("updates:check_spam", args=[self.update.slug]))

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    def test_check_spam_requires_authentication(self):
        response = self.client.post(reverse("updates:check_spam", args=[self.update.slug]))

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    @patch("updates.tasks.check_spam_score")
    def test_check_spam_returns_score(self, mock_check):
        self.client.force_login(self.superuser)
        mock_check.return_value = {"score": 1.5, "success": True, "rules": []}

        response = self.client.post(reverse("updates:check_spam", args=[self.update.slug]))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["spam_score"]["score"], 1.5)

    @patch("updates.tasks.check_spam_score")
    def test_check_spam_persists_score_to_update(self, mock_check):
        self.client.force_login(self.superuser)
        mock_check.return_value = {"score": 2.0, "success": True, "rules": [{"name": "TEST_RULE"}]}

        response = self.client.post(reverse("updates:check_spam", args=[self.update.slug]))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.update.refresh_from_db()
        self.assertEqual(self.update.spam_score, 2.0)
        self.assertEqual(self.update.spam_rules, [{"name": "TEST_RULE"}])

    @patch("updates.tasks.check_spam_score")
    def test_check_spam_handles_api_failure(self, mock_check):
        self.client.force_login(self.superuser)
        mock_check.return_value = None

        response = self.client.post(reverse("updates:check_spam", args=[self.update.slug]))

        self.assertEqual(response.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
        data = response.json()
        self.assertIn("error", data)

    def test_check_spam_404_for_nonexistent_update(self):
        self.client.force_login(self.superuser)

        response = self.client.post(reverse("updates:check_spam", args=["nonexistent-slug"]))

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_detail_view_shows_check_spam_button_to_superuser(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("updates:detail", args=[self.update.slug]))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertContains(response, "Check Spam")
        self.assertContains(response, "checkSpam()")


class TestSpamScoreDisplay(TestCase):
    """Tests for spam score display in the admin toolbar."""

    def setUp(self):
        self.superuser = UserFactory(is_superuser=True)

    def test_detail_view_shows_good_spam_score(self):
        self.client.force_login(self.superuser)
        update = UpdateFactory(spam_score=1.0)

        response = self.client.get(reverse("updates:detail", args=[update.slug]))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        # Check for actual spam score element in admin panel (with class and score)
        self.assertContains(response, '<span class="spam-score good"')
        self.assertContains(response, "1.0")
        self.assertContains(response, "✅")

    def test_detail_view_shows_borderline_spam_score(self):
        self.client.force_login(self.superuser)
        update = UpdateFactory(spam_score=3.5)

        response = self.client.get(reverse("updates:detail", args=[update.slug]))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertContains(response, '<span class="spam-score borderline"')
        self.assertContains(response, "3.5")
        self.assertContains(response, "⚠️")

    def test_detail_view_shows_bad_spam_score(self):
        self.client.force_login(self.superuser)
        update = UpdateFactory(spam_score=6.0)

        response = self.client.get(reverse("updates:detail", args=[update.slug]))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertContains(response, '<span class="spam-score bad"')
        self.assertContains(response, "6.0")
        self.assertContains(response, "❌")

    def test_detail_view_shows_details_link_when_spam_score_present(self):
        self.client.force_login(self.superuser)
        update = UpdateFactory(spam_score=1.5)

        response = self.client.get(reverse("updates:detail", args=[update.slug]))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertContains(response, "details</a>")
        self.assertContains(response, f"/admin/updates/update/{update.pk}/change/")

    def test_detail_view_hides_spam_score_when_not_present(self):
        self.client.force_login(self.superuser)
        update = UpdateFactory(spam_score=None)

        response = self.client.get(reverse("updates:detail", args=[update.slug]))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        # The CSS class .spam-score will exist in the stylesheet, but no span with it
        self.assertNotContains(response, '<span class="spam-score')

    def test_detail_view_hides_spam_score_from_non_superuser(self):
        user = UserFactory()
        self.client.force_login(user)
        update = UpdateFactory(spam_score=1.5)

        response = self.client.get(reverse("updates:detail", args=[update.slug]))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        # Non-superuser should not see the admin panel at all
        self.assertNotContains(response, "Admin Panel")
