from datetime import timedelta

from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from users.constants import AccessTokenManagedBy
from users.middlewares import LastActiveMiddleware
from users.models import AccessToken, Device
from users.tests.factories import UserFactory


TEST_URL = "/api/users/me/"


class TestLastActiveMiddlewareProfile(TestCase):
    """LastActiveMiddleware updates Profile.last_active for all authenticated requests."""

    @classmethod
    def setUpTestData(cls):
        cls.user = UserFactory()

    def setUp(self):
        self.client.login(email=self.user.email, password="testpass1234")

    def tearDown(self):
        self.client.logout()

    def test_updates_profile_last_active_when_stale(self):
        profile = self.user.profile
        profile.last_active = timezone.now() - timedelta(hours=2)
        profile.save(update_fields=["last_active"])

        self.client.get(TEST_URL)

        profile.refresh_from_db()
        self.assertAlmostEqual(
            profile.last_active,
            timezone.now(),
            delta=timedelta(seconds=5),
        )

    @override_settings(PROFILE_LAST_ACTIVE_THROTTLE_SECONDS=3600)
    def test_skips_profile_last_active_when_recent(self):
        profile = self.user.profile
        recent = timezone.now() - timedelta(minutes=30)
        profile.last_active = recent
        profile.save(update_fields=["last_active"])

        self.client.get(TEST_URL)

        profile.refresh_from_db()
        self.assertEqual(profile.last_active, recent)

    @override_settings(PROFILE_LAST_ACTIVE_THROTTLE_SECONDS=3600)
    def test_updates_profile_last_active_with_device_token(self):
        """Profile.last_active is updated for device-token requests too."""
        profile = self.user.profile
        profile.last_active = timezone.now() - timedelta(hours=2)
        profile.save(update_fields=["last_active"])

        access_token = AccessToken.objects.create(user=self.user, managed_by=AccessTokenManagedBy.SYSTEM)
        Device.objects.create(
            user=self.user,
            access_token=access_token,
            client_id="test-device",
            name="Test Phone",
        )

        self.client.logout()
        self.client.get(TEST_URL, HTTP_AUTHORIZATION=f"Bearer {access_token.value}")

        profile.refresh_from_db()
        self.assertAlmostEqual(
            profile.last_active,
            timezone.now(),
            delta=timedelta(seconds=5),
        )


class TestLastActiveMiddlewareHijack(TestCase):
    """LastActiveMiddleware skips updates when an admin is impersonating the user."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = UserFactory(is_superuser=True, is_staff=True)
        cls.target = UserFactory()

    def _hijack(self):
        self.client.login(email=self.admin.email, password="testpass1234")
        response = self.client.post("/hijack/acquire/", {"user_pk": self.target.pk})
        # django-hijack redirects on a successful acquire; 200 here would mean the
        # form re-rendered with errors (e.g. permission denied, CSRF rejection) —
        # which we don't want to silently accept as "hijack succeeded".
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session.get("hijack_history") or [], [str(self.admin.pk)])

    def test_does_not_update_profile_when_hijacked(self):
        profile = self.target.profile
        old_time = timezone.now() - timedelta(hours=2)
        profile.last_active = old_time
        profile.save(update_fields=["last_active"])

        self._hijack()
        response = self.client.get(TEST_URL)

        self.assertEqual(response.wsgi_request.user.pk, self.target.pk)
        self.assertTrue(response.wsgi_request.user.is_hijacked)

        profile.refresh_from_db()
        self.assertEqual(profile.last_active, old_time)


class TestLastActiveMiddlewareHijackUnit(TestCase):
    """Direct middleware-level test for the hijack guard.

    Bypasses django-hijack's HTTP surface so the regression is pinned to the
    session-key contract `LastActiveMiddleware` actually reads, not to the
    URL/form behavior of any particular django-hijack release.
    """

    @classmethod
    def setUpTestData(cls):
        cls.admin = UserFactory(is_superuser=True, is_staff=True)
        cls.target = UserFactory()

    def test_does_not_update_profile_when_session_marks_hijack(self):
        profile = self.target.profile
        old_time = timezone.now() - timedelta(hours=2)
        profile.last_active = old_time
        profile.save(update_fields=["last_active"])

        request = RequestFactory().get(TEST_URL)
        request.session = {"hijack_history": [str(self.admin.pk)]}
        request.user = self.target

        middleware = LastActiveMiddleware(get_response=lambda r: HttpResponse())
        middleware(request)

        profile.refresh_from_db()
        self.assertEqual(profile.last_active, old_time)

    def test_updates_profile_when_session_has_no_hijack_history(self):
        """Sanity check: the same setup *without* hijack_history does update."""
        profile = self.target.profile
        old_time = timezone.now() - timedelta(hours=2)
        profile.last_active = old_time
        profile.save(update_fields=["last_active"])

        request = RequestFactory().get(TEST_URL)
        request.session = {}
        request.user = self.target

        middleware = LastActiveMiddleware(get_response=lambda r: HttpResponse())
        middleware(request)

        profile.refresh_from_db()
        self.assertGreater(profile.last_active, old_time)

    def test_does_not_update_profile_for_anonymous_user(self):
        request = RequestFactory().get(TEST_URL)
        request.session = {}
        request.user = AnonymousUser()

        middleware = LastActiveMiddleware(get_response=lambda r: HttpResponse())
        response = middleware(request)

        self.assertEqual(response.status_code, 200)

    def test_does_not_update_device_when_session_marks_hijack(self):
        """Defense-in-depth: even if a hijacked request carries a device token,
        the Device.last_active timestamp must not be bumped."""
        access_token = AccessToken.objects.create(user=self.target, managed_by=AccessTokenManagedBy.SYSTEM)
        device = Device.objects.create(
            user=self.target,
            access_token=access_token,
            client_id="hijack-unit-device",
            name="Target Phone",
        )
        old_time = timezone.now() - timedelta(hours=2)
        device.last_active = old_time
        device.save(update_fields=["last_active", "modified"])

        request = RequestFactory().get(TEST_URL)
        request.session = {"hijack_history": [str(self.admin.pk)]}
        request.user = self.target
        request._access_token = access_token

        middleware = LastActiveMiddleware(get_response=lambda r: HttpResponse())
        middleware(request)

        device.refresh_from_db()
        self.assertEqual(device.last_active, old_time)


class TestLastActiveMiddlewareDevice(TestCase):
    """LastActiveMiddleware updates Device.last_active when request uses a device token."""

    @classmethod
    def setUpTestData(cls):
        cls.user = UserFactory()

    def _create_device(self, **kwargs):
        access_token = AccessToken.objects.create(user=self.user, managed_by=AccessTokenManagedBy.SYSTEM)
        defaults = {
            "user": self.user,
            "access_token": access_token,
            "client_id": "test-uuid-1234",
            "name": "Test Phone",
        }
        defaults.update(kwargs)
        return Device.objects.create(**defaults)

    @override_settings(DEVICE_LAST_ACTIVE_THROTTLE_SECONDS=300)
    def test_updates_device_last_active_with_device_token(self):
        device = self._create_device()
        old_time = timezone.now() - timedelta(minutes=10)
        device.last_active = old_time
        device.save(update_fields=["last_active", "modified"])

        self.client.get(
            TEST_URL,
            HTTP_AUTHORIZATION=f"Bearer {device.access_token.value}",
        )

        device.refresh_from_db()
        self.assertGreater(device.last_active, old_time)

    @override_settings(DEVICE_LAST_ACTIVE_THROTTLE_SECONDS=300)
    def test_skips_device_last_active_when_recent(self):
        device = self._create_device()
        recent = timezone.now() - timedelta(minutes=2)
        device.last_active = recent
        device.save(update_fields=["last_active", "modified"])

        self.client.get(
            TEST_URL,
            HTTP_AUTHORIZATION=f"Bearer {device.access_token.value}",
        )

        device.refresh_from_db()
        self.assertEqual(device.last_active, recent)

    def test_does_not_update_device_for_session_auth(self):
        """Session-authenticated requests should not touch Device.last_active."""
        device = self._create_device()
        old_time = timezone.now() - timedelta(minutes=10)
        device.last_active = old_time
        device.save(update_fields=["last_active", "modified"])

        self.client.login(email=self.user.email, password="testpass1234")
        self.client.get(TEST_URL)
        self.client.logout()

        device.refresh_from_db()
        self.assertEqual(device.last_active, old_time)

    def test_does_not_update_device_for_default_token(self):
        """Default user-managed token should not touch Device.last_active."""
        device = self._create_device()
        old_time = timezone.now() - timedelta(minutes=10)
        device.last_active = old_time
        device.save(update_fields=["last_active", "modified"])

        default_token = AccessToken.objects.get_default_token_value(self.user.id)
        self.client.get(
            TEST_URL,
            HTTP_AUTHORIZATION=f"Bearer {default_token}",
        )

        device.refresh_from_db()
        self.assertEqual(device.last_active, old_time)

    def test_handles_token_without_device(self):
        """AccessToken without a linked Device should not raise an error."""
        access_token = AccessToken.objects.create(user=self.user, managed_by=AccessTokenManagedBy.USER)

        response = self.client.get(
            TEST_URL,
            HTTP_AUTHORIZATION=f"Bearer {access_token.value}",
        )

        self.assertEqual(response.status_code, 200)
