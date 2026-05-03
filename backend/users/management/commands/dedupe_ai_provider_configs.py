"""
Deduplicate AIProviderConfig rows that share the same (scope, provider, api_key, api_base_url).

Historical bug: POST /api/v1/users/me/ai/providers/ (and the org variant) inserted
a fresh row on every save. Users who hit "Save" multiple times — e.g., when
validation transiently failed — accumulated duplicate rows for the same key.

Within each (user|org, provider, api_key, api_base_url) group, this command keeps
the "best" row and deletes the rest. Best is defined as:
    1. is_validated=True wins over False
    2. is_default=True wins over False
    3. Most recently modified wins

api_base_url is part of the identity so custom providers that share an api_key
across distinct endpoints (e.g., a self-hosted URL and a hosted aggregator) are
treated as separate services and never merged. Built-in providers store
api_base_url="" and are unaffected.

api_key is an EncryptedTextField with non-deterministic ciphertext, so grouping
happens in Python after decryption (one query per (scope, provider) bucket).

AskRequest rows that pointed at a dropped config are reassigned to the keeper
before delete so analytics/usage history is preserved (AskRequest.ai_config is
on_delete=SET_NULL, which would otherwise silently drop those references).

If any row in the group has is_default=True but the keeper does not (the sort
priority puts is_validated ahead of is_default), the keeper is promoted to
default before the duplicates are deleted. Otherwise the user could be left
with no default key when the only is_default row was unvalidated.

Usage:
    python manage.py dedupe_ai_provider_configs --dry-run
    python manage.py dedupe_ai_provider_configs
"""

from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction

from ask.models import AskRequest
from users.models import AIProviderConfig


class Command(BaseCommand):
    help = "Delete duplicate AIProviderConfig rows that share the same " "(scope, provider, api_key, api_base_url)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be deleted without making changes",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        total_deleted = 0
        total_groups = 0
        total_reassigned = 0
        total_promoted = 0

        for scope_kwargs, label in self._iter_scope_buckets():
            rows = list(AIProviderConfig.objects.filter(**scope_kwargs))
            by_key = defaultdict(list)
            for row in rows:
                if not row.api_key:
                    continue
                by_key[(row.api_key, row.api_base_url or "")].append(row)

            for (api_key, api_base_url), group in by_key.items():
                if len(group) < 2:
                    continue

                total_groups += 1
                group.sort(
                    key=lambda r: (
                        not r.is_validated,
                        not r.is_default,
                        -r.modified.timestamp(),
                    )
                )
                keep = group[0]
                drop = group[1:]
                drop_pks = [r.pk for r in drop]
                hint = keep.get_key_hint() or "<empty>"

                self.stdout.write(
                    f"{label} key={hint}: keeping pk={keep.pk} "
                    f"(validated={keep.is_validated}, default={keep.is_default}); "
                    f"deleting {len(drop)} dup pk(s) {drop_pks}"
                )

                promote_keeper = not keep.is_default and any(r.is_default for r in drop)

                if not dry_run:
                    with transaction.atomic():
                        reassigned = AskRequest.objects.filter(ai_config_id__in=drop_pks).update(ai_config=keep)
                        if promote_keeper:
                            keep.is_default = True
                            keep.save(update_fields=["is_default", "modified"])
                        AIProviderConfig.objects.filter(pk__in=drop_pks).delete()
                    total_reassigned += reassigned
                if promote_keeper:
                    total_promoted += 1
                total_deleted += len(drop)

        verb = "Would delete" if dry_run else "Deleted"
        summary = f"{verb} {total_deleted} duplicate row(s) across {total_groups} group(s)."
        if not dry_run:
            summary += f" Reassigned {total_reassigned} AskRequest row(s) to keepers."
        promote_verb = "Would promote" if dry_run else "Promoted"
        summary += f" {promote_verb} {total_promoted} keeper(s) to default."
        self.stdout.write(self.style.SUCCESS(summary))

    def _iter_scope_buckets(self):
        """Yield (queryset_kwargs, label) for each (scope, provider) bucket.

        The label includes both scope id and provider so the per-group log line
        unambiguously identifies which (scope, provider) bucket is being reported.
        """
        user_buckets = (
            AIProviderConfig.objects.filter(user__isnull=False)
            .values_list("user_id", "provider")
            .order_by("user_id", "provider")
            .distinct()
        )
        for user_id, provider in user_buckets:
            yield (
                {"user_id": user_id, "provider": provider},
                f"user_id={user_id} provider={provider}",
            )

        org_buckets = (
            AIProviderConfig.objects.filter(org__isnull=False)
            .values_list("org_id", "provider")
            .order_by("org_id", "provider")
            .distinct()
        )
        for org_id, provider in org_buckets:
            yield (
                {"org_id": org_id, "provider": provider},
                f"org_id={org_id} provider={provider}",
            )
