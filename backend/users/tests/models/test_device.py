from datetime import timedelta
from unittest.mock import patch

from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from users.constants import AccessTokenManagedBy, DeviceClientType
from users.models import AccessToken, Device
from users.tests.factories import UserFactory


class TestDeviceModel(TestCase):
    def _create_device(self, user=None, **kwargs):
        user = user or UserFactory()
        access_token = AccessToken.objects.create(
            user=user,
            managed_by=AccessTokenManagedBy.SYSTEM,
        )
        defaults = {
            "user": user,
            "access_token": access_token,
            "client_id": "test-uuid-1234",
            "name": "iPhone 15",
            "os": "ios",
            "app_version": "1.0.0",
        }
        defaults.update(kwargs)
        return Device.objects.create(**defaults)

    def test_creation_with_defaults(self):
        device = self._create_device()

        self.assertIsNotNone(device.id)
        self.assertIsNotNone(device.external_id)
        self.assertEqual(device.client_id, "test-uuid-1234")
        self.assertEqual(device.client_type, DeviceClientType.MOBILE)
        self.assertEqual(device.name, "iPhone 15")
        self.assertEqual(device.os, "ios")
        self.assertEqual(device.app_version, "1.0.0")
        self.assertEqual(device.push_token, "")
        self.assertIsNotNone(device.last_active)
        self.assertEqual(device.details, {})
        self.assertIsNotNone(device.created)
        self.assertIsNotNone(device.modified)

    def test_creation_with_client_type(self):
        device = self._create_device(client_type=DeviceClientType.CLI)

        self.assertEqual(device.client_type, DeviceClientType.CLI)

    def test_creation_with_details(self):
        details = {"screen_size": "6.1in", "model": "A2846"}
        device = self._create_device(details=details)

        self.assertEqual(device.details, details)

    def test_external_id_is_auto_generated_and_unique(self):
        user = UserFactory()
        device1 = self._create_device(user=user, client_id="uuid-1")
        device2 = self._create_device(user=UserFactory(), client_id="uuid-2")

        self.assertIsNotNone(device1.external_id)
        self.assertIsNotNone(device2.external_id)
        self.assertNotEqual(device1.external_id, device2.external_id)

    def test_unique_user_client_id_constraint(self):
        user = UserFactory()
        self._create_device(user=user, client_id="same-uuid")

        with self.assertRaises(IntegrityError):
            self._create_device(user=user, client_id="same-uuid")

    def test_same_client_id_different_users(self):
        user1 = UserFactory()
        user2 = UserFactory()

        device1 = self._create_device(user=user1, client_id="shared-uuid")
        device2 = self._create_device(user=user2, client_id="shared-uuid")

        self.assertNotEqual(device1.id, device2.id)

    def test_one_to_one_with_access_token(self):
        device = self._create_device()

        self.assertIsNotNone(device.access_token)
        self.assertEqual(device.access_token.device, device)

    def test_cascade_on_access_token_delete(self):
        device = self._create_device()
        device_id = device.id

        device.access_token.delete()

        self.assertFalse(Device.objects.filter(id=device_id).exists())

    def test_cascade_on_user_delete(self):
        user = UserFactory()
        self._create_device(user=user)
        user_id = user.id

        self.assertEqual(Device.objects.filter(user_id=user_id).count(), 1)

        user.delete()

        self.assertEqual(Device.objects.filter(user_id=user_id).count(), 0)

    def test_str_representation_with_name(self):
        device = self._create_device(name="My iPhone")

        self.assertIn("My iPhone", str(device))

    def test_str_representation_without_name(self):
        device = self._create_device(name="")

        self.assertIn("Unknown device", str(device))

    def test_update_last_active_when_stale(self):
        device = self._create_device()
        old_time = timezone.now() - timedelta(minutes=10)
        device.last_active = old_time
        device.save(update_fields=["last_active", "modified"])

        device.update_last_active()
        device.refresh_from_db()

        self.assertGreater(device.last_active, old_time)

    def test_update_last_active_skips_when_recent(self):
        device = self._create_device()
        recent_time = timezone.now() - timedelta(minutes=2)
        device.last_active = recent_time
        device.save(update_fields=["last_active", "modified"])

        with patch.object(Device, "save") as mock_save:
            device.update_last_active()
            mock_save.assert_not_called()

    def test_update_last_active_includes_modified(self):
        device = self._create_device()
        old_time = timezone.now() - timedelta(minutes=10)
        device.last_active = old_time
        device.save(update_fields=["last_active", "modified"])

        with patch.object(Device, "save") as mock_save:
            device.update_last_active()
            mock_save.assert_called_once_with(update_fields=["last_active", "modified"])

    def test_multiple_devices_per_user(self):
        user = UserFactory()
        self._create_device(user=user, client_id="phone-1")
        self._create_device(user=user, client_id="phone-2")

        self.assertEqual(Device.objects.filter(user=user).count(), 2)
