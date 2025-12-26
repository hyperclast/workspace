from http import HTTPStatus

from core.tests.common import BaseAuthenticatedViewTestCase
from users.tests.factories import UserFactory


class TestUpdateUserAPI(BaseAuthenticatedViewTestCase):
    def send_update_user_request(self, data):
        return self.send_api_request(url="/api/users/me/", method="patch", data=data)

    def test_update_username_success(self):
        response = self.send_update_user_request({"username": "newusername"})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "newusername")

    def test_update_username_with_hyphens_underscores(self):
        response = self.send_update_user_request({"username": "new-user_name123"})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "new-user_name123")

    def test_update_username_rejects_special_chars(self):
        response = self.send_update_user_request({"username": "user@name"})

        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)
        self.user.refresh_from_db()
        self.assertNotEqual(self.user.username, "user@name")

    def test_update_username_rejects_spaces(self):
        response = self.send_update_user_request({"username": "user name"})

        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)

    def test_update_username_allows_dots(self):
        response = self.send_update_user_request({"username": "user.name"})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "user.name")

    def test_update_username_case_insensitive_uniqueness(self):
        UserFactory(username="ExistingUser")

        response = self.send_update_user_request({"username": "existinguser"})

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        payload = response.json()
        self.assertEqual(payload["message"], "Username is already taken")

    def test_update_username_case_insensitive_uniqueness_uppercase(self):
        UserFactory(username="existinguser")

        response = self.send_update_user_request({"username": "EXISTINGUSER"})

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        payload = response.json()
        self.assertEqual(payload["message"], "Username is already taken")

    def test_update_username_allows_own_username_different_case(self):
        self.user.username = "myusername"
        self.user.save()

        response = self.send_update_user_request({"username": "MyUsername"})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "MyUsername")

    def test_update_username_mixed_case_allowed(self):
        response = self.send_update_user_request({"username": "CamelCaseUser"})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "CamelCaseUser")
