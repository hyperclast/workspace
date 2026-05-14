"""Tests that successful embedding calls write an EmbeddingUsage audit row."""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.conf import settings
from django.test import TestCase, override_settings

from ask.helpers.embeddings import (
    EMBEDDING_COST_PER_MILLION_TOKENS,
    _compute_embedding_cost,
    _extract_usage_tokens,
    collect_embedding_usage,
    create_embedding,
)
from ask.models import EmbeddingUsage
from pages.tests.factories import PageFactory
from users.tests.factories import UserFactory


def _build_litellm_response(*, embedding_dims=1536, prompt_tokens=10, total_tokens=10):
    """Minimal stand-in for a litellm embedding response.

    SimpleNamespace mirrors the attribute access pattern (`response.data`,
    `response.usage.prompt_tokens`) — a real-shaped object without pulling in
    litellm internals.
    """
    return SimpleNamespace(
        data=[{"embedding": [0.0] * embedding_dims}],
        usage=SimpleNamespace(prompt_tokens=prompt_tokens, total_tokens=total_tokens),
        model=settings.ASK_EMBEDDINGS_DEFAULT_MODEL,
    )


@override_settings(EMBEDDINGS_SERVER_API_KEY="sk-server")
class TestRecordsUsageOnSuccess(TestCase):
    @patch("ask.helpers.embeddings.embedding")
    def test_creates_one_row_with_server_source(self, mock_embedding):
        mock_embedding.return_value = _build_litellm_response(prompt_tokens=42, total_tokens=42)

        user = UserFactory()
        page = PageFactory(creator=user)
        create_embedding("hello world", user=user, page=page, kind="index")

        rows = list(EmbeddingUsage.objects.all())
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row.user, user)
        self.assertEqual(row.page, page)
        self.assertEqual(row.kind, "index")
        self.assertEqual(row.key_source, "server")
        self.assertEqual(row.prompt_tokens, 42)
        self.assertEqual(row.total_tokens, 42)
        self.assertEqual(row.model, settings.ASK_EMBEDDINGS_DEFAULT_MODEL)
        self.assertGreater(row.cost_usd, Decimal("0"))

    @patch("ask.helpers.embeddings.embedding")
    def test_query_kind_recorded_with_null_page(self, mock_embedding):
        mock_embedding.return_value = _build_litellm_response()
        user = UserFactory()
        create_embedding("what is X?", user=user, kind="query")

        row = EmbeddingUsage.objects.get()
        self.assertEqual(row.kind, "query")
        self.assertIsNone(row.page)


@override_settings(EMBEDDINGS_SERVER_API_KEY="")
class TestRecordsUserSourceWhenFallback(TestCase):
    @patch("ask.helpers.embeddings.embedding")
    def test_user_keyed_call_attributed_to_user_source(self, mock_embedding):
        from ask.constants import AIProvider
        from users.models import AIProviderConfig

        mock_embedding.return_value = _build_litellm_response()
        user = UserFactory()
        AIProviderConfig.objects.create(
            user=user,
            provider=AIProvider.OPENAI.value,
            api_key="sk-user",
            is_enabled=True,
            is_validated=True,
        )
        create_embedding("data", user=user, kind="index")

        row = EmbeddingUsage.objects.get()
        self.assertEqual(row.key_source, "user")
        self.assertIsNone(row.org)

    @patch("ask.helpers.embeddings.embedding")
    def test_org_keyed_call_records_paying_org(self, mock_embedding):
        """When the resolver picks an org's shared AIProviderConfig, the audit
        row must point at that org so spend rolls up to the paying entity."""
        from ask.constants import AIProvider
        from users.models import AIProviderConfig
        from users.tests.factories import OrgFactory, OrgMemberFactory

        mock_embedding.return_value = _build_litellm_response()
        org = OrgFactory()
        user = UserFactory()
        OrgMemberFactory(org=org, user=user, role="member")
        AIProviderConfig.objects.create(
            org=org,
            provider=AIProvider.OPENAI.value,
            api_key="sk-org-openai",
            is_enabled=True,
            is_validated=True,
        )
        create_embedding("data", user=user, kind="index")

        row = EmbeddingUsage.objects.get()
        self.assertEqual(row.key_source, "user")
        self.assertEqual(row.org, org)

    @override_settings(EMBEDDINGS_SERVER_API_KEY="sk-server")
    @patch("ask.helpers.embeddings.embedding")
    def test_server_keyed_call_records_no_org_for_org_member(self, mock_embedding):
        """Regression guard: a member of an org that has a shared config must
        still record `org=None` when the server key wins precedence."""
        from ask.constants import AIProvider
        from users.models import AIProviderConfig
        from users.tests.factories import OrgFactory, OrgMemberFactory

        mock_embedding.return_value = _build_litellm_response()
        org = OrgFactory()
        user = UserFactory()
        OrgMemberFactory(org=org, user=user, role="member")
        AIProviderConfig.objects.create(
            org=org,
            provider=AIProvider.OPENAI.value,
            api_key="sk-org-openai",
            is_enabled=True,
            is_validated=True,
        )
        create_embedding("data", user=user, kind="index")

        row = EmbeddingUsage.objects.get()
        self.assertEqual(row.key_source, "server")
        self.assertIsNone(row.org)


class TestRecordingRobustness(TestCase):
    @patch("ask.helpers.embeddings.embedding")
    def test_no_row_when_response_shape_unrecognized(self, mock_embedding):
        """Defensive path: a response without a parseable `usage` shouldn't
        create a half-populated row. Existing tests using bare `Mock()` rely on
        this — they were written before usage attribution existed."""
        bare_mock = Mock()
        bare_mock.data = [{"embedding": [0.1] * 5}]
        mock_embedding.return_value = bare_mock

        create_embedding("data", api_key="sk-test")
        self.assertEqual(EmbeddingUsage.objects.count(), 0)

    @patch("ask.models.EmbeddingUsage")
    @patch("ask.helpers.embeddings.embedding")
    def test_recording_failure_does_not_break_embedding_return(self, mock_embedding, mock_usage_cls):
        """If the audit table is unreachable, the embedding pipeline must still
        return a usable vector — observability shouldn't take down the feature."""
        mock_embedding.return_value = _build_litellm_response()
        mock_usage_cls.return_value.save.side_effect = RuntimeError("DB unreachable")

        result = create_embedding("data", api_key="sk-test")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1536)

    @patch("ask.helpers.embeddings.log_error")
    @patch("ask.models.EmbeddingUsage")
    @patch("ask.helpers.embeddings.embedding")
    def test_recording_failure_logs_exception_type(self, mock_embedding, mock_usage_cls, mock_log_error):
        """Triage in production is much faster when the log line names the
        exception class — `RuntimeError` vs `IntegrityError` vs `OperationalError`
        all need different responses. The bare message alone doesn't tell you
        which one tripped."""
        mock_embedding.return_value = _build_litellm_response()
        mock_usage_cls.return_value.save.side_effect = RuntimeError("DB unreachable")

        create_embedding("data", api_key="sk-test")

        mock_log_error.assert_called_once()
        args, _ = mock_log_error.call_args
        self.assertIn("RuntimeError", args)


@override_settings(EMBEDDINGS_SERVER_API_KEY="sk-server")
class TestRecordingOnFailure(TestCase):
    @patch("ask.helpers.embeddings.embedding")
    def test_no_row_when_litellm_raises(self, mock_embedding):
        mock_embedding.side_effect = RuntimeError("API down")

        with self.assertRaises(RuntimeError):
            create_embedding("data", api_key="sk-test")

        self.assertEqual(EmbeddingUsage.objects.count(), 0)


class TestComputeEmbeddingCost(TestCase):
    """Unit-level coverage for the cost calculation helper. The wider test above
    just asserts cost > 0; this nails down the exact arithmetic so a future
    change to the per-million-token table is caught immediately."""

    def test_fallback_rate_for_text_embedding_3_small(self):
        # Force litellm.completion_cost to return 0 so the fallback path runs.
        with patch("litellm.completion_cost", return_value=0):
            cost = _compute_embedding_cost(
                response=_build_litellm_response(total_tokens=1_000_000),
                model="text-embedding-3-small",
                total_tokens=1_000_000,
            )
        self.assertEqual(cost, Decimal("0.02000000"))

    def test_fallback_returns_zero_for_unknown_model(self):
        with patch("litellm.completion_cost", return_value=0):
            cost = _compute_embedding_cost(
                response=_build_litellm_response(),
                model="some-unknown-model",
                total_tokens=1000,
            )
        self.assertEqual(cost, Decimal("0"))

    def test_fallback_quantizes_to_eight_places(self):
        """The cost_usd column has decimal_places=8 — small numbers must
        survive the quantize without losing precision or overflowing."""
        with patch("litellm.completion_cost", return_value=0):
            cost = _compute_embedding_cost(
                response=_build_litellm_response(total_tokens=100),
                model="text-embedding-3-small",
                total_tokens=100,
            )
        # 100 tokens at $0.02/1M = $0.000002 exactly. Stored as Decimal(8dp).
        self.assertEqual(cost, Decimal("0.00000200"))

    def test_known_models_have_positive_rates(self):
        """Sanity check that the model table isn't accidentally emptied."""
        self.assertIn("text-embedding-3-small", EMBEDDING_COST_PER_MILLION_TOKENS)
        for model, rate in EMBEDDING_COST_PER_MILLION_TOKENS.items():
            self.assertGreater(rate, Decimal("0"), f"{model} should have a positive rate")


@override_settings(EMBEDDINGS_SERVER_API_KEY="sk-server")
class TestUsageShapeTolerance(TestCase):
    """litellm's `response.usage` is a Pydantic object in some setups and a
    plain dict in others. The recording layer has to handle both; otherwise a
    litellm version bump can silently kill cost attribution."""

    @patch("ask.helpers.embeddings.embedding")
    def test_dict_shaped_usage(self, mock_embedding):
        mock_embedding.return_value = SimpleNamespace(
            data=[{"embedding": [0.0] * 1536}],
            usage={"prompt_tokens": 17, "total_tokens": 17},
            model="text-embedding-3-small",
        )

        create_embedding("data", api_key="sk-test")

        row = EmbeddingUsage.objects.get()
        self.assertEqual(row.prompt_tokens, 17)
        self.assertEqual(row.total_tokens, 17)

    @patch("ask.helpers.embeddings.embedding")
    def test_object_shaped_usage(self, mock_embedding):
        mock_embedding.return_value = SimpleNamespace(
            data=[{"embedding": [0.0] * 1536}],
            usage=SimpleNamespace(prompt_tokens=33, total_tokens=33),
            model="text-embedding-3-small",
        )

        create_embedding("data", api_key="sk-test")

        row = EmbeddingUsage.objects.get()
        self.assertEqual(row.prompt_tokens, 33)
        self.assertEqual(row.total_tokens, 33)

    @patch("ask.helpers.embeddings.embedding")
    def test_missing_usage_skips_recording(self, mock_embedding):
        """Some providers respond without a `usage` block at all. Better to
        skip the row than write zeros that look like real activity."""
        mock_embedding.return_value = SimpleNamespace(
            data=[{"embedding": [0.0] * 1536}],
            usage=None,
            model="text-embedding-3-small",
        )

        create_embedding("data", api_key="sk-test")
        self.assertEqual(EmbeddingUsage.objects.count(), 0)


class TestExtractUsageTokensDirect(TestCase):
    """Direct unit coverage for the shape-tolerance branch in
    `_extract_usage_tokens`. This includes the `isinstance(response, dict)`
    branch — which `create_embedding` itself can't currently exercise (it
    does `response.data[0]` and would crash on a plain dict), but the helper
    still handles it defensively. Tested directly so the branch isn't dead
    code that silently drifts."""

    def test_object_response_with_object_usage(self):
        response = SimpleNamespace(usage=SimpleNamespace(prompt_tokens=7, total_tokens=7))
        self.assertEqual(_extract_usage_tokens(response), (7, 7))

    def test_object_response_with_dict_usage(self):
        response = SimpleNamespace(usage={"prompt_tokens": 9, "total_tokens": 9})
        self.assertEqual(_extract_usage_tokens(response), (9, 9))

    def test_dict_response_with_nested_usage(self):
        """If a future proxy/mock path ever hands us a plain dict response,
        the helper still finds the usage block."""
        response = {"data": [{"embedding": []}], "usage": {"prompt_tokens": 4, "total_tokens": 4}}
        self.assertEqual(_extract_usage_tokens(response), (4, 4))

    def test_dict_response_without_usage(self):
        response = {"data": [{"embedding": []}]}
        self.assertEqual(_extract_usage_tokens(response), (None, None))

    def test_non_int_token_values_rejected(self):
        """Defensive: a malformed usage dict where tokens come back as None,
        strings, or Mocks shouldn't produce a row with garbage values."""
        response = SimpleNamespace(usage={"prompt_tokens": None, "total_tokens": "10"})
        self.assertEqual(_extract_usage_tokens(response), (None, None))


@override_settings(EMBEDDINGS_SERVER_API_KEY="sk-server")
class TestCollectEmbeddingUsageBuffer(TestCase):
    """The buffering context manager defers per-call INSERTs so a bulk caller
    can amortize them into a single `bulk_create`."""

    @patch("ask.helpers.embeddings.embedding")
    def test_calls_inside_context_do_not_insert(self, mock_embedding):
        mock_embedding.return_value = _build_litellm_response()

        with collect_embedding_usage() as buffer:
            create_embedding("a", api_key="sk-test")
            create_embedding("b", api_key="sk-test")
            self.assertEqual(EmbeddingUsage.objects.count(), 0)
            self.assertEqual(len(buffer), 2)
            for row in buffer:
                self.assertIsNone(row.pk)

    @patch("ask.helpers.embeddings.embedding")
    def test_buffer_resets_after_context(self, mock_embedding):
        """Default per-call insertion must resume after the context exits."""
        mock_embedding.return_value = _build_litellm_response()

        with collect_embedding_usage():
            create_embedding("inside", api_key="sk-test")
            self.assertEqual(EmbeddingUsage.objects.count(), 0)

        create_embedding("outside", api_key="sk-test")
        self.assertEqual(EmbeddingUsage.objects.count(), 1)

    @patch("ask.helpers.embeddings.embedding")
    def test_buffer_resets_on_exception(self, mock_embedding):
        """The contextvar must be reset even when the block raises, otherwise
        a stray exception would silently disable per-call inserts for the
        rest of the worker process."""
        mock_embedding.return_value = _build_litellm_response()

        with self.assertRaises(RuntimeError):
            with collect_embedding_usage():
                create_embedding("inside", api_key="sk-test")
                raise RuntimeError("boom")

        create_embedding("outside", api_key="sk-test")
        self.assertEqual(EmbeddingUsage.objects.count(), 1)

    @patch("ask.helpers.embeddings.embedding")
    def test_buffer_flushable_via_bulk_create(self, mock_embedding):
        mock_embedding.return_value = _build_litellm_response(prompt_tokens=5, total_tokens=5)

        with collect_embedding_usage() as buffer:
            for _ in range(3):
                create_embedding("data", api_key="sk-test")
            EmbeddingUsage.objects.bulk_create(buffer)

        rows = list(EmbeddingUsage.objects.all())
        self.assertEqual(len(rows), 3)
        for row in rows:
            self.assertEqual(row.total_tokens, 5)
            self.assertIsNotNone(row.created)
