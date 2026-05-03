"""Tests for ask.helpers.validate_key module."""

from unittest.mock import Mock, patch

import requests
from django.test import TestCase

from ask.constants import AIProvider
from ask.helpers.validate_key import (
    ANTHROPIC_MODELS_URL,
    GOOGLE_MODELS_URL,
    OPENAI_MODELS_URL,
    _validate_anthropic_key,
    _validate_google_key,
    _validate_openai_key,
    validate_api_key,
)


def _http_error(status_code: int) -> requests.exceptions.HTTPError:
    response = Mock()
    response.status_code = status_code
    return requests.exceptions.HTTPError(f"{status_code} Error", response=response)


class TestValidateOpenAIKey(TestCase):
    @patch("ask.helpers.validate_key.send_api_request")
    def test_valid_key_returns_true_and_uses_correct_url_and_headers(self, mock_send):
        mock_send.return_value = {"data": [{"id": "gpt-4o-mini"}]}

        is_valid, error = _validate_openai_key("sk-good")

        self.assertTrue(is_valid)
        self.assertIsNone(error)
        mock_send.assert_called_once_with(
            OPENAI_MODELS_URL,
            method="get",
            headers={"Authorization": "Bearer sk-good"},
        )

    @patch("ask.helpers.validate_key.send_api_request")
    def test_401_returns_invalid_key(self, mock_send):
        mock_send.side_effect = _http_error(401)
        is_valid, error = _validate_openai_key("sk-bad")
        self.assertFalse(is_valid)
        self.assertEqual(error, "Invalid API key")

    @patch("ask.helpers.validate_key.send_api_request")
    def test_403_returns_invalid_key(self, mock_send):
        mock_send.side_effect = _http_error(403)
        is_valid, error = _validate_openai_key("sk-restricted")
        self.assertFalse(is_valid)
        self.assertEqual(error, "Invalid API key")

    @patch("ask.helpers.validate_key.send_api_request")
    def test_400_does_not_treat_as_invalid_key(self, mock_send):
        mock_send.side_effect = _http_error(400)
        is_valid, error = _validate_openai_key("sk-x")
        self.assertFalse(is_valid)
        self.assertEqual(error, "Validation failed: HTTP 400")

    @patch("ask.helpers.validate_key.send_api_request")
    def test_other_http_error_returns_validation_failed(self, mock_send):
        mock_send.side_effect = _http_error(404)
        is_valid, error = _validate_openai_key("sk-x")
        self.assertFalse(is_valid)
        self.assertEqual(error, "Validation failed: HTTP 404")

    @patch("ask.helpers.validate_key.send_api_request")
    def test_5xx_after_retries_returns_validation_failed(self, mock_send):
        mock_send.side_effect = _http_error(502)
        is_valid, error = _validate_openai_key("sk-x")
        self.assertFalse(is_valid)
        self.assertEqual(error, "Validation failed: HTTP 502")

    @patch("ask.helpers.validate_key.send_api_request")
    def test_connection_error_returns_validation_failed(self, mock_send):
        mock_send.side_effect = requests.exceptions.ConnectionError("dns failed")
        is_valid, error = _validate_openai_key("sk-x")
        self.assertFalse(is_valid)
        self.assertTrue(error.startswith("Validation failed:"))
        self.assertIn("dns failed", error)


class TestValidateAnthropicKey(TestCase):
    @patch("ask.helpers.validate_key.send_api_request")
    def test_valid_key_returns_true_and_uses_correct_url_and_headers(self, mock_send):
        mock_send.return_value = {"data": [{"id": "claude-haiku-4-5-20251001"}]}

        is_valid, error = _validate_anthropic_key("sk-ant-good")

        self.assertTrue(is_valid)
        self.assertIsNone(error)
        mock_send.assert_called_once_with(
            ANTHROPIC_MODELS_URL,
            method="get",
            headers={
                "x-api-key": "sk-ant-good",
                "anthropic-version": "2023-06-01",
            },
        )

    @patch("ask.helpers.validate_key.send_api_request")
    def test_401_returns_invalid_key(self, mock_send):
        mock_send.side_effect = _http_error(401)
        is_valid, error = _validate_anthropic_key("sk-ant-bad")
        self.assertFalse(is_valid)
        self.assertEqual(error, "Invalid API key")

    @patch("ask.helpers.validate_key.send_api_request")
    def test_403_returns_invalid_key(self, mock_send):
        mock_send.side_effect = _http_error(403)
        is_valid, error = _validate_anthropic_key("sk-ant-bad")
        self.assertFalse(is_valid)
        self.assertEqual(error, "Invalid API key")

    @patch("ask.helpers.validate_key.send_api_request")
    def test_400_does_not_treat_as_invalid_key(self, mock_send):
        mock_send.side_effect = _http_error(400)
        is_valid, error = _validate_anthropic_key("sk-ant-x")
        self.assertFalse(is_valid)
        self.assertEqual(error, "Validation failed: HTTP 400")


class TestValidateGoogleKey(TestCase):
    @patch("ask.helpers.validate_key.send_api_request")
    def test_valid_key_returns_true_and_uses_correct_url_and_headers(self, mock_send):
        mock_send.return_value = {"models": [{"name": "models/gemini-2.5-flash"}]}

        is_valid, error = _validate_google_key("AIza-good")

        self.assertTrue(is_valid)
        self.assertIsNone(error)
        mock_send.assert_called_once_with(
            GOOGLE_MODELS_URL,
            method="get",
            headers={"x-goog-api-key": "AIza-good"},
        )

    @patch("ask.helpers.validate_key.send_api_request")
    def test_400_returns_invalid_key(self, mock_send):
        mock_send.side_effect = _http_error(400)
        is_valid, error = _validate_google_key("AIza-bad")
        self.assertFalse(is_valid)
        self.assertEqual(error, "Invalid API key")

    @patch("ask.helpers.validate_key.send_api_request")
    def test_401_returns_invalid_key(self, mock_send):
        mock_send.side_effect = _http_error(401)
        is_valid, error = _validate_google_key("AIza-bad")
        self.assertFalse(is_valid)
        self.assertEqual(error, "Invalid API key")

    @patch("ask.helpers.validate_key.send_api_request")
    def test_403_returns_invalid_key(self, mock_send):
        mock_send.side_effect = _http_error(403)
        is_valid, error = _validate_google_key("AIza-restricted")
        self.assertFalse(is_valid)
        self.assertEqual(error, "Invalid API key")

    @patch("ask.helpers.validate_key.send_api_request")
    def test_other_http_error_returns_validation_failed(self, mock_send):
        mock_send.side_effect = _http_error(404)
        is_valid, error = _validate_google_key("AIza-x")
        self.assertFalse(is_valid)
        self.assertEqual(error, "Validation failed: HTTP 404")

    @patch("ask.helpers.validate_key.send_api_request")
    def test_connection_error_returns_validation_failed(self, mock_send):
        mock_send.side_effect = requests.exceptions.ConnectionError("connect refused")
        is_valid, error = _validate_google_key("AIza-x")
        self.assertFalse(is_valid)
        self.assertTrue(error.startswith("Validation failed:"))


class TestValidateAPIKeyDispatch(TestCase):
    """Dispatcher routes to correct validator and skips litellm for builtin providers."""

    @patch("ask.helpers.validate_key.litellm")
    @patch("ask.helpers.validate_key.send_api_request")
    def test_openai_does_not_call_litellm(self, mock_send, mock_litellm):
        mock_send.return_value = {"data": []}

        is_valid, error = validate_api_key(AIProvider.OPENAI.value, "sk-good")

        self.assertTrue(is_valid)
        self.assertIsNone(error)
        mock_litellm.completion.assert_not_called()

    @patch("ask.helpers.validate_key.litellm")
    @patch("ask.helpers.validate_key.send_api_request")
    def test_anthropic_does_not_call_litellm(self, mock_send, mock_litellm):
        mock_send.return_value = {"data": []}

        is_valid, error = validate_api_key(AIProvider.ANTHROPIC.value, "sk-ant-good")

        self.assertTrue(is_valid)
        self.assertIsNone(error)
        mock_litellm.completion.assert_not_called()

    @patch("ask.helpers.validate_key.litellm")
    @patch("ask.helpers.validate_key.send_api_request")
    def test_google_does_not_call_litellm(self, mock_send, mock_litellm):
        mock_send.return_value = {"models": []}

        is_valid, error = validate_api_key(AIProvider.GOOGLE.value, "AIza-good")

        self.assertTrue(is_valid)
        self.assertIsNone(error)
        mock_litellm.completion.assert_not_called()

    def test_empty_api_key_for_builtin_returns_required_error(self):
        is_valid, error = validate_api_key(AIProvider.OPENAI.value, "")
        self.assertFalse(is_valid)
        self.assertEqual(error, "API key is required")

    def test_unknown_provider_returns_error(self):
        is_valid, error = validate_api_key("foo", "sk-x")
        self.assertFalse(is_valid)
        self.assertEqual(error, "Unknown provider: foo")

    @patch("ask.helpers.validate_key.send_api_request")
    def test_openai_invalid_key_via_dispatcher(self, mock_send):
        mock_send.side_effect = _http_error(401)
        is_valid, error = validate_api_key(AIProvider.OPENAI.value, "sk-bad")
        self.assertFalse(is_valid)
        self.assertEqual(error, "Invalid API key")
