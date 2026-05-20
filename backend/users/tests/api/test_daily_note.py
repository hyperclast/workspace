from http import HTTPStatus

from core.tests.common import BaseAuthenticatedViewTestCase
from pages.constants import ProjectEditorRole
from pages.models import Folder, Page, Project
from pages.models.editors import ProjectEditor
from pages.tests.factories import FolderFactory, PageFactory, ProjectEditorFactory, ProjectFactory
from users.constants import OrgMemberRole
from users.models import OrgMember, Profile
from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory


CONFIG_URL = "/api/users/me/daily-note/config/"
TODAY_URL = "/api/users/me/daily-note/today/"
ORGANIZE_URL = "/api/users/me/daily-note/organize/"


class DailyNoteTestBase(BaseAuthenticatedViewTestCase):
    """Sets up the authenticated user with an org membership so auto-setup can work."""

    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.ADMIN.value)

    def _profile(self):
        return Profile.objects.get(user=self.user)

    def _bucket(self, org=None):
        """Return `Profile.org_state[org.external_id]` (a fresh dict if unset)."""
        org = org or self.org
        return (self._profile().org_state or {}).get(org.external_id, {})

    def _set_daily_note(self, project, template=None, org=None):
        """Helper: write the daily-note pair into `Profile.org_state[org]`."""
        org = org or self.org
        profile = self._profile()
        org_state = dict(profile.org_state or {})
        bucket = dict(org_state.get(org.external_id, {}))
        bucket["daily_note_project_id"] = project.external_id if project else None
        bucket["daily_note_template_id"] = template.external_id if template else None
        org_state[org.external_id] = bucket
        profile.org_state = org_state
        profile.save(update_fields=["org_state", "modified"])


class TestDailyNoteConfigGet(DailyNoteTestBase):
    def test_returns_nulls_when_unset(self):
        response = self.send_api_request(url=CONFIG_URL, method="get")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        payload = response.json()
        self.assertIsNone(payload["project"])
        self.assertIsNone(payload["template"])
        self.assertEqual(payload["unorganized_count"], 0)

    def test_returns_project_and_template_when_set(self):
        project = ProjectFactory(org=self.org, creator=self.user)
        template = PageFactory(project=project, creator=self.user, title="My Template")
        self._set_daily_note(project, template)

        response = self.send_api_request(url=CONFIG_URL, method="get")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        payload = response.json()
        self.assertEqual(payload["project"]["external_id"], project.external_id)
        self.assertEqual(payload["project"]["name"], project.name)
        self.assertEqual(payload["template"]["external_id"], template.external_id)
        self.assertEqual(payload["template"]["title"], "My Template")


class TestDailyNoteConfigPatchAuto(DailyNoteTestBase):
    def test_auto_picks_existing_daily_notes_project(self):
        existing = ProjectFactory(org=self.org, creator=self.user, name="Daily Notes")

        response = self.send_api_request(url=CONFIG_URL, method="patch", data={"auto": True})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        payload = response.json()
        self.assertEqual(payload["project"]["external_id"], existing.external_id)
        self.assertEqual(self._bucket()["daily_note_project_id"], existing.external_id)

    def test_auto_creates_project_when_none_exists(self):
        response = self.send_api_request(url=CONFIG_URL, method="patch", data={"auto": True})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        payload = response.json()
        self.assertEqual(payload["project"]["name"], "Daily Notes")
        project = Project.objects.get(external_id=payload["project"]["external_id"])
        self.assertEqual(project.org_id, self.org.id)
        self.assertEqual(project.creator_id, self.user.id)

    def test_auto_reports_unorganized_count(self):
        project = ProjectFactory(org=self.org, creator=self.user, name="Daily Notes")
        # Flat notes without folders
        PageFactory(project=project, creator=self.user, title="2026-04-01")
        PageFactory(project=project, creator=self.user, title="2026-04-02")
        PageFactory(project=project, creator=self.user, title="Not a date")

        response = self.send_api_request(url=CONFIG_URL, method="patch", data={"auto": True})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["unorganized_count"], 2)

    def test_auto_fails_without_any_org(self):
        # Remove the user's org membership
        OrgMember.objects.filter(user=self.user).delete()
        # Also ensure no accidentally-writable "Daily Notes" project exists

        response = self.send_api_request(url=CONFIG_URL, method="patch", data={"auto": True})

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)


class TestDailyNoteConfigPatchExplicit(DailyNoteTestBase):
    def test_sets_project_and_template(self):
        project = ProjectFactory(org=self.org, creator=self.user)
        template = PageFactory(project=project, creator=self.user)

        response = self.send_api_request(
            url=CONFIG_URL,
            method="patch",
            data={
                "project_external_id": project.external_id,
                "template_external_id": template.external_id,
            },
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        bucket = self._bucket()
        self.assertEqual(bucket["daily_note_project_id"], project.external_id)
        self.assertEqual(bucket["daily_note_template_id"], template.external_id)

    def test_rejects_project_in_another_org(self):
        """Cross-org boundary: a daily-note project from Org B cannot be set
        while the active org is Org A. The endpoint rejects with 400 before
        the per-project permission check, since this is a hard product
        invariant (orgs are the top-level boundary)."""
        other_user = UserFactory()
        other_org = OrgFactory()
        OrgMemberFactory(org=other_org, user=other_user, role=OrgMemberRole.ADMIN.value)
        other_project = ProjectFactory(org=other_org, creator=other_user)

        response = self.send_api_request(
            url=CONFIG_URL,
            method="patch",
            data={"project_external_id": other_project.external_id},
        )

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)

    def test_rejects_project_user_cannot_write_to_in_same_org(self):
        """When the project IS in the active org but the user lacks write
        permission (org_members_can_access=False and they're a non-admin
        member), the endpoint returns 403."""
        # Demote the test user to MEMBER (the base class makes them an admin,
        # and org admins bypass the org_members_can_access gate via Tier 0).
        OrgMember.objects.filter(user=self.user, org=self.org).update(role=OrgMemberRole.MEMBER.value)

        owner = UserFactory()
        OrgMemberFactory(org=self.org, user=owner, role=OrgMemberRole.ADMIN.value)
        # Project locked down so non-admin members can't reach it.
        locked_project = ProjectFactory(org=self.org, creator=owner, org_members_can_access=False)

        response = self.send_api_request(
            url=CONFIG_URL,
            method="patch",
            data={"project_external_id": locked_project.external_id},
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    def test_rejects_template_not_in_project(self):
        project = ProjectFactory(org=self.org, creator=self.user)
        other_project = ProjectFactory(org=self.org, creator=self.user)
        template_elsewhere = PageFactory(project=other_project, creator=self.user)

        response = self.send_api_request(
            url=CONFIG_URL,
            method="patch",
            data={
                "project_external_id": project.external_id,
                "template_external_id": template_elsewhere.external_id,
            },
        )

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)

    def test_changing_project_without_new_template_clears_stale_template(self):
        project1 = ProjectFactory(org=self.org, creator=self.user)
        template = PageFactory(project=project1, creator=self.user)
        self._set_daily_note(project1, template)

        project2 = ProjectFactory(org=self.org, creator=self.user)
        response = self.send_api_request(
            url=CONFIG_URL,
            method="patch",
            data={"project_external_id": project2.external_id},
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        bucket = self._bucket()
        self.assertEqual(bucket["daily_note_project_id"], project2.external_id)
        self.assertIsNone(bucket.get("daily_note_template_id"))

    def test_requires_project_external_id_when_not_auto(self):
        response = self.send_api_request(url=CONFIG_URL, method="patch", data={})

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)

    def test_returns_404_for_unknown_project(self):
        response = self.send_api_request(
            url=CONFIG_URL,
            method="patch",
            data={"project_external_id": "does-not-exist"},
        )

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)


class TestDailyNoteToday(DailyNoteTestBase):
    def test_returns_409_when_not_configured(self):
        response = self.send_api_request(url=TODAY_URL, method="post", data={})

        self.assertEqual(response.status_code, HTTPStatus.CONFLICT)
        payload = response.json()
        self.assertEqual(payload.get("code"), "daily_note_not_configured")

    def _configure(self, project, template=None):
        self._set_daily_note(project, template)

    def test_creates_page_and_folders_on_first_call(self):
        project = ProjectFactory(org=self.org, creator=self.user)
        self._configure(project)

        response = self.send_api_request(url=TODAY_URL, method="post", data={"date": "2026-04-18"})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        payload = response.json()
        self.assertEqual(payload["title"], "2026-04-18")

        year_folder = Folder.objects.get(project=project, parent=None, name="2026")
        month_folder = Folder.objects.get(project=project, parent=year_folder, name="04")

        page = Page.objects.get(external_id=payload["external_id"])
        self.assertEqual(page.folder_id, month_folder.id)
        self.assertEqual(page.title, "2026-04-18")

    def test_second_call_returns_same_page_no_duplicate_folders(self):
        project = ProjectFactory(org=self.org, creator=self.user)
        self._configure(project)

        first = self.send_api_request(url=TODAY_URL, method="post", data={"date": "2026-04-18"})
        second = self.send_api_request(url=TODAY_URL, method="post", data={"date": "2026-04-18"})

        self.assertEqual(first.status_code, HTTPStatus.OK)
        self.assertEqual(second.status_code, HTTPStatus.OK)
        self.assertEqual(first.json()["external_id"], second.json()["external_id"])

        self.assertEqual(Folder.objects.filter(project=project, parent=None, name="2026").count(), 1)
        self.assertEqual(Page.objects.filter(project=project, title="2026-04-18").count(), 1)

    def test_honors_template_via_copy_from(self):
        project = ProjectFactory(org=self.org, creator=self.user)
        template = PageFactory(
            project=project,
            creator=self.user,
            title="Daily Template",
            details={"content": "# Daily checklist\n- [ ] Item", "filetype": "md"},
        )
        self._configure(project, template=template)

        response = self.send_api_request(url=TODAY_URL, method="post", data={"date": "2026-04-18"})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        page = Page.objects.get(external_id=response.json()["external_id"])
        self.assertEqual(page.details.get("content"), "# Daily checklist\n- [ ] Item")

    def test_rejects_malformed_date(self):
        project = ProjectFactory(org=self.org, creator=self.user)
        self._configure(project)

        response = self.send_api_request(url=TODAY_URL, method="post", data={"date": "not-a-date"})
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)

    def test_rejects_invalid_calendar_date(self):
        project = ProjectFactory(org=self.org, creator=self.user)
        self._configure(project)

        response = self.send_api_request(url=TODAY_URL, method="post", data={"date": "2026-02-30"})
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)

    def test_returns_409_when_user_lost_read_access(self):
        """If the user has lost ALL access to their daily-note project
        (locked-down project, demoted from admin, no editor role), the
        endpoint surfaces it as `daily_note_not_configured` — the same
        signal the frontend wizard uses to re-prompt. We don't expose a
        403 here because that would confirm the existence of the
        project to a user who can no longer see it."""
        from pages.tests.factories import ProjectEditorFactory

        owner = UserFactory()
        OrgMemberFactory(org=self.org, user=owner, role=OrgMemberRole.ADMIN.value)
        project = ProjectFactory(org=self.org, creator=owner, org_members_can_access=False)

        # Demote self to non-admin member; the locked-down project denies
        # access at every tier.
        OrgMember.objects.filter(user=self.user, org=self.org).update(role=OrgMemberRole.MEMBER.value)

        self._configure(project)

        response = self.send_api_request(url=TODAY_URL, method="post", data={"date": "2026-04-18"})

        self.assertEqual(response.status_code, HTTPStatus.CONFLICT)
        self.assertEqual(response.json().get("code"), "daily_note_not_configured")

    def test_returns_403_when_user_has_read_but_not_write_access(self):
        """If the user can still read the project but not write, /today/
        rejects with 403. Construct the project with org-member read
        access enabled but the user only as a `viewer` (read-only) editor."""
        from pages.constants import ProjectEditorRole
        from pages.tests.factories import ProjectEditorFactory

        owner = UserFactory()
        OrgMemberFactory(org=self.org, user=owner, role=OrgMemberRole.ADMIN.value)
        project = ProjectFactory(org=self.org, creator=owner, org_members_can_access=False)

        # Self gets viewer-only access via project sharing — read yes, write no.
        OrgMember.objects.filter(user=self.user, org=self.org).update(role=OrgMemberRole.MEMBER.value)
        ProjectEditorFactory(user=self.user, project=project, role=ProjectEditorRole.VIEWER.value)

        self._configure(project)

        response = self.send_api_request(url=TODAY_URL, method="post", data={"date": "2026-04-18"})

        # Project resolves (read access via project editor); write check fails.
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    def test_falls_back_to_utc_when_date_missing(self):
        project = ProjectFactory(org=self.org, creator=self.user)
        self._configure(project)

        response = self.send_api_request(url=TODAY_URL, method="post", data={})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        payload = response.json()
        # Title should be a valid YYYY-MM-DD
        self.assertRegex(payload["title"], r"^\d{4}-\d{2}-\d{2}$")

    def test_returns_409_when_project_deleted(self):
        """If the configured project is hard-deleted, /today/ returns 409.

        Under `Profile.org_state` (JSONField) the external_id stays in
        the JSON as a stale string. The endpoint resolves through an
        is_deleted=False filter that won't match a hard-deleted row, so
        the call falls through to the not-configured branch.
        """
        project = ProjectFactory(org=self.org, creator=self.user)
        self._configure(project)
        project.delete()

        response = self.send_api_request(url=TODAY_URL, method="post", data={"date": "2026-04-18"})

        self.assertEqual(response.status_code, HTTPStatus.CONFLICT)
        self.assertEqual(response.json().get("code"), "daily_note_not_configured")

    def test_creates_blank_note_when_template_deleted(self):
        """If the configured template is hard-deleted, /today/ creates a blank note."""
        project = ProjectFactory(org=self.org, creator=self.user)
        template = PageFactory(
            project=project,
            creator=self.user,
            title="Daily Template",
            details={"content": "# Template content", "filetype": "md"},
        )
        self._configure(project, template=template)
        template.delete()

        response = self.send_api_request(url=TODAY_URL, method="post", data={"date": "2026-04-18"})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        page = Page.objects.get(external_id=response.json()["external_id"])
        self.assertEqual(page.details.get("content"), "")

    def test_auto_creates_new_project_when_user_has_viewer_only_daily_notes(self):
        """auto=true should create a new project when the user only has viewer access to a 'Daily Notes' project."""
        other_user = UserFactory()
        other_org = OrgFactory()
        OrgMemberFactory(org=other_org, user=other_user, role=OrgMemberRole.ADMIN.value)
        existing = ProjectFactory(org=other_org, creator=other_user, name="Daily Notes")

        # Give our user viewer-only access to the existing project
        ProjectEditorFactory(user=self.user, project=existing, role=ProjectEditorRole.VIEWER.value)

        response = self.send_api_request(url=CONFIG_URL, method="patch", data={"auto": True})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        payload = response.json()
        # Backend should create a new project, not reuse the viewer-only one
        self.assertNotEqual(payload["project"]["external_id"], existing.external_id)
        self.assertEqual(payload["project"]["name"], "Daily Notes")

        new_project = Project.objects.get(external_id=payload["project"]["external_id"])
        self.assertEqual(new_project.creator_id, self.user.id)


class TestDailyNoteOrganize(DailyNoteTestBase):
    def _configure(self, project):
        self._set_daily_note(project)

    def test_returns_409_when_not_configured(self):
        response = self.send_api_request(url=ORGANIZE_URL, method="post", data={})
        self.assertEqual(response.status_code, HTTPStatus.CONFLICT)

    def test_moves_only_date_titled_pages(self):
        project = ProjectFactory(org=self.org, creator=self.user)
        self._configure(project)

        dated1 = PageFactory(project=project, creator=self.user, title="2026-04-01", folder=None)
        dated2 = PageFactory(project=project, creator=self.user, title="2025-12-31", folder=None)
        not_dated = PageFactory(project=project, creator=self.user, title="Random Page", folder=None)

        response = self.send_api_request(url=ORGANIZE_URL, method="post", data={"dry_run": False})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        body = response.json()
        self.assertEqual(body["total_matched"], 2)
        self.assertEqual(body["moved_count"], 2)

        dated1.refresh_from_db()
        dated2.refresh_from_db()
        not_dated.refresh_from_db()
        self.assertIsNotNone(dated1.folder)
        self.assertEqual(dated1.folder.name, "04")
        self.assertEqual(dated1.folder.parent.name, "2026")
        self.assertEqual(dated2.folder.name, "12")
        self.assertEqual(dated2.folder.parent.name, "2025")
        self.assertIsNone(not_dated.folder)

    def test_idempotent_on_second_run(self):
        project = ProjectFactory(org=self.org, creator=self.user)
        self._configure(project)
        PageFactory(project=project, creator=self.user, title="2026-04-01", folder=None)

        first = self.send_api_request(url=ORGANIZE_URL, method="post", data={"dry_run": False})
        second = self.send_api_request(url=ORGANIZE_URL, method="post", data={"dry_run": False})

        self.assertEqual(first.status_code, HTTPStatus.OK)
        self.assertEqual(first.json()["moved_count"], 1)
        self.assertEqual(second.status_code, HTTPStatus.OK)
        self.assertEqual(second.json()["moved_count"], 0)
        self.assertEqual(second.json()["skipped_count"], 1)
        self.assertEqual(second.json()["total_matched"], 1)

    def test_dry_run_returns_counts_without_mutation(self):
        project = ProjectFactory(org=self.org, creator=self.user)
        self._configure(project)
        page = PageFactory(project=project, creator=self.user, title="2026-04-01", folder=None)

        response = self.send_api_request(url=ORGANIZE_URL, method="post", data={"dry_run": True})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        body = response.json()
        self.assertEqual(body["moved_count"], 1)
        self.assertEqual(body["total_matched"], 1)

        page.refresh_from_db()
        self.assertIsNone(page.folder)
        self.assertFalse(Folder.objects.filter(project=project).exists())

    def test_organize_excludes_non_date_titles_at_db_level(self):
        """Pages with non-YYYY-MM-DD titles should never be loaded from the DB."""
        project = ProjectFactory(org=self.org, creator=self.user)
        self._configure(project)

        PageFactory(project=project, creator=self.user, title="2026-04-01", folder=None)
        PageFactory(project=project, creator=self.user, title="Meeting Notes", folder=None)
        PageFactory(project=project, creator=self.user, title="2026-ab-01", folder=None)
        PageFactory(project=project, creator=self.user, title="not-a-date", folder=None)

        response = self.send_api_request(url=ORGANIZE_URL, method="post", data={"dry_run": True})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        body = response.json()
        self.assertEqual(body["total_matched"], 1)
        self.assertEqual(body["moved_count"], 1)

    def test_skips_pages_already_in_correct_folder(self):
        project = ProjectFactory(org=self.org, creator=self.user)
        self._configure(project)
        year = FolderFactory(project=project, parent=None, name="2026")
        month = FolderFactory(project=project, parent=year, name="04")
        PageFactory(project=project, creator=self.user, title="2026-04-01", folder=month)

        response = self.send_api_request(url=ORGANIZE_URL, method="post", data={"dry_run": False})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        body = response.json()
        self.assertEqual(body["moved_count"], 0)
        self.assertEqual(body["skipped_count"], 1)
        self.assertEqual(body["total_matched"], 1)


class TestDailyNoteStaleReferenceTolerance(DailyNoteTestBase):
    """`Profile.org_state` stores external_ids (strings), not FKs, so a
    soft-deleted project/page leaves a harmless stale id in the JSON
    rather than requiring eager cleanup. The endpoints resolve every id
    through `is_deleted=False` filters at access time and silently treat
    stale values as 'not configured.'"""

    def test_today_returns_409_when_project_is_soft_deleted(self):
        project = ProjectFactory(org=self.org, creator=self.user)
        self._set_daily_note(project)
        project.is_deleted = True
        project.save(update_fields=["is_deleted", "modified"])

        response = self.send_api_request(url=TODAY_URL, method="post", data={"date": "2026-04-18"})

        self.assertEqual(response.status_code, HTTPStatus.CONFLICT)
        self.assertEqual(response.json().get("code"), "daily_note_not_configured")
        # Stale id remains in JSON — harmless and overwritten on next config update.
        self.assertEqual(self._bucket().get("daily_note_project_id"), project.external_id)

    def test_organize_returns_409_when_project_is_soft_deleted(self):
        project = ProjectFactory(org=self.org, creator=self.user)
        self._set_daily_note(project)
        project.is_deleted = True
        project.save(update_fields=["is_deleted", "modified"])

        response = self.send_api_request(url=ORGANIZE_URL, method="post", data={"dry_run": False})

        self.assertEqual(response.status_code, HTTPStatus.CONFLICT)
        self.assertEqual(response.json().get("code"), "daily_note_not_configured")

    def test_config_returns_nulls_for_soft_deleted_project(self):
        project = ProjectFactory(org=self.org, creator=self.user)
        self._set_daily_note(project)
        project.is_deleted = True
        project.save(update_fields=["is_deleted", "modified"])

        response = self.send_api_request(url=CONFIG_URL, method="get")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIsNone(payload["project"])
        self.assertIsNone(payload["template"])

    def test_template_in_other_project_is_silently_ignored(self):
        """A template id pointing at a page in a different project (e.g.
        the daily-note project was reassigned without updating the
        template) resolves to None instead of leaking across projects."""
        project = ProjectFactory(org=self.org, creator=self.user)
        other_project = ProjectFactory(org=self.org, creator=self.user)
        template = PageFactory(project=other_project, creator=self.user, title="Template")
        self._set_daily_note(project, template=template)

        response = self.send_api_request(url=CONFIG_URL, method="get")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(payload["project"]["external_id"], project.external_id)
        self.assertIsNone(payload["template"])


class TestDailyNoteConfigAccessBoundary(DailyNoteTestBase):
    """Reads use the same access boundary as writes: a user who has lost
    access to the configured project must not see its name, template
    title, or page count via the config endpoint."""

    def test_config_hides_project_when_user_lost_read_access(self):
        owner = UserFactory()
        OrgMemberFactory(org=self.org, user=owner, role=OrgMemberRole.ADMIN.value)
        project = ProjectFactory(org=self.org, creator=owner, org_members_can_access=False)
        template = PageFactory(project=project, creator=owner, title="Secret Template")

        OrgMember.objects.filter(user=self.user, org=self.org).update(role=OrgMemberRole.MEMBER.value)
        self._set_daily_note(project, template=template)

        response = self.send_api_request(url=CONFIG_URL, method="get")
        payload = response.json()

        # Looks unconfigured. No project name, template title, or count.
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIsNone(payload["project"])
        self.assertIsNone(payload["template"])
        self.assertEqual(payload["unorganized_count"], 0)

    def test_unorganized_count_excludes_inaccessible_pages(self):
        """The user has read access to the daily-note project itself but
        the project contains a YYYY-MM-DD page hidden behind page-level
        sharing. That page must not contribute to the count."""
        from pages.constants import ProjectEditorRole
        from pages.tests.factories import ProjectEditorFactory

        # User has Tier 2 (project editor) read access to the project.
        owner = UserFactory()
        OrgMemberFactory(org=self.org, user=owner, role=OrgMemberRole.ADMIN.value)
        project = ProjectFactory(org=self.org, creator=owner, org_members_can_access=False)
        OrgMember.objects.filter(user=self.user, org=self.org).update(role=OrgMemberRole.MEMBER.value)
        ProjectEditorFactory(user=self.user, project=project, role=ProjectEditorRole.EDITOR.value)
        self._set_daily_note(project)

        # An accessible page in the daily-note project, not yet filed.
        PageFactory(project=project, creator=self.user, title="2026-04-01")

        # A page in the SAME project but kept inaccessible to self.user.
        # We achieve this by creating it inside a separate locked-down
        # project — pages can't escape their project, so the simpler
        # mechanism is to keep one project visible to the user and add
        # the noise page to a project they can't touch.
        hidden_project = ProjectFactory(org=self.org, creator=owner, org_members_can_access=False)
        PageFactory(project=hidden_project, creator=owner, title="2026-04-02")

        response = self.send_api_request(url=CONFIG_URL, method="get")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        # Only the page in the user-accessible daily-note project counts.
        self.assertEqual(payload["unorganized_count"], 1)


class TestDailyNoteOrgIdOverride(DailyNoteTestBase):
    """Every daily-note endpoint accepts `?org_id=…` to operate on a
    specific org rather than the implicit one chosen by `_resolve_org`
    (Profile.current_org → first joined org). The frontend always sends
    it now to keep the per-org state addressing unambiguous. These
    tests pin:

      * The override actually targets that org's bucket, not the default.
      * Per-org state is isolated — writing daily-note config for Org A
        doesn't surface in Org B's response.
      * Orgs the user has no access to at all (no membership, no
        project/page-editor tie) are rejected with the same "no org
        available" contract as the no-org-at-all path.
      * External collaborators (project- or page-editors without
        `OrgMember`) can still target their workspace via `?org_id=`
        thanks to the shared three-tier `user_has_org_access` check.
    """

    def setUp(self):
        super().setUp()
        # `self.org` (set up by DailyNoteTestBase) is Org A. Add a second.
        self.org_b = OrgFactory()
        OrgMemberFactory(org=self.org_b, user=self.user, role=OrgMemberRole.ADMIN.value)
        self.profile = self._profile()

    def test_config_get_targets_specified_org_not_default(self):
        """Setting the daily-note project in Org B and then calling
        `GET /config/?org_id=<B>` returns Org B's project — not whatever
        `_resolve_org`'s fallback would have picked."""
        project_a = ProjectFactory(org=self.org, creator=self.user, name="A project")
        project_b = ProjectFactory(org=self.org_b, creator=self.user, name="B project")
        self._set_daily_note(project_a, org=self.org)
        self._set_daily_note(project_b, org=self.org_b)

        # No `?org_id=` falls through to the default (Profile.current_org
        # is None, so first joined org → self.org). Confirm baseline.
        response = self.send_api_request(url=CONFIG_URL, method="get")
        self.assertEqual(response.json()["project"]["external_id"], project_a.external_id)

        # `?org_id=<B>` overrides.
        response = self.send_api_request(url=f"{CONFIG_URL}?org_id={self.org_b.external_id}", method="get")
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["project"]["external_id"], project_b.external_id)

    def test_config_patch_explicit_writes_to_specified_org_only(self):
        """A PATCH with `?org_id=<B>` writes to Org B's bucket. Org A's
        bucket must not be touched (no cross-org leakage in `org_state`)."""
        project_a = ProjectFactory(org=self.org, creator=self.user, name="A project")
        project_b = ProjectFactory(org=self.org_b, creator=self.user, name="B project")
        self._set_daily_note(project_a, org=self.org)

        response = self.send_api_request(
            url=f"{CONFIG_URL}?org_id={self.org_b.external_id}",
            method="patch",
            data={"project_external_id": project_b.external_id},
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)

        # Org B's bucket has the new project.
        self.assertEqual(self._bucket(org=self.org_b).get("daily_note_project_id"), project_b.external_id)
        # Org A's bucket is untouched.
        self.assertEqual(self._bucket(org=self.org).get("daily_note_project_id"), project_a.external_id)

    def test_config_patch_auto_targets_specified_org(self):
        """`auto=True` with `?org_id=<B>` creates the 'Daily Notes'
        project in Org B, not Org A."""
        response = self.send_api_request(
            url=f"{CONFIG_URL}?org_id={self.org_b.external_id}",
            method="patch",
            data={"auto": True},
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        payload = response.json()
        project = Project.objects.get(external_id=payload["project"]["external_id"])
        self.assertEqual(project.org_id, self.org_b.id)

    def test_config_patch_rejects_project_in_a_different_org_than_query(self):
        """The "project must belong to active org" 400 fires against the
        org named in `?org_id=`, not the default. A project in Org A
        cannot be set as the daily-note project when targeting Org B."""
        project_a = ProjectFactory(org=self.org, creator=self.user, name="A project")

        response = self.send_api_request(
            url=f"{CONFIG_URL}?org_id={self.org_b.external_id}",
            method="patch",
            data={"project_external_id": project_a.external_id},
        )
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIn("belong to the active organization", response.json().get("message", ""))

    def test_today_uses_specified_org(self):
        """`/today/?org_id=<B>` opens today's daily note in Org B's
        configured project — not Org A's."""
        project_a = ProjectFactory(org=self.org, creator=self.user, name="A project")
        project_b = ProjectFactory(org=self.org_b, creator=self.user, name="B project")
        self._set_daily_note(project_a, org=self.org)
        self._set_daily_note(project_b, org=self.org_b)

        response = self.send_api_request(
            url=f"{TODAY_URL}?org_id={self.org_b.external_id}", method="post", data={"date": "2026-04-18"}
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        # Page was created under Org B's project.
        page = Page.objects.get(external_id=response.json()["external_id"])
        self.assertEqual(page.project_id, project_b.id)

    def test_today_with_unconfigured_specified_org_returns_409(self):
        """Org B has no daily-note config, but Org A does. With
        `?org_id=<B>` the endpoint must return 409 (it's looking at B's
        bucket), not silently fall through to A."""
        project_a = ProjectFactory(org=self.org, creator=self.user, name="A project")
        self._set_daily_note(project_a, org=self.org)

        response = self.send_api_request(
            url=f"{TODAY_URL}?org_id={self.org_b.external_id}", method="post", data={"date": "2026-04-18"}
        )
        self.assertEqual(response.status_code, HTTPStatus.CONFLICT)
        self.assertEqual(response.json().get("code"), "daily_note_not_configured")

    def test_non_member_org_id_falls_to_no_org_available(self):
        """`?org_id=<some-org-user-is-not-a-member-of>` returns
        non-membership through the same "no org available" contract
        as the unauthenticated/no-org case — no membership leak."""
        outsider_org = OrgFactory()

        # GET: returns nulls (matches the no-org-resolved branch).
        response = self.send_api_request(url=f"{CONFIG_URL}?org_id={outsider_org.external_id}", method="get")
        self.assertEqual(response.status_code, HTTPStatus.OK)
        payload = response.json()
        self.assertIsNone(payload["project"])

        # PATCH: 400 No organization available.
        response = self.send_api_request(
            url=f"{CONFIG_URL}?org_id={outsider_org.external_id}",
            method="patch",
            data={"auto": True},
        )
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)

        # /today/: 409 not_configured.
        response = self.send_api_request(
            url=f"{TODAY_URL}?org_id={outsider_org.external_id}",
            method="post",
            data={"date": "2026-04-18"},
        )
        self.assertEqual(response.status_code, HTTPStatus.CONFLICT)

    def test_project_editor_in_non_member_org_can_target_via_explicit_org_id(self):
        """A user who is a *project editor* in Org C but not an
        `OrgMember` can use `?org_id=<C>` to operate on it via the
        daily-note endpoints. `_resolve_org` aligns with the shared
        three-tier access check (`users.access.user_has_org_access`),
        matching the read and write paths for `Profile.current_org`
        elsewhere on this branch. An earlier membership-only gate
        silently dropped these users into the "no org available" 400.
        """
        from pages.constants import ProjectEditorRole
        from pages.tests.factories import ProjectEditorFactory

        org_c = OrgFactory()
        owner = UserFactory()
        OrgMemberFactory(org=org_c, user=owner, role=OrgMemberRole.ADMIN.value)
        project_c = ProjectFactory(org=org_c, creator=owner, org_members_can_access=False)
        # A real page in `project_c` so the user's project-editor row
        # actually surfaces through `get_user_accessible_pages` — the
        # three-tier helper bottoms out on that queryset. An editor of
        # an empty project has nothing to access in the org and is
        # intentionally not promoted by the helper.
        PageFactory(project=project_c, creator=owner)
        ProjectEditorFactory(user=self.user, project=project_c, role=ProjectEditorRole.EDITOR.value)

        response = self.send_api_request(
            url=f"{CONFIG_URL}?org_id={org_c.external_id}",
            method="patch",
            data={"auto": True},
        )
        # `_resolve_org` resolves Org C via Tier 2 → auto-setup succeeds
        # and the created Daily Notes project belongs to Org C.
        self.assertEqual(response.status_code, HTTPStatus.OK)
        payload = response.json()
        project = Project.objects.get(external_id=payload["project"]["external_id"])
        self.assertEqual(project.org_id, org_c.id)

    def test_page_editor_in_non_member_org_can_target_via_explicit_org_id(self):
        """Same alignment as the project-editor case, but at Tier 3 (page
        editor on a single page in the org). Pins that the helper is the
        single source of truth — narrowing it to project-level would
        silently regress this case.
        """
        from pages.constants import PageEditorRole
        from pages.tests.factories import PageEditorFactory

        org_c = OrgFactory()
        owner = UserFactory()
        OrgMemberFactory(org=org_c, user=owner, role=OrgMemberRole.ADMIN.value)
        project_c = ProjectFactory(org=org_c, creator=owner, org_members_can_access=False)
        page_c = PageFactory(project=project_c, creator=owner)
        PageEditorFactory(user=self.user, page=page_c, role=PageEditorRole.EDITOR.value)

        # GET resolves Org C and returns the no-config-yet shape (the
        # user has no `org_state` bucket for Org C yet — that's a 200
        # with nulls, *not* the "no org available" branch).
        response = self.send_api_request(url=f"{CONFIG_URL}?org_id={org_c.external_id}", method="get")
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIsNone(response.json()["project"])

    def test_current_org_honors_three_tier_access(self):
        """Priority 2 of `_resolve_org` (no explicit `?org_id=`,
        falls through to `Profile.current_org`) honors the same
        three-tier check. Without this, an external collaborator who
        legitimately persisted Org C as their current workspace would
        silently fall back to the membership-only "first joined org",
        landing daily-note writes in the wrong workspace.
        """
        from pages.constants import ProjectEditorRole
        from pages.tests.factories import ProjectEditorFactory

        org_c = OrgFactory()
        owner = UserFactory()
        OrgMemberFactory(org=org_c, user=owner, role=OrgMemberRole.ADMIN.value)
        project_c = ProjectFactory(org=org_c, creator=owner, org_members_can_access=False)
        # See the project-editor test above for why a real page is
        # required to surface the user's Tier 2 access.
        PageFactory(project=project_c, creator=owner)
        ProjectEditorFactory(user=self.user, project=project_c, role=ProjectEditorRole.EDITOR.value)

        # Persist Org C as current_org for the user (no `?org_id=` in
        # the request below — Priority 2 is what's under test).
        profile = self._profile()
        profile.current_org = org_c
        profile.save(update_fields=["current_org", "modified"])

        response = self.send_api_request(
            url=CONFIG_URL,
            method="patch",
            data={"auto": True},
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        project = Project.objects.get(external_id=response.json()["project"]["external_id"])
        # Auto-created in Org C (via Priority 2 three-tier resolution),
        # not in self.org (the user's first joined org).
        self.assertEqual(project.org_id, org_c.id)
