"""Tests for the token CRUD endpoints (Step 5b).

These tests will fail until the endpoints are implemented.
Endpoints under test:
  GET    /api/users/me/tokens/                  — list user-managed tokens
  POST   /api/users/me/tokens/                  — create a new user-managed token
  GET    /api/users/me/tokens/{external_id}/    — retrieve a specific token
  PATCH  /api/users/me/tokens/{external_id}/    — update label / activate / deactivate
"""

import json
from http import HTTPStatus

from django.test import TestCase

from users.constants import AccessTokenManagedBy
from users.models import AccessToken
from users.tests.factories import UserFactory


BASE_URL = "/api/users/me/tokens/"


class TestListAccessTokens(TestCase):
    """Test GET /api/users/me/tokens/ endpoint."""

    @classmethod
    def setUpTestData(cls):
        cls.user = UserFactory()
        cls.other_user = UserFactory()

    def setUp(self):
        self.client.login(email=self.user.email, password="testpass1234")

    def tearDown(self):
        self.client.logout()

    def test_lists_user_managed_tokens(self):
        """Returns the signal-created default + manually created tokens."""
        AccessToken.objects.create(user=self.user, managed_by=AccessTokenManagedBy.USER, label="Extra")

        response = self.client.get(BASE_URL)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        # Signal creates 1 default, plus 1 manual = 2 total
        self.assertEqual(len(data), 2)
        for token_data in data:
            self.assertIn("external_id", token_data)
            self.assertIn("value", token_data)
            self.assertIn("label", token_data)
            self.assertIn("is_default", token_data)
            self.assertIn("is_active", token_data)
            self.assertIn("created", token_data)

    def test_excludes_system_managed_tokens(self):
        """System-managed tokens (device tokens) are not listed."""
        AccessToken.objects.create(user=self.user, managed_by=AccessTokenManagedBy.SYSTEM)

        response = self.client.get(BASE_URL)

        data = response.json()
        # Only the signal-created default user-managed token
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["is_default"], True)

    def test_excludes_other_users_tokens(self):
        """Tokens belonging to other users are not listed."""
        AccessToken.objects.create(user=self.other_user, managed_by=AccessTokenManagedBy.USER, label="Other")

        response = self.client.get(BASE_URL)

        data = response.json()
        self.assertEqual(len(data), 1)  # Only the current user's default

    def test_ordered_by_newest_first(self):
        """Tokens are returned newest first."""
        extra = AccessToken.objects.create(user=self.user, managed_by=AccessTokenManagedBy.USER, label="Newer")

        response = self.client.get(BASE_URL)

        data = response.json()
        self.assertEqual(data[0]["external_id"], extra.external_id)

    def test_requires_authentication(self):
        self.client.logout()

        response = self.client.get(BASE_URL)

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)


class TestCreateAccessToken(TestCase):
    """Test POST /api/users/me/tokens/ endpoint."""

    @classmethod
    def setUpTestData(cls):
        cls.user = UserFactory()

    def setUp(self):
        self.client.login(email=self.user.email, password="testpass1234")

    def tearDown(self):
        self.client.logout()

    def _create(self, data):
        return self.client.post(
            BASE_URL,
            data=json.dumps(data),
            content_type="application/json",
        )

    def test_creates_user_managed_token(self):
        response = self._create({"label": "Deploy Script"})

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        data = response.json()
        self.assertEqual(data["label"], "Deploy Script")
        self.assertFalse(data["is_default"])
        self.assertTrue(data["is_active"])
        self.assertIn("value", data)
        self.assertTrue(len(data["value"]) > 0)

    def test_created_token_does_not_steal_default(self):
        """Newly created tokens have is_default=False."""
        response = self._create({"label": "New Token"})

        data = response.json()
        self.assertFalse(data["is_default"])

        # The original default token is still the default
        default = AccessToken.objects.get_default_token(self.user.id)
        self.assertIsNotNone(default)
        self.assertNotEqual(default.external_id, data["external_id"])

    def test_requires_authentication(self):
        self.client.logout()

        response = self._create({"label": "Unauthed"})

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)


class TestRetrieveAccessToken(TestCase):
    """Test GET /api/users/me/tokens/{external_id}/ endpoint."""

    @classmethod
    def setUpTestData(cls):
        cls.user = UserFactory()
        cls.other_user = UserFactory()

    def setUp(self):
        self.client.login(email=self.user.email, password="testpass1234")

    def tearDown(self):
        self.client.logout()

    def test_retrieves_own_token(self):
        token = AccessToken.objects.create(user=self.user, managed_by=AccessTokenManagedBy.USER, label="My Token")

        response = self.client.get(f"{BASE_URL}{token.external_id}/")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(data["external_id"], token.external_id)
        self.assertEqual(data["label"], "My Token")
        self.assertEqual(data["value"], token.value)

    def test_returns_404_for_other_users_token(self):
        other_token = AccessToken.objects.create(
            user=self.other_user, managed_by=AccessTokenManagedBy.USER, label="Other"
        )

        response = self.client.get(f"{BASE_URL}{other_token.external_id}/")

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_returns_404_for_system_managed_token(self):
        system_token = AccessToken.objects.create(user=self.user, managed_by=AccessTokenManagedBy.SYSTEM)

        response = self.client.get(f"{BASE_URL}{system_token.external_id}/")

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_requires_authentication(self):
        self.client.logout()
        token = AccessToken.objects.get(user=self.user, is_default=True)

        response = self.client.get(f"{BASE_URL}{token.external_id}/")

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)


class TestUpdateAccessToken(TestCase):
    """Test PATCH /api/users/me/tokens/{external_id}/ endpoint."""

    @classmethod
    def setUpTestData(cls):
        cls.user = UserFactory()
        cls.other_user = UserFactory()

    def setUp(self):
        self.client.login(email=self.user.email, password="testpass1234")

    def tearDown(self):
        self.client.logout()

    def _patch(self, external_id, data):
        return self.client.patch(
            f"{BASE_URL}{external_id}/",
            data=json.dumps(data),
            content_type="application/json",
        )

    def test_updates_label(self):
        token = AccessToken.objects.create(user=self.user, managed_by=AccessTokenManagedBy.USER, label="Old Label")

        response = self._patch(token.external_id, {"label": "New Label"})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        token.refresh_from_db()
        self.assertEqual(token.label, "New Label")
        # is_active should be unchanged
        self.assertTrue(token.is_active)

    def test_deactivates_non_default_token(self):
        token = AccessToken.objects.create(user=self.user, managed_by=AccessTokenManagedBy.USER, label="Deactivate Me")

        response = self._patch(token.external_id, {"is_active": False})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        token.refresh_from_db()
        self.assertFalse(token.is_active)

    def test_reactivates_token(self):
        token = AccessToken.objects.create(
            user=self.user,
            managed_by=AccessTokenManagedBy.USER,
            label="Reactivate Me",
            is_active=False,
        )

        response = self._patch(token.external_id, {"is_active": True})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        token.refresh_from_db()
        self.assertTrue(token.is_active)

    def test_cannot_deactivate_default_token(self):
        """Deactivating the default token is rejected."""
        default_token = AccessToken.objects.get_default_token(self.user.id)

        response = self._patch(default_token.external_id, {"is_active": False})

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        default_token.refresh_from_db()
        self.assertTrue(default_token.is_active)

    def test_update_label_only_does_not_change_is_active(self):
        token = AccessToken.objects.create(user=self.user, managed_by=AccessTokenManagedBy.USER, label="Original")

        response = self._patch(token.external_id, {"label": "Updated"})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        token.refresh_from_db()
        self.assertEqual(token.label, "Updated")
        self.assertTrue(token.is_active)

    def test_update_is_active_only_does_not_change_label(self):
        token = AccessToken.objects.create(user=self.user, managed_by=AccessTokenManagedBy.USER, label="Keep This")

        response = self._patch(token.external_id, {"is_active": False})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        token.refresh_from_db()
        self.assertEqual(token.label, "Keep This")
        self.assertFalse(token.is_active)

    def test_returns_404_for_other_users_token(self):
        other_token = AccessToken.objects.create(
            user=self.other_user, managed_by=AccessTokenManagedBy.USER, label="Other"
        )

        response = self._patch(other_token.external_id, {"label": "Hacked"})

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_returns_404_for_system_managed_token(self):
        system_token = AccessToken.objects.create(user=self.user, managed_by=AccessTokenManagedBy.SYSTEM)

        response = self._patch(system_token.external_id, {"label": "Hacked"})

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_requires_authentication(self):
        self.client.logout()
        token = AccessToken.objects.get(user=self.user, is_default=True)

        response = self._patch(token.external_id, {"label": "Unauthed"})

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)
