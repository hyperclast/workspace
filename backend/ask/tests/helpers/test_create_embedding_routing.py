"""Tests for what `create_embedding` actually sends to litellm — the call shape,
not the side-effects on the audit table (those live in
test_embedding_usage_recording.py).
"""

from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase, override_settings

from ask.constants import AIProvider
from ask.helpers.embeddings import compute_embedding, create_embedding
from pages.tests.factories import PageFactory
from users.models import AIProviderConfig
from users.tests.factories import UserFactory


def _ok_response():
    return SimpleNamespace(
        data=[{"embedding": [0.0] * 1536}],
        usage=SimpleNamespace(prompt_tokens=5, total_tokens=5),
        model="text-embedding-3-small",
    )


@override_settings(EMBEDDINGS_SERVER_API_KEY="sk-server")
class TestApiBaseForwarding(TestCase):
    """When a base URL is set, it must reach litellm — that's what lets
    operators point at Azure OpenAI / proxies / OpenAI-compatible servers."""

    @override_settings(EMBEDDINGS_SERVER_API_BASE_URL="https://azure.example/v1")
    @patch("ask.helpers.embeddings.embedding")
    def test_server_base_url_passed_as_api_base(self, mock_embedding):
        mock_embedding.return_value = _ok_response()

        create_embedding("hello")

        _, kwargs = mock_embedding.call_args
        self.assertEqual(kwargs["api_key"], "sk-server")
        self.assertEqual(kwargs["api_base"], "https://azure.example/v1")

    @override_settings(EMBEDDINGS_SERVER_API_BASE_URL="")
    @patch("ask.helpers.embeddings.embedding")
    def test_no_api_base_kwarg_when_unset(self, mock_embedding):
        """Don't pass api_base=None — litellm interprets that as an explicit override.
        Omit the kwarg entirely so litellm uses its own defaults."""
        mock_embedding.return_value = _ok_response()

        create_embedding("hello")

        _, kwargs = mock_embedding.call_args
        self.assertNotIn("api_base", kwargs)


@override_settings(EMBEDDINGS_SERVER_API_KEY="")
class TestUserConfigBaseUrlForwarding(TestCase):
    """The self-host fallback path must also honor the user's configured base URL,
    not just their key — otherwise Azure-OpenAI self-hosters can't use embeddings."""

    @patch("ask.helpers.embeddings.embedding")
    def test_user_config_base_url_forwarded(self, mock_embedding):
        mock_embedding.return_value = _ok_response()
        user = UserFactory()
        AIProviderConfig.objects.create(
            user=user,
            provider=AIProvider.OPENAI.value,
            api_key="sk-user",
            api_base_url="https://self-hosted-proxy/v1",
            is_enabled=True,
            is_validated=True,
        )

        create_embedding("hello", user=user)

        _, kwargs = mock_embedding.call_args
        self.assertEqual(kwargs["api_key"], "sk-user")
        self.assertEqual(kwargs["api_base"], "https://self-hosted-proxy/v1")


@override_settings(EMBEDDINGS_SERVER_API_KEY="sk-server")
class TestComputeEmbeddingThreading(TestCase):
    """`page` and `kind` are recently-added kwargs that must reach
    `create_embedding`. Without this guard, a future refactor could quietly
    drop them and we'd lose attribution on indexed pages."""

    @patch("ask.helpers.embeddings.create_embedding")
    @patch("ask.helpers.embeddings.truncate_input_data")
    def test_compute_embedding_passes_page_and_kind(self, mock_truncate, mock_create):
        mock_truncate.return_value = "truncated"
        mock_create.return_value = [0.0] * 1536
        user = UserFactory()
        page = PageFactory(creator=user)

        compute_embedding("body", user=user, page=page, kind="index")

        _, kwargs = mock_create.call_args
        self.assertEqual(kwargs["page"], page)
        self.assertEqual(kwargs["kind"], "index")
        self.assertEqual(kwargs["user"], user)

    @patch("ask.helpers.embeddings.create_embedding")
    @patch("ask.helpers.embeddings.truncate_input_data")
    def test_compute_embedding_defaults_to_query_kind_no_page(self, mock_truncate, mock_create):
        mock_truncate.return_value = "truncated"
        mock_create.return_value = [0.0] * 1536

        compute_embedding("a question", user=UserFactory())

        _, kwargs = mock_create.call_args
        self.assertEqual(kwargs["kind"], "query")
        self.assertIsNone(kwargs["page"])


@override_settings(EMBEDDINGS_SERVER_API_KEY="sk-server")
class TestCallShape(TestCase):
    """Sanity guards on the basic kwargs into litellm.embedding so a change to
    the wrapper surfaces here instead of as a runtime 4xx in production."""

    @patch("ask.helpers.embeddings.embedding")
    def test_input_is_wrapped_in_a_list(self, mock_embedding):
        """litellm.embedding takes a list of inputs; passing a bare string
        works for some providers but breaks token counting on others."""
        mock_embedding.return_value = _ok_response()

        create_embedding("hello world")

        _, kwargs = mock_embedding.call_args
        self.assertEqual(kwargs["input"], ["hello world"])

    @patch("ask.helpers.embeddings.embedding")
    def test_default_model_passed_when_caller_omits(self, mock_embedding):
        mock_embedding.return_value = _ok_response()

        create_embedding("hello")

        _, kwargs = mock_embedding.call_args
        self.assertEqual(kwargs["model"], settings.ASK_EMBEDDINGS_DEFAULT_MODEL)
