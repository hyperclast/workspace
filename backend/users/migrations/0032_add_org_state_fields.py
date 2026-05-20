"""Introduce the org-scoped user state used by the "open page is the
current org" architecture:

- `Profile.current_org`: a fallback for non-page routes (settings, the
  homepage redirect). Page routes derive `currentOrgId` from the open
  page's project instead.
- `Profile.org_state`: per-org state keyed by org `external_id`. Shape:
    {
      "<orgExternalId>": {
        "last_page_id":          "<page external_id>" | None,
        "daily_note_project_id": "<project external_id>" | None,
        "daily_note_template_id":"<page external_id>" | None,
      },
      ...
    }
  External-id strings (not FKs) so a soft-deleted project/page leaves a
  harmless stale string in JSON rather than requiring eager cleanup.

This migration also backfills `org_state` from the pre-branch
`Profile.daily_note_project` / `Profile.daily_note_template` FK pair
(added in 0031) so existing daily-note configurations survive the move
to per-org state. The old FK fields are dropped by 0033.
"""

import django.db.models.deletion
from django.db import migrations, models


def backfill_org_state_from_daily_note_fields(apps, schema_editor):
    """Move each Profile's daily-note pair into `org_state` keyed by the
    project's org. Pre-branch the daily-note pair lived directly on
    Profile (one pair per user, not per-org); we promote it to the
    per-org shape by reading the project's org.
    """
    Profile = apps.get_model("users", "Profile")

    profiles = Profile.objects.exclude(daily_note_project__isnull=True).select_related(
        "daily_note_project__org", "daily_note_template"
    )
    for profile in profiles.iterator():
        project = profile.daily_note_project
        if project is None or project.org is None:
            continue
        template = profile.daily_note_template
        template_in_project = template is not None and template.project_id == project.id
        org_state = dict(profile.org_state or {})
        bucket = dict(org_state.get(project.org.external_id, {}))
        bucket["daily_note_project_id"] = project.external_id
        bucket["daily_note_template_id"] = template.external_id if template_in_project else None
        bucket.setdefault("last_page_id", None)
        org_state[project.org.external_id] = bucket
        profile.org_state = org_state
        profile.save(update_fields=["org_state", "modified"])


def reverse_clear_org_state(apps, schema_editor):
    """Reverse: clear `org_state`. The pre-branch shape stored daily-note
    data on FKs which the next migration (0033) re-adds on reverse —
    they re-populate from the JSON we're about to clear, so order
    matters: this RunPython runs AFTER 0033's reverse (which re-adds
    the FKs) has placed the FKs back. The reverse just zeroes the JSON.
    """
    Profile = apps.get_model("users", "Profile")
    Profile.objects.exclude(org_state={}).update(org_state={})


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0031_add_daily_note_prefs"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="current_org",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="users.org",
            ),
        ),
        migrations.AddField(
            model_name="profile",
            name="org_state",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.RunPython(
            backfill_org_state_from_daily_note_fields,
            reverse_clear_org_state,
        ),
    ]
