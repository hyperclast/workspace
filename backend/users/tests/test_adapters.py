from unittest.mock import MagicMock

from django.conf import settings
from django.test import TestCase, RequestFactory, override_settings

from users.adapters import CustomHeadlessAdapter, _save_demo_visits_from_cookie
from users.tests.factories import UserFactory


class TestSaveDemoVisitsFromCookie(TestCase):
    def test_saves_demo_visits_and_updates_modified(self):
        user = UserFactory()
        original_modified = user.profile.modified

        request = MagicMock()
        request.COOKIES = {"demo_first_visit": "2026-01-15T10:00:00Z"}

        _save_demo_visits_from_cookie(request, user)
        user.profile.refresh_from_db()

        self.assertEqual(user.profile.demo_visits, ["2026-01-15T10:00:00Z"])
        self.assertGreaterEqual(user.profile.modified, original_modified)

    def test_no_cookie_does_not_save(self):
        user = UserFactory()
        original_modified = user.profile.modified

        request = MagicMock()
        request.COOKIES = {}

        _save_demo_visits_from_cookie(request, user)
        user.profile.refresh_from_db()

        self.assertEqual(user.profile.demo_visits, [])
        self.assertEqual(user.profile.modified, original_modified)


class TestSocialAccountAdapterSavesPicture(TestCase):
    def test_picture_save_updates_modified(self):
        """Test that saving a profile picture also updates the modified timestamp."""
        user = UserFactory()
        original_modified = user.profile.modified

        user.profile.picture = "https://example.com/photo.jpg"
        user.profile.save(update_fields=["picture", "modified"])
        user.profile.refresh_from_db()

        self.assertEqual(user.profile.picture, "https://example.com/photo.jpg")
        self.assertGreaterEqual(user.profile.modified, original_modified)


class TestCustomHeadlessAdapterGetFrontendUrl(TestCase):
    """Tests for CustomHeadlessAdapter.get_frontend_url() fallback behavior.

    The custom override prevents ImproperlyConfigured from being raised when
    a URL name is not in HEADLESS_FRONTEND_URLS (which crashes allauth's
    default adapter when HEADLESS_ONLY=True). Instead it falls back to
    FRONTEND_URL and logs a warning.
    """

    def _make_adapter(self):
        """Create an adapter with a real request in allauth's context."""
        from allauth.core.context import _request_var

        request = RequestFactory().get("/")
        self._context_token = _request_var.set(request)
        return CustomHeadlessAdapter()

    def tearDown(self):
        from allauth.core.context import _request_var

        if hasattr(self, "_context_token"):
            _request_var.reset(self._context_token)

    def test_returns_mapped_url_for_known_urlname(self):
        """Configured URL names return the correct URL."""
        adapter = self._make_adapter()

        url = adapter.get_frontend_url("account_signup")

        self.assertIn("/signup", url)

    def test_renders_url_template_with_kwargs(self):
        """URL templates with {key} placeholders are substituted correctly."""
        adapter = self._make_adapter()

        url = adapter.get_frontend_url("account_reset_password_from_key", key="abc-123-token")

        self.assertIn("abc-123-token", url)
        self.assertIn("/reset-password", url)
        # The {key} placeholder should be fully replaced
        self.assertNotIn("{key}", url)

    @override_settings(FRONTEND_URL="https://app.example.com")
    def test_falls_back_to_frontend_url_for_unknown_urlname(self):
        """Unmapped URL names fall back to FRONTEND_URL instead of crashing."""
        adapter = self._make_adapter()

        url = adapter.get_frontend_url("some_future_urlname_that_does_not_exist")

        self.assertEqual(url, "https://app.example.com/")

    @override_settings(FRONTEND_URL="https://app.example.com")
    def test_logs_warning_for_unknown_urlname(self):
        """A warning is logged when falling back for an unmapped URL name."""
        adapter = self._make_adapter()

        with self.assertLogs(level="WARNING") as cm:
            adapter.get_frontend_url("nonexistent_url_name")

        self.assertTrue(
            any("nonexistent_url_name" in msg for msg in cm.output),
            f"Expected warning about 'nonexistent_url_name' in logs, got: {cm.output}",
        )

    @override_settings(FRONTEND_URL="https://app.example.com")
    def test_logs_warning_includes_kwargs(self):
        """The fallback warning includes kwargs so missing placeholders are debuggable."""
        adapter = self._make_adapter()

        with self.assertLogs(level="WARNING") as cm:
            adapter.get_frontend_url("nonexistent_url_name", key="some-token")

        warning = next(msg for msg in cm.output if "nonexistent_url_name" in msg)
        self.assertIn("some-token", warning)


class TestHeadlessFrontendUrlsCompleteness(TestCase):
    """Verify HEADLESS_FRONTEND_URLS contains all URL names allauth can request.

    Allauth passes these URL names to get_frontend_url(). If a name is missing
    and HEADLESS_ONLY=True, the default adapter raises ImproperlyConfigured.
    Our CustomHeadlessAdapter falls back gracefully, but missing entries still
    cause degraded UX (e.g., emails linking to the app root instead of the
    correct page). This test ensures all known names are explicitly configured.
    """

    # All URL names allauth passes to get_frontend_url(), mapped to the
    # module where the call originates.
    KNOWN_URL_NAMES = {
        "account_signup",  # allauth.account.internal.flows.signup
        "account_confirm_email",  # allauth.account.internal.flows.email_verification
        "account_reset_password",  # allauth.account.internal.flows.password_reset
        "account_reset_password_from_key",  # allauth.account.internal.flows.password_reset
        "socialaccount_login_error",  # allauth.headless.socialaccount.internal
    }

    def test_all_known_headless_url_names_are_configured(self):
        """Every known allauth URL name must have an entry in HEADLESS_FRONTEND_URLS."""
        configured = set(settings.HEADLESS_FRONTEND_URLS.keys())
        missing = self.KNOWN_URL_NAMES - configured

        self.assertEqual(
            missing,
            set(),
            f"HEADLESS_FRONTEND_URLS is missing entries for: {missing}. "
            f"Add them to settings/base.py to avoid degraded UX or 500 errors.",
        )
