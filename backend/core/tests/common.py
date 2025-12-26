from typing import Optional

from django.shortcuts import reverse
from django.test import TestCase
from django.utils.http import urlencode

from users.tests.factories import TEST_USER_PASSWORD, UserFactory


class BaseViewTestCase(TestCase):
    """Common logic for testing unauthenticated views."""

    url_name = None

    def send_request(
        self,
        url: Optional[str] = None,
        method: Optional[str] = "get",
        query_params: Optional[dict] = None,
        path_params: Optional[dict] = None,
        data: Optional[dict] = None,
        **kwargs,
    ):
        if not url:
            url = reverse(self.url_name, kwargs=path_params)

        if query_params:
            url = f"{url}?{urlencode(query_params)}"

        req = getattr(self.client, method)

        return req(url, data=data, **kwargs)

    def send_api_request(
        self,
        url: Optional[str] = None,
        method: Optional[str] = "get",
        query_params: Optional[dict] = None,
        path_params: Optional[dict] = None,
        data: Optional[dict] = None,
        **kwargs,
    ):
        return self.send_request(
            url, method, query_params, path_params, data, content_type="application/json", **kwargs
        )


class BaseAuthenticatedViewTestCase(BaseViewTestCase):
    """Common logic for testing authenticated views."""

    login_using = "email"

    @classmethod
    def setUpTestData(cls):
        cls.user = UserFactory()

    def setUp(self):
        self.login(self.user)

    def tearDown(self):
        self.client.logout()

    def login(self, user):
        login_creds = {
            self.login_using: getattr(user, self.login_using, None),
            "password": TEST_USER_PASSWORD,
        }
        self.client.login(**login_creds)
