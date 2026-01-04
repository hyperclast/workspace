from http import HTTPStatus
from unittest.mock import patch

from core.tests.common import BaseAuthenticatedViewTestCase
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
