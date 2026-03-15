import json
from http import HTTPStatus

from django.test import TestCase

from users.constants import AccessTokenManagedBy, DeviceClientType
from users.models import AccessToken, Device
from users.tests.factories import UserFactory


BASE_URL = "/api/users/me/devices/"


class TestRegisterDevice(TestCase):
    """Test POST /api/users/me/devices/ endpoint."""

    @classmethod
    def setUpTestData(cls):
        cls.user = UserFactory()

    def setUp(self):
        self.client.login(email=self.user.email, password="testpass1234")

    def tearDown(self):
        self.client.logout()

    def _register(self, data):
        return self.client.post(
            BASE_URL,
            data=json.dumps(data),
            content_type="application/json",
        )

    def test_creates_device_and_access_token(self):
        response = self._register({"client_id": "uuid-new-device"})

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        payload = response.json()
        self.assertIn("access_token", payload)
        self.assertEqual(payload["client_id"], "uuid-new-device")

        device = Device.objects.get(user=self.user, client_id="uuid-new-device")
        self.assertEqual(device.client_type, DeviceClientType.MOBILE)
        self.assertEqual(device.access_token.managed_by, AccessTokenManagedBy.SYSTEM)
        self.assertTrue(device.access_token.is_active)
        self.assertEqual(device.access_token.value, payload["access_token"])

    def test_rotates_token_on_re_registration(self):
        resp1 = self._register({"client_id": "uuid-reuse"})
        old_token = resp1.json()["access_token"]

        resp2 = self._register({"client_id": "uuid-reuse"})
        new_token = resp2.json()["access_token"]

        self.assertEqual(resp2.status_code, HTTPStatus.CREATED)
        self.assertNotEqual(old_token, new_token)

        # Only one device row exists
        self.assertEqual(Device.objects.filter(user=self.user, client_id="uuid-reuse").count(), 1)

    def test_reactivates_revoked_device(self):
        resp1 = self._register({"client_id": "uuid-revoked"})
        old_token = resp1.json()["access_token"]

        # Revoke the device
        device = Device.objects.get(user=self.user, client_id="uuid-revoked")
        device.access_token.is_active = False
        device.access_token.save(update_fields=["is_active", "modified"])

        # Re-register
        resp2 = self._register({"client_id": "uuid-revoked"})
        new_token = resp2.json()["access_token"]

        self.assertEqual(resp2.status_code, HTTPStatus.CREATED)
        self.assertNotEqual(old_token, new_token)

        device.access_token.refresh_from_db()
        self.assertTrue(device.access_token.is_active)

    def test_populates_metadata_on_creation(self):
        self._register(
            {
                "client_id": "uuid-meta",
                "name": "iPhone 15",
                "os": "ios",
                "app_version": "1.0.0",
                "details": {"screen_size": "6.1in"},
            }
        )

        device = Device.objects.get(user=self.user, client_id="uuid-meta")
        self.assertEqual(device.name, "iPhone 15")
        self.assertEqual(device.os, "ios")
        self.assertEqual(device.app_version, "1.0.0")
        self.assertEqual(device.details, {"screen_size": "6.1in"})

    def test_updates_metadata_on_re_registration(self):
        self._register(
            {
                "client_id": "uuid-update",
                "name": "iPhone 14",
                "os": "ios",
                "app_version": "1.0.0",
            }
        )

        self._register(
            {
                "client_id": "uuid-update",
                "name": "iPhone 15",
                "app_version": "2.0.0",
            }
        )

        device = Device.objects.get(user=self.user, client_id="uuid-update")
        self.assertEqual(device.name, "iPhone 15")
        self.assertEqual(device.os, "ios")  # Kept from first registration
        self.assertEqual(device.app_version, "2.0.0")

    def test_defaults_empty_metadata_on_creation(self):
        self._register({"client_id": "uuid-minimal"})

        device = Device.objects.get(user=self.user, client_id="uuid-minimal")
        self.assertEqual(device.name, "")
        self.assertEqual(device.os, "")
        self.assertEqual(device.app_version, "")
        self.assertEqual(device.details, {})

    def test_requires_authentication(self):
        self.client.logout()

        response = self._register({"client_id": "uuid-unauthed"})

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)

    def test_token_auth_works_for_registration(self):
        """Device registration should also work with bearer token auth."""
        self.client.logout()
        token = self.user.profile.access_token

        response = self.client.post(
            BASE_URL,
            data=json.dumps({"client_id": "uuid-bearer"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, HTTPStatus.CREATED)


class TestListDevices(TestCase):
    """Test GET /api/users/me/devices/ endpoint."""

    @classmethod
    def setUpTestData(cls):
        cls.user = UserFactory()
        cls.other_user = UserFactory()

    def setUp(self):
        self.client.login(email=self.user.email, password="testpass1234")

    def tearDown(self):
        self.client.logout()

    def _create_device(self, user, client_id, **kwargs):
        token = AccessToken.objects.create(user=user, managed_by=AccessTokenManagedBy.SYSTEM)
        defaults = {
            "user": user,
            "access_token": token,
            "client_id": client_id,
            "name": "Test Device",
            "os": "ios",
            "app_version": "1.0.0",
        }
        defaults.update(kwargs)
        return Device.objects.create(**defaults)

    def test_lists_user_devices(self):
        self._create_device(self.user, "device-1", name="Phone 1")
        self._create_device(self.user, "device-2", name="Phone 2")

        response = self.client.get(BASE_URL)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(len(data), 2)
        client_ids = {d["client_id"] for d in data}
        self.assertEqual(client_ids, {"device-1", "device-2"})

    def test_excludes_other_users_devices(self):
        self._create_device(self.user, "my-device")
        self._create_device(self.other_user, "other-device")

        response = self.client.get(BASE_URL)

        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["client_id"], "my-device")

    def test_excludes_deactivated_tokens(self):
        device = self._create_device(self.user, "revoked-device")
        device.access_token.is_active = False
        device.access_token.save(update_fields=["is_active", "modified"])
        self._create_device(self.user, "active-device")

        response = self.client.get(BASE_URL)

        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["client_id"], "active-device")

    def test_is_current_flag_with_device_token(self):
        device = self._create_device(self.user, "current-device")
        self._create_device(self.user, "other-device")

        self.client.logout()
        response = self.client.get(
            BASE_URL,
            HTTP_AUTHORIZATION=f"Bearer {device.access_token.value}",
        )

        data = response.json()
        current = {d["client_id"]: d["is_current"] for d in data}
        self.assertTrue(current["current-device"])
        self.assertFalse(current["other-device"])

    def test_is_current_false_for_session_auth(self):
        self._create_device(self.user, "some-device")

        response = self.client.get(BASE_URL)

        data = response.json()
        self.assertFalse(data[0]["is_current"])

    def test_response_includes_client_type_and_details(self):
        self._create_device(
            self.user,
            "typed-device",
            client_type=DeviceClientType.CLI,
            details={"version": "2.0"},
        )

        response = self.client.get(BASE_URL)

        data = response.json()
        self.assertEqual(data[0]["client_type"], DeviceClientType.CLI)
        self.assertEqual(data[0]["details"], {"version": "2.0"})

    def test_requires_authentication(self):
        self.client.logout()

        response = self.client.get(BASE_URL)

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)


class TestRevokeDevice(TestCase):
    """Test DELETE /api/users/me/devices/{client_id}/ endpoint."""

    @classmethod
    def setUpTestData(cls):
        cls.user = UserFactory()
        cls.other_user = UserFactory()

    def setUp(self):
        self.client.login(email=self.user.email, password="testpass1234")

    def tearDown(self):
        self.client.logout()

    def _create_device(self, user, client_id):
        token = AccessToken.objects.create(user=user, managed_by=AccessTokenManagedBy.SYSTEM)
        return Device.objects.create(
            user=user,
            access_token=token,
            client_id=client_id,
            name="Test Device",
            os="ios",
            app_version="1.0.0",
        )

    def test_deactivates_device_token(self):
        device = self._create_device(self.user, "to-revoke")

        response = self.client.delete(f"{BASE_URL}to-revoke/")

        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)
        device.access_token.refresh_from_db()
        self.assertFalse(device.access_token.is_active)

    def test_revoked_token_returns_401(self):
        device = self._create_device(self.user, "to-revoke-2")
        token_value = device.access_token.value

        self.client.delete(f"{BASE_URL}to-revoke-2/")

        # Try using the revoked token
        self.client.logout()
        response = self.client.get(
            "/api/users/me/",
            HTTP_AUTHORIZATION=f"Bearer {token_value}",
        )
        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)

    def test_cannot_revoke_other_users_device(self):
        self._create_device(self.other_user, "not-mine")

        response = self.client.delete(f"{BASE_URL}not-mine/")

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_cannot_revoke_already_revoked_device(self):
        device = self._create_device(self.user, "already-revoked")
        device.access_token.is_active = False
        device.access_token.save(update_fields=["is_active", "modified"])

        response = self.client.delete(f"{BASE_URL}already-revoked/")

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_requires_authentication(self):
        self.client.logout()

        response = self.client.delete(f"{BASE_URL}some-device/")

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)


class TestUpdateDevice(TestCase):
    """Test PATCH /api/users/me/devices/{client_id}/ endpoint."""

    @classmethod
    def setUpTestData(cls):
        cls.user = UserFactory()
        cls.other_user = UserFactory()

    def setUp(self):
        self.client.login(email=self.user.email, password="testpass1234")

    def tearDown(self):
        self.client.logout()

    def _create_device(self, user, client_id, **kwargs):
        token = AccessToken.objects.create(user=user, managed_by=AccessTokenManagedBy.SYSTEM)
        defaults = {
            "user": user,
            "access_token": token,
            "client_id": client_id,
            "name": "Test Device",
            "os": "ios",
            "app_version": "1.0.0",
        }
        defaults.update(kwargs)
        return Device.objects.create(**defaults)

    def test_updates_metadata_fields(self):
        self._create_device(self.user, "to-update")

        response = self.client.patch(
            f"{BASE_URL}to-update/",
            data=json.dumps({"name": "New Name", "app_version": "2.0.0"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        device = Device.objects.get(user=self.user, client_id="to-update")
        self.assertEqual(device.name, "New Name")
        self.assertEqual(device.app_version, "2.0.0")
        self.assertEqual(device.os, "ios")  # Unchanged

    def test_updates_details_json(self):
        self._create_device(self.user, "to-update-details", details={"old": "value"})

        response = self.client.patch(
            f"{BASE_URL}to-update-details/",
            data=json.dumps({"details": {"new": "value"}}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        device = Device.objects.get(user=self.user, client_id="to-update-details")
        self.assertEqual(device.details, {"new": "value"})

    def test_cannot_update_other_users_device(self):
        self._create_device(self.other_user, "not-mine")

        response = self.client.patch(
            f"{BASE_URL}not-mine/",
            data=json.dumps({"name": "Hacked"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_cannot_update_revoked_device(self):
        device = self._create_device(self.user, "revoked")
        device.access_token.is_active = False
        device.access_token.save(update_fields=["is_active", "modified"])

        response = self.client.patch(
            f"{BASE_URL}revoked/",
            data=json.dumps({"name": "Updated"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_requires_authentication(self):
        self.client.logout()

        response = self.client.patch(
            f"{BASE_URL}some-device/",
            data=json.dumps({"name": "Updated"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)

    def test_response_includes_device_fields(self):
        self._create_device(self.user, "full-response", name="My Phone")

        response = self.client.patch(
            f"{BASE_URL}full-response/",
            data=json.dumps({"app_version": "3.0.0"}),
            content_type="application/json",
        )

        data = response.json()
        self.assertEqual(data["client_id"], "full-response")
        self.assertEqual(data["name"], "My Phone")
        self.assertEqual(data["app_version"], "3.0.0")
        self.assertIn("last_active", data)
        self.assertIn("created", data)
        self.assertIn("is_current", data)
