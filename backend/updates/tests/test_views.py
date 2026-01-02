from datetime import timedelta
from http import HTTPStatus
from unittest.mock import patch

from django.core.signing import TimestampSigner
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

    @patch("updates.views.django_rq.get_queue")
    def test_send_test_email_enqueues_task(self, mock_get_queue):
        self.client.force_login(self.superuser)
        mock_queue = mock_get_queue.return_value

        response = self.client.post(reverse("updates:send_test_email", args=[self.update.slug]))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertIn("test@example.com", data["message"])
        mock_queue.enqueue.assert_called_once_with(
            "updates.tasks.send_test_update_email", self.update.id, "test@example.com"
        )

    @patch("updates.views.django_rq.get_queue")
    @override_settings(UPDATES_TEST_EMAIL="custom@example.org")
    def test_send_test_email_uses_configured_email(self, mock_get_queue):
        self.client.force_login(self.superuser)
        mock_queue = mock_get_queue.return_value

        response = self.client.post(reverse("updates:send_test_email", args=[self.update.slug]))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertIn("custom@example.org", data["message"])
        mock_queue.enqueue.assert_called_once_with(
            "updates.tasks.send_test_update_email", self.update.id, "custom@example.org"
        )

    @patch("updates.views.django_rq.get_queue")
    def test_send_test_email_works_even_after_real_send(self, mock_get_queue):
        self.client.force_login(self.superuser)
        self.update.emailed_at = timezone.now()
        self.update.save()
        mock_queue = mock_get_queue.return_value

        response = self.client.post(reverse("updates:send_test_email", args=[self.update.slug]))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertTrue(data["success"])

    @patch("updates.views.django_rq.get_queue")
    def test_send_test_email_does_not_set_emailed_at(self, mock_get_queue):
        self.client.force_login(self.superuser)
        mock_queue = mock_get_queue.return_value

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


class TestUnsubscribeView(TestCase):
    def setUp(self):
        self.user = UserFactory(receive_product_updates=True)
        self.signer = TimestampSigner(salt="updates-unsubscribe")

    def test_valid_token_unsubscribes_user(self):
        token = self.signer.sign(str(self.user.id))

        response = self.client.get(reverse("updates:unsubscribe", args=[token]))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertContains(response, "unsubscribed")

        self.user.refresh_from_db()
        self.assertFalse(self.user.receive_product_updates)

    def test_invalid_token_shows_error(self):
        response = self.client.get(reverse("updates:unsubscribe", args=["invalid-token"]))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertContains(response, "invalid or has expired")

    def test_expired_token_shows_error(self):
        signer = TimestampSigner(salt="updates-unsubscribe")
        token = signer.sign(str(self.user.id))

        with patch("updates.views.UNSUBSCRIBE_TOKEN_MAX_AGE", 0):
            response = self.client.get(reverse("updates:unsubscribe", args=[token]))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertContains(response, "invalid or has expired")

    def test_already_unsubscribed_user_still_shows_success(self):
        self.user.receive_product_updates = False
        self.user.save()
        token = self.signer.sign(str(self.user.id))

        response = self.client.get(reverse("updates:unsubscribe", args=[token]))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertContains(response, "unsubscribed")

    def test_nonexistent_user_shows_error(self):
        token = self.signer.sign("999999")

        response = self.client.get(reverse("updates:unsubscribe", args=[token]))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertContains(response, "invalid or has expired")
