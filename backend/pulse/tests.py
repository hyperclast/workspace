import json
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from ask.models import EmbeddingUsage
from users.tests.factories import TEST_USER_PASSWORD, UserFactory


def _make_usage(*, user=None, created=None, key_source="server", cost="0.001", tokens=100, kind="index"):
    """Create an EmbeddingUsage row with the given timestamp.

    `created` is auto-managed by Django (auto_now_add=True), so we override
    with an explicit UPDATE after creation rather than passing it to .create().
    """
    row = EmbeddingUsage.objects.create(
        user=user,
        model="text-embedding-3-small",
        prompt_tokens=tokens,
        total_tokens=tokens,
        cost_usd=Decimal(cost),
        kind=kind,
        key_source=key_source,
    )
    if created is not None:
        EmbeddingUsage.objects.filter(pk=row.pk).update(created=created)
    return row


class TestPulseDashboardEmbeddingSpend(TestCase):
    """The /pulse dashboard surfaces server-keyed embedding spend so admins
    can see what the hosted product is paying for embeddings."""

    def setUp(self):
        self.admin = UserFactory(is_staff=True, is_superuser=True)
        self.client.login(username=self.admin.username, password=TEST_USER_PASSWORD)
        self.url = reverse("pulse:dashboard")

    def test_empty_state_renders_when_no_usage(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        ctx = response.context
        self.assertEqual(ctx["emb_lifetime"]["cost"], Decimal("0"))
        self.assertEqual(ctx["emb_lifetime"]["calls"], 0)
        self.assertEqual(ctx["emb_30d"]["calls"], 0)
        self.assertEqual(ctx["emb_7d"]["calls"], 0)
        self.assertEqual(list(ctx["emb_top_users"]), [])

    def test_lifetime_30d_7d_aggregations(self):
        u = UserFactory()
        now = timezone.now()
        _make_usage(user=u, created=now - timedelta(days=2), cost="0.10", tokens=100)
        _make_usage(user=u, created=now - timedelta(days=10), cost="0.30", tokens=300)
        _make_usage(user=u, created=now - timedelta(days=45), cost="0.50", tokens=500)

        response = self.client.get(self.url)
        ctx = response.context

        # Lifetime spans everything.
        self.assertEqual(ctx["emb_lifetime"]["cost"], Decimal("0.90"))
        self.assertEqual(ctx["emb_lifetime"]["tokens"], 900)
        self.assertEqual(ctx["emb_lifetime"]["calls"], 3)
        # 30d window includes the 2d and 10d rows, excludes the 45d row.
        self.assertEqual(ctx["emb_30d"]["cost"], Decimal("0.40"))
        self.assertEqual(ctx["emb_30d"]["calls"], 2)
        # 7d window includes only the 2d row.
        self.assertEqual(ctx["emb_7d"]["cost"], Decimal("0.10"))
        self.assertEqual(ctx["emb_7d"]["calls"], 1)

    def test_user_keyed_rows_excluded_from_server_spend(self):
        """User-source rows represent self-hosters paying their own OpenAI bill;
        they appear in the user-keyed counter, never in server spend."""
        user_a = UserFactory()
        now = timezone.now()
        _make_usage(user=user_a, created=now - timedelta(days=1), key_source="server", cost="0.20")
        _make_usage(user=user_a, created=now - timedelta(days=1), key_source="user", cost="9.99")

        response = self.client.get(self.url)
        ctx = response.context

        self.assertEqual(ctx["emb_lifetime"]["cost"], Decimal("0.20"))
        self.assertEqual(ctx["emb_user_keyed_calls_30d"], 1)

    def test_top_users_sorted_by_lifetime_server_cost(self):
        heavy_user = UserFactory()
        light_user = UserFactory()
        now = timezone.now()
        _make_usage(user=heavy_user, created=now - timedelta(days=1), cost="0.50")
        _make_usage(user=heavy_user, created=now - timedelta(days=2), cost="0.30")
        _make_usage(user=light_user, created=now - timedelta(days=1), cost="0.05")

        response = self.client.get(self.url)
        top = list(response.context["emb_top_users"])

        self.assertEqual(len(top), 2)
        self.assertEqual(top[0]["user_id"], heavy_user.id)
        self.assertEqual(top[0]["total_cost"], Decimal("0.80"))
        self.assertEqual(top[0]["total_calls"], 2)
        self.assertEqual(top[1]["user_id"], light_user.id)
        self.assertEqual(top[1]["total_cost"], Decimal("0.05"))

    def test_top_users_excludes_orphaned_rows(self):
        """A row whose user was deleted (SET_NULL) shouldn't appear in the
        per-user table — it has no email/username to display."""
        now = timezone.now()
        _make_usage(user=None, created=now - timedelta(days=1), cost="0.99")

        response = self.client.get(self.url)
        self.assertEqual(list(response.context["emb_top_users"]), [])
        # But lifetime aggregate still counts it (it's still real spend).
        self.assertEqual(response.context["emb_lifetime"]["cost"], Decimal("0.99"))

    def test_non_superuser_forbidden(self):
        plain_user = UserFactory()
        self.client.login(username=plain_user.username, password=TEST_USER_PASSWORD)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_explicit_source_excluded_from_server_spend(self):
        """Rows from scripts/tests with `key_source=explicit` are real spend
        but not on the Hyperclast-paid path. They must not inflate the headline
        cards or the top-users table."""
        user = UserFactory()
        now = timezone.now()
        _make_usage(user=user, created=now - timedelta(days=1), key_source="server", cost="0.10")
        _make_usage(user=user, created=now - timedelta(days=1), key_source="explicit", cost="50.00")

        response = self.client.get(self.url)
        ctx = response.context

        # Server spend reflects only the server row, not the explicit-keyed one.
        self.assertEqual(ctx["emb_lifetime"]["cost"], Decimal("0.10"))
        self.assertEqual(ctx["emb_lifetime"]["calls"], 1)
        # The chart and top-users views derive from the same queryset.
        chart_rows = json.loads(ctx["emb_daily_data_json"])
        self.assertEqual(sum(r["cost"] for r in chart_rows), 0.10)

    def test_user_cost_aggregates_multiple_calls(self):
        """A heavy user with many small calls should appear with the sum across
        all of them — not just the latest. Regression guard for grouping."""
        user = UserFactory()
        now = timezone.now()
        for delta in range(1, 6):
            _make_usage(user=user, created=now - timedelta(days=delta), cost="0.10", tokens=100)

        response = self.client.get(self.url)
        top = list(response.context["emb_top_users"])

        self.assertEqual(len(top), 1)
        self.assertEqual(top[0]["total_calls"], 5)
        self.assertEqual(top[0]["total_tokens"], 500)
        self.assertEqual(top[0]["total_cost"], Decimal("0.50"))

    def test_daily_chart_data_has_one_row_per_active_day(self):
        """The bar chart consumes `emb_daily_data_json`. Verify shape: one row
        per day with `cost` and `calls`, sorted ascending — so the chart axis
        renders left-to-right by date."""
        user = UserFactory()
        now = timezone.now()
        _make_usage(user=user, created=now - timedelta(days=1), cost="0.20", tokens=50)
        _make_usage(user=user, created=now - timedelta(days=1), cost="0.30", tokens=50)  # same day
        _make_usage(user=user, created=now - timedelta(days=5), cost="0.10", tokens=50)

        response = self.client.get(self.url)
        rows = json.loads(response.context["emb_daily_data_json"])

        self.assertEqual(len(rows), 2)
        # Ascending order by date.
        self.assertLess(rows[0]["date"], rows[1]["date"])
        # Same-day rows are aggregated.
        recent = rows[1]
        self.assertEqual(recent["calls"], 2)
        self.assertAlmostEqual(recent["cost"], 0.50, places=6)

    def test_emb_server_key_configured_flag_reflects_setting(self):
        """The template uses this to decide whether to show the 'not set'
        warning. Wired from settings, so guarding against it being dropped."""
        with override_settings(EMBEDDINGS_SERVER_API_KEY=""):
            response = self.client.get(self.url)
            self.assertFalse(response.context["emb_server_key_configured"])

        with override_settings(EMBEDDINGS_SERVER_API_KEY="sk-server"):
            response = self.client.get(self.url)
            self.assertTrue(response.context["emb_server_key_configured"])
