from http import HTTPStatus
from unittest.mock import patch

from core.tests.common import BaseAuthenticatedViewTestCase
from users.api.users import ALLOWED_SETTINGS_FIELDS
from users.models import Profile


class TestUpdateSettingsAPI(BaseAuthenticatedViewTestCase):
    def send_update_settings_api_request(self, data):
        url = "/api/users/settings/"
        return self.send_api_request(url=url, method="patch", data=data)

    def test_ok_update_settings(self):
        user = self.user
        orig_profile = Profile.objects.get(user=user)
        orig_tz = orig_profile.tz
        data = {"tz": "US/Pacific"}

        response = self.send_update_settings_api_request(data)
        payload = response.json()
        updated_profile = Profile.objects.get(user=user)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(payload["message"], "ok")
        self.assertIn("details", payload)
        self.assertEqual(updated_profile.tz, "US/Pacific")
        self.assertNotEqual(updated_profile.tz, orig_tz)

    def test_update_settings_ignores_blank_data(self):
        user = self.user
        orig_profile = Profile.objects.get(user=user)
        orig_tz = orig_profile.tz
        data = {}

        response = self.send_update_settings_api_request(data)
        payload = response.json()
        updated_profile = Profile.objects.get(user=user)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(payload["message"], "ok")
        self.assertNotIn("details", payload)
        self.assertEqual(updated_profile.tz, orig_tz)

    def test_update_settings_does_not_allow_unauth(self):
        data = {"tz": "US/Pacific"}
        self.client.logout()

        response = self.send_update_settings_api_request(data)

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)

    @patch("users.api.users.log_error")
    def test_update_settings_handles_errors(self, mocked_log_error):
        from django.utils import timezone

        user = self.user
        orig_profile = Profile.objects.get(user=user)
        orig_tz = orig_profile.tz
        data = {"tz": "US/Pacific"}

        # Set last_active to now so LastActiveMiddleware won't call save()
        orig_profile.last_active = timezone.now()
        orig_profile.save(update_fields=["last_active"])

        with patch.object(Profile, "save", side_effect=ValueError("TEST ERROR")):
            response = self.send_update_settings_api_request(data)

        payload = response.json()
        updated_profile = Profile.objects.get(user=user)

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIn("message", payload)
        self.assertNotIn("details", payload)
        self.assertEqual(updated_profile.tz, orig_tz)
        mocked_log_error.assert_called_once()


class TestUpdateSettingsWhitelist(BaseAuthenticatedViewTestCase):
    """Tests for the settings endpoint whitelist security."""

    def send_update_settings_api_request(self, data):
        url = "/api/users/settings/"
        return self.send_api_request(url=url, method="patch", data=data)

    def test_whitelist_contains_expected_fields(self):
        """Verify the whitelist contains exactly the expected fields."""
        expected_fields = {"tz", "keyboard_shortcuts"}
        self.assertEqual(ALLOWED_SETTINGS_FIELDS, expected_fields)

    def test_update_tz_allowed(self):
        """Verify tz field is in whitelist and can be updated."""
        self.assertIn("tz", ALLOWED_SETTINGS_FIELDS)

        orig_profile = Profile.objects.get(user=self.user)
        orig_tz = orig_profile.tz
        new_tz = "Europe/London"

        response = self.send_update_settings_api_request({"tz": new_tz})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        updated_profile = Profile.objects.get(user=self.user)
        self.assertEqual(updated_profile.tz, new_tz)
        self.assertNotEqual(updated_profile.tz, orig_tz)

    def test_update_keyboard_shortcuts_allowed(self):
        """Verify keyboard_shortcuts field is in whitelist and can be updated."""
        self.assertIn("keyboard_shortcuts", ALLOWED_SETTINGS_FIELDS)

        orig_profile = Profile.objects.get(user=self.user)
        new_shortcuts = {"ctrl+s": "save", "ctrl+n": "new"}

        response = self.send_update_settings_api_request({"keyboard_shortcuts": new_shortcuts})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        updated_profile = Profile.objects.get(user=self.user)
        self.assertEqual(updated_profile.keyboard_shortcuts, new_shortcuts)

    def test_update_multiple_allowed_fields(self):
        """Verify multiple whitelisted fields can be updated at once."""
        new_tz = "Asia/Tokyo"
        new_shortcuts = {"ctrl+b": "bold"}

        response = self.send_update_settings_api_request({"tz": new_tz, "keyboard_shortcuts": new_shortcuts})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        updated_profile = Profile.objects.get(user=self.user)
        self.assertEqual(updated_profile.tz, new_tz)
        self.assertEqual(updated_profile.keyboard_shortcuts, new_shortcuts)

    def test_sensitive_fields_not_in_whitelist(self):
        """Verify sensitive profile fields are NOT in the whitelist."""
        sensitive_fields = ["access_token", "last_active", "receive_product_updates", "demo_visits", "picture"]
        for field in sensitive_fields:
            self.assertNotIn(
                field, ALLOWED_SETTINGS_FIELDS, f"Sensitive field '{field}' should not be in ALLOWED_SETTINGS_FIELDS"
            )
