"""Drop the pre-branch `Profile.daily_note_project` / `Profile.daily_note_template`
FK pair. 0032 backfilled the data into `Profile.org_state`.

The reverse path is non-trivial. Django's auto-generated reverse of the
two `RemoveField` operations re-adds the FK columns but leaves them
empty — so an operator running `manage.py migrate users 0031` would
silently lose every user's daily-note configuration. To prevent that
data loss, this migration includes a `RunPython` whose `reverse_code`
re-populates the FK columns from `org_state` after Django has put the
columns back. Order matters:

    operations = [RunPython, RemoveField, RemoveField]

Operations are unapplied in reverse order, so on `migrate users 0031`
Django first re-adds the two FK columns (reverse of `RemoveField`),
then runs `repopulate_daily_note_fks_from_org_state` to populate them.
0032's own reverse (`reverse_clear_org_state`) runs last and zeroes
the JSON — by which point the FKs are already restored.
"""

from django.db import migrations


def _repopulate_daily_note_fks_from_org_state(apps, schema_editor):
    """Reverse of the FK drop: best-effort restore each Profile's
    daily-note FK pair from `Profile.org_state`.

    Pre-branch the daily-note pair lived directly on Profile — one pair
    per user. After 0032 the data is per-org in
    `org_state[<orgExternalId>]`; there's no canonical per-user pair to
    recover, so pick the first bucket (sorted by org `external_id` for
    deterministic recovery) that names a project. The pre-branch UI
    only ever set one pair per user, so for the overwhelming common
    case (one bucket) this is exact; for users who configured
    daily-notes in multiple workspaces post-0032, only the lexically
    first org's pair survives the rollback — acceptable for a manual
    rollback path that's only ever exercised by ops in emergencies.

    Any project / template that's been hard-deleted since 0032 leaves
    the corresponding FK NULL, matching the shape Django's
    auto-generated reverse would have produced.
    """
    Profile = apps.get_model("users", "Profile")
    Project = apps.get_model("pages", "Project")
    Page = apps.get_model("pages", "Page")

    for profile in Profile.objects.exclude(org_state={}).iterator():
        buckets = profile.org_state or {}
        chosen_project_external_id = None
        chosen_template_external_id = None
        for org_external_id in sorted(buckets):
            bucket = buckets[org_external_id]
            if not isinstance(bucket, dict):
                continue
            project_external_id = bucket.get("daily_note_project_id")
            if project_external_id:
                chosen_project_external_id = project_external_id
                chosen_template_external_id = bucket.get("daily_note_template_id")
                break

        if chosen_project_external_id is None:
            continue

        project = Project.objects.filter(external_id=chosen_project_external_id).first()
        if project is None:
            continue
        template = None
        if chosen_template_external_id:
            template = Page.objects.filter(external_id=chosen_template_external_id, project=project).first()
        profile.daily_note_project = project
        profile.daily_note_template = template
        profile.save(update_fields=["daily_note_project", "daily_note_template", "modified"])


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0032_add_org_state_fields"),
        # Required by the reverse `RunPython` below:
        # `_repopulate_daily_note_fks_from_org_state` calls
        # `apps.get_model("pages", "Project")` and
        # `apps.get_model("pages", "Page")`, which only works if the
        # historical apps registry has the `pages` app at a state
        # where those models exist. Pinning to a concrete `pages`
        # migration also keeps the migration graph deterministic
        # across re-runs. `0029_commentreaction` is the pages-head as
        # of this migration's authoring — any pages migration that
        # has both models with their `external_id` field would do.
        ("pages", "0029_commentreaction"),
    ]

    operations = [
        # Forward: noop — data was already moved to `org_state` in 0032.
        # Reverse: re-populates the FKs from `org_state`. Sits FIRST in
        # the list so that on reverse (operations are unapplied in
        # reverse order) the FK columns have already been re-added by
        # the reversed `RemoveField`s below before this RunPython fires.
        migrations.RunPython(
            migrations.RunPython.noop,
            _repopulate_daily_note_fks_from_org_state,
        ),
        migrations.RemoveField(
            model_name="profile",
            name="daily_note_project",
        ),
        migrations.RemoveField(
            model_name="profile",
            name="daily_note_template",
        ),
    ]
