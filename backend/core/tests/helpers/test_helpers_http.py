from django.test import RequestFactory, SimpleTestCase

from core.helpers import is_hijacked_session


class TestIsHijackedSession(SimpleTestCase):
    """Tests helper `is_hijacked_session`.

    The helper guards `LastActiveMiddleware` against bumping a user's activity
    timestamps when an admin is impersonating them via django-hijack, so its
    behavior on missing/empty/populated session state is load-bearing.
    """

    def setUp(self):
        self.factory = RequestFactory()

    def test_returns_false_when_request_has_no_session(self):
        request = self.factory.get("/")

        self.assertFalse(is_hijacked_session(request))

    def test_returns_false_for_empty_session(self):
        request = self.factory.get("/")
        request.session = {}

        self.assertFalse(is_hijacked_session(request))

    def test_returns_false_when_hijack_history_is_empty_list(self):
        request = self.factory.get("/")
        request.session = {"hijack_history": []}

        self.assertFalse(is_hijacked_session(request))

    def test_returns_true_when_hijack_history_is_populated(self):
        request = self.factory.get("/")
        request.session = {"hijack_history": ["1"]}

        self.assertTrue(is_hijacked_session(request))
