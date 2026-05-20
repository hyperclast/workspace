"""Round-trip test for `users.0033_drop_profile_daily_note_fields`.

The forward path drops the pre-branch `Profile.daily_note_project` /
`daily_note_template` FK pair (data was moved into `Profile.org_state`
by 0032). The reverse path repopulates those FKs from `org_state`
before 0032's reverse clears the JSON. Without that repopulation, an
operator running `manage.py migrate users 0031` would silently wipe
every user's daily-note configuration — which is exactly the kind of
quiet data-loss path that's easy to ship and hard to recover from.

This test seeds a populated `org_state` bucket, reverses 0033, and
asserts the FKs come back filled in.
"""

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


HEAD_TARGET = [("users", "0033_drop_profile_daily_note_fields")]
PRE_BACKFILL_TARGET = [("users", "0031_add_daily_note_prefs")]


class TestRollbackRepopulatesDailyNoteFKs(TransactionTestCase):
    """`TransactionTestCase` because `MigrationExecutor.migrate` commits
    DDL — a `TestCase`'s wrapping transaction would hide the schema
    swap from the helper queries inside the reverse `RunPython`.

    `setUp` / `tearDown` re-apply HEAD so the test leaves the DB at the
    same migration state the rest of the suite expects, regardless of
    where mid-test assertions fail.
    """

    def setUp(self):
        MigrationExecutor(connection).migrate(HEAD_TARGET)

    def tearDown(self):
        MigrationExecutor(connection).migrate(HEAD_TARGET)

    def test_reverse_restores_daily_note_fks_from_org_state(self):
        # --- Phase 1: seed at HEAD via historical models. -----------
        head_apps = MigrationExecutor(connection).loader.project_state(HEAD_TARGET).apps
        User = head_apps.get_model("users", "User")
        Profile = head_apps.get_model("users", "Profile")
        Org = head_apps.get_model("users", "Org")
        Project = head_apps.get_model("pages", "Project")
        Page = head_apps.get_model("pages", "Page")

        user = User.objects.create(username="rb-user-1", email="rb1@example.com", password="x")
        # Signals are connected to the live Profile class, not the
        # historical one — auto-Profile may or may not have fired.
        # Tolerate both.
        profile = Profile.objects.filter(user=user).first() or Profile.objects.create(user=user)

        org = Org.objects.create(name="Rollback Org", domain="rb1.example.com")
        project = Project.objects.create(org=org, creator=user, name="Daily Notes")
        template = Page.objects.create(project=project, creator=user, title="Template")

        profile.org_state = {
            org.external_id: {
                "daily_note_project_id": project.external_id,
                "daily_note_template_id": template.external_id,
                "last_page_id": None,
            }
        }
        profile.save(update_fields=["org_state", "modified"])

        seeded_project_external_id = project.external_id
        seeded_template_external_id = template.external_id
        profile_pk = profile.pk

        # --- Phase 2: reverse to the pre-backfill schema. -----------
        MigrationExecutor(connection).migrate(PRE_BACKFILL_TARGET)

        # --- Phase 3: assert the FKs came back populated. -----------
        pre_apps = MigrationExecutor(connection).loader.project_state(PRE_BACKFILL_TARGET).apps
        Profile0031 = pre_apps.get_model("users", "Profile")
        Project0031 = pre_apps.get_model("pages", "Project")
        Page0031 = pre_apps.get_model("pages", "Page")

        restored = Profile0031.objects.get(pk=profile_pk)
        self.assertIsNotNone(
            restored.daily_note_project_id,
            "rollback dropped daily_note_project — operators lose user config",
        )
        self.assertEqual(
            Project0031.objects.get(pk=restored.daily_note_project_id).external_id,
            seeded_project_external_id,
        )
        self.assertIsNotNone(
            restored.daily_note_template_id,
            "rollback dropped daily_note_template — operators lose template selection",
        )
        self.assertEqual(
            Page0031.objects.get(pk=restored.daily_note_template_id).external_id,
            seeded_template_external_id,
        )

    def test_reverse_leaves_fks_null_when_org_state_is_empty(self):
        """A profile with no `org_state` (legacy user who never set a
        daily note) shouldn't crash the reverse; it should just leave
        the re-added FK columns NULL. Pins the .iterator() / exclude
        guard so a future contributor doesn't reintroduce an
        unconditional save() that touches every Profile.
        """
        head_apps = MigrationExecutor(connection).loader.project_state(HEAD_TARGET).apps
        User = head_apps.get_model("users", "User")
        Profile = head_apps.get_model("users", "Profile")

        user = User.objects.create(username="rb-user-2", email="rb2@example.com", password="x")
        profile = Profile.objects.filter(user=user).first() or Profile.objects.create(user=user)
        # No org_state set — default {}.
        profile_pk = profile.pk

        MigrationExecutor(connection).migrate(PRE_BACKFILL_TARGET)

        pre_apps = MigrationExecutor(connection).loader.project_state(PRE_BACKFILL_TARGET).apps
        Profile0031 = pre_apps.get_model("users", "Profile")
        restored = Profile0031.objects.get(pk=profile_pk)
        self.assertIsNone(restored.daily_note_project_id)
        self.assertIsNone(restored.daily_note_template_id)
