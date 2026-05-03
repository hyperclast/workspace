from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from ask.constants import AIProvider
from ask.models import AskRequest
from users.models import AIProviderConfig
from users.tests.factories import OrgFactory, UserFactory


class DedupeReassignsAskRequestsTests(TestCase):
    """B1: AskRequest.ai_config references on dropped rows must be reassigned to the keeper.

    AskRequest.ai_config is on_delete=SET_NULL, so a naive .delete() of duplicate configs
    would silently null those references and erase usage history from the analytics
    endpoints (GET /api/v1/users/me/ai/usage/ filters by ai_config_id__in=...).
    """

    def test_drops_are_reassigned_not_nulled(self):
        user = UserFactory()
        keeper = AIProviderConfig.objects.create(
            user=user,
            provider=AIProvider.OPENAI.value,
            api_key="sk-shared",
            is_validated=True,
        )
        dup = AIProviderConfig.objects.create(
            user=user,
            provider=AIProvider.OPENAI.value,
            api_key="sk-shared",
            is_validated=False,
        )

        keeper_request = AskRequest.objects.create(user=user, ai_config=keeper, query="q1")
        dup_request = AskRequest.objects.create(user=user, ai_config=dup, query="q2")

        out = StringIO()
        call_command("dedupe_ai_provider_configs", stdout=out)

        self.assertFalse(AIProviderConfig.objects.filter(pk=dup.pk).exists())
        self.assertTrue(AIProviderConfig.objects.filter(pk=keeper.pk).exists())

        keeper_request.refresh_from_db()
        dup_request.refresh_from_db()
        self.assertEqual(keeper_request.ai_config_id, keeper.pk)
        self.assertEqual(dup_request.ai_config_id, keeper.pk)

        output = out.getvalue()
        self.assertIn("Reassigned 1 AskRequest row(s)", output)
        # Bucket label includes (scope_id, provider) so the per-group line is
        # unambiguous, and provider= isn't duplicated by an extra inline tag.
        self.assertIn(f"user_id={user.id} provider={AIProvider.OPENAI.value}", output)
        self.assertEqual(output.count(f"provider={AIProvider.OPENAI.value}"), 1)

    def test_dry_run_reports_duplicates_without_deleting(self):
        user = UserFactory()
        keeper = AIProviderConfig.objects.create(
            user=user,
            provider=AIProvider.OPENAI.value,
            api_key="sk-shared",
            is_validated=True,
        )
        dup = AIProviderConfig.objects.create(
            user=user,
            provider=AIProvider.OPENAI.value,
            api_key="sk-shared",
            is_validated=False,
        )
        dup_request = AskRequest.objects.create(user=user, ai_config=dup, query="q")

        out = StringIO()
        call_command("dedupe_ai_provider_configs", "--dry-run", stdout=out)

        self.assertTrue(AIProviderConfig.objects.filter(pk=dup.pk).exists())
        dup_request.refresh_from_db()
        self.assertEqual(dup_request.ai_config_id, dup.pk)

        output = out.getvalue()
        self.assertNotIn("Reassigned", output)
        # Dry-run still reports the offending pair so the operator can review.
        self.assertIn(f"keeping pk={keeper.pk}", output)
        self.assertIn(str(dup.pk), output)
        self.assertIn("Would delete 1 duplicate row(s) across 1 group(s)", output)


class DedupePropagatesDefaultTests(TestCase):
    """B7: keeper inherits is_default if any duplicate in the group had it.

    Sort priority is is_validated > is_default > -modified. A
    (is_validated=True, is_default=False) row beats a (is_validated=False,
    is_default=True) row, so without explicit propagation deleting the loser
    leaves the user with no default key.
    """

    def test_promotes_keeper_when_only_default_is_dropped(self):
        user = UserFactory()
        keeper = AIProviderConfig.objects.create(
            user=user,
            provider=AIProvider.OPENAI.value,
            api_key="sk-shared",
            is_validated=True,
        )
        # Auto-promotion makes keeper the default on first save; a second
        # is_default=True save below clears it again, which is the broken
        # historical state we are simulating.
        keeper.refresh_from_db()
        self.assertTrue(keeper.is_default)

        dup = AIProviderConfig.objects.create(
            user=user,
            provider=AIProvider.OPENAI.value,
            api_key="sk-shared",
            is_validated=False,
            is_default=True,
        )
        keeper.refresh_from_db()
        dup.refresh_from_db()
        self.assertFalse(keeper.is_default)
        self.assertTrue(dup.is_default)

        out = StringIO()
        call_command("dedupe_ai_provider_configs", stdout=out)

        self.assertFalse(AIProviderConfig.objects.filter(pk=dup.pk).exists())
        keeper.refresh_from_db()
        self.assertTrue(keeper.is_default)
        self.assertIn("Promoted 1 keeper(s) to default.", out.getvalue())

    def test_does_not_promote_when_no_drop_was_default(self):
        user = UserFactory()
        keeper = AIProviderConfig.objects.create(
            user=user,
            provider=AIProvider.OPENAI.value,
            api_key="sk-shared",
            is_validated=True,
            is_enabled=False,  # avoids auto-promotion to default
        )
        AIProviderConfig.objects.create(
            user=user,
            provider=AIProvider.OPENAI.value,
            api_key="sk-shared",
            is_validated=False,
            is_enabled=False,
        )
        keeper.refresh_from_db()
        self.assertFalse(keeper.is_default)

        out = StringIO()
        call_command("dedupe_ai_provider_configs", stdout=out)

        keeper.refresh_from_db()
        self.assertFalse(keeper.is_default)
        self.assertIn("Promoted 0 keeper(s) to default.", out.getvalue())


class DedupeRespectsApiBaseUrlTests(TestCase):
    """B3: identity is (scope, provider, api_key, api_base_url) — same key against
    distinct base URLs is a different service and must not be merged.
    """

    def test_custom_provider_same_key_different_base_url_not_merged(self):
        user = UserFactory()
        a = AIProviderConfig.objects.create(
            user=user,
            provider=AIProvider.CUSTOM.value,
            api_key="sk-shared",
            api_base_url="https://api.together.xyz/v1",
            is_validated=True,
        )
        b = AIProviderConfig.objects.create(
            user=user,
            provider=AIProvider.CUSTOM.value,
            api_key="sk-shared",
            api_base_url="https://my-self-hosted.example.com/v1",
            is_validated=True,
        )

        out = StringIO()
        call_command("dedupe_ai_provider_configs", stdout=out)

        self.assertTrue(AIProviderConfig.objects.filter(pk=a.pk).exists())
        self.assertTrue(AIProviderConfig.objects.filter(pk=b.pk).exists())
        self.assertIn("Deleted 0 duplicate row(s) across 0 group(s)", out.getvalue())

    def test_custom_provider_same_key_same_base_url_merged(self):
        user = UserFactory()
        keeper = AIProviderConfig.objects.create(
            user=user,
            provider=AIProvider.CUSTOM.value,
            api_key="sk-shared",
            api_base_url="https://api.together.xyz/v1",
            is_validated=True,
        )
        dup = AIProviderConfig.objects.create(
            user=user,
            provider=AIProvider.CUSTOM.value,
            api_key="sk-shared",
            api_base_url="https://api.together.xyz/v1",
            is_validated=False,
        )

        out = StringIO()
        call_command("dedupe_ai_provider_configs", stdout=out)

        self.assertTrue(AIProviderConfig.objects.filter(pk=keeper.pk).exists())
        self.assertFalse(AIProviderConfig.objects.filter(pk=dup.pk).exists())
        self.assertIn("Deleted 1 duplicate row(s) across 1 group(s)", out.getvalue())


class DedupeKeeperSelectionTests(TestCase):
    """Sort priority is is_validated > is_default > -modified.

    is_enabled=False on every row keeps the model's auto-promotion logic
    (which would otherwise set is_default=True) out of the picture so each
    test isolates a single rung of the sort key.
    """

    def test_keeps_validated_drops_unvalidated(self):
        user = UserFactory()
        unvalidated = AIProviderConfig.objects.create(
            user=user,
            provider=AIProvider.OPENAI.value,
            api_key="sk-shared",
            is_validated=False,
            is_enabled=False,
        )
        validated = AIProviderConfig.objects.create(
            user=user,
            provider=AIProvider.OPENAI.value,
            api_key="sk-shared",
            is_validated=True,
            is_enabled=False,
        )

        call_command("dedupe_ai_provider_configs", stdout=StringIO())

        self.assertTrue(AIProviderConfig.objects.filter(pk=validated.pk).exists())
        self.assertFalse(AIProviderConfig.objects.filter(pk=unvalidated.pk).exists())

    def test_tie_break_keeps_most_recently_modified(self):
        user = UserFactory()
        older = AIProviderConfig.objects.create(
            user=user,
            provider=AIProvider.OPENAI.value,
            api_key="sk-shared",
            is_validated=True,
            is_enabled=False,
        )
        newer = AIProviderConfig.objects.create(
            user=user,
            provider=AIProvider.OPENAI.value,
            api_key="sk-shared",
            is_validated=True,
            is_enabled=False,
        )
        # Force deterministic timestamps; back-to-back creates can otherwise tie.
        now = timezone.now()
        AIProviderConfig.objects.filter(pk=older.pk).update(modified=now - timedelta(hours=1))
        AIProviderConfig.objects.filter(pk=newer.pk).update(modified=now)

        call_command("dedupe_ai_provider_configs", stdout=StringIO())

        self.assertTrue(AIProviderConfig.objects.filter(pk=newer.pk).exists())
        self.assertFalse(AIProviderConfig.objects.filter(pk=older.pk).exists())


class DedupeScopeIsolationTests(TestCase):
    """A user-scope row and an org-scope row sharing provider+key are different
    services and must never be merged. _iter_scope_buckets yields user_id and
    org_id buckets independently, so they never appear in the same group.
    """

    def test_user_scope_does_not_merge_with_org_scope(self):
        user = UserFactory()
        org = OrgFactory()
        user_row = AIProviderConfig.objects.create(
            user=user,
            provider=AIProvider.OPENAI.value,
            api_key="sk-shared",
            is_validated=True,
        )
        org_row = AIProviderConfig.objects.create(
            org=org,
            provider=AIProvider.OPENAI.value,
            api_key="sk-shared",
            is_validated=True,
        )

        out = StringIO()
        call_command("dedupe_ai_provider_configs", stdout=out)

        self.assertTrue(AIProviderConfig.objects.filter(pk=user_row.pk).exists())
        self.assertTrue(AIProviderConfig.objects.filter(pk=org_row.pk).exists())
        self.assertIn("Deleted 0 duplicate row(s) across 0 group(s)", out.getvalue())


class DedupeEmptyApiKeyTests(TestCase):
    """An empty api_key has no useful identity to dedupe on, so two rows with
    api_key="" must not be collapsed into one even when scope+provider match.
    """

    def test_empty_api_key_rows_are_not_merged(self):
        user = UserFactory()
        a = AIProviderConfig.objects.create(
            user=user,
            provider=AIProvider.OPENAI.value,
            api_key="",
        )
        b = AIProviderConfig.objects.create(
            user=user,
            provider=AIProvider.OPENAI.value,
            api_key="",
        )

        out = StringIO()
        call_command("dedupe_ai_provider_configs", stdout=out)

        self.assertTrue(AIProviderConfig.objects.filter(pk=a.pk).exists())
        self.assertTrue(AIProviderConfig.objects.filter(pk=b.pk).exists())
        self.assertIn("Deleted 0 duplicate row(s) across 0 group(s)", out.getvalue())
