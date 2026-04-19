from http import HTTPStatus

from core.tests.common import BaseAuthenticatedViewTestCase
from pages.models import Folder, Page, Project
from pages.tests.factories import FolderFactory, PageFactory, ProjectFactory
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
        profile = self._profile()
        profile.daily_note_project = project
        profile.daily_note_template = template
        profile.save(update_fields=["daily_note_project", "daily_note_template", "modified"])

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
        self.assertEqual(self._profile().daily_note_project_id, existing.id)

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
        profile = self._profile()
        self.assertEqual(profile.daily_note_project_id, project.id)
        self.assertEqual(profile.daily_note_template_id, template.id)

    def test_rejects_project_user_cannot_write_to(self):
        other_user = UserFactory()
        other_org = OrgFactory()
        OrgMemberFactory(org=other_org, user=other_user, role=OrgMemberRole.ADMIN.value)
        other_project = ProjectFactory(org=other_org, creator=other_user)

        response = self.send_api_request(
            url=CONFIG_URL,
            method="patch",
            data={"project_external_id": other_project.external_id},
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
        profile = self._profile()
        profile.daily_note_project = project1
        profile.daily_note_template = template
        profile.save(update_fields=["daily_note_project", "daily_note_template", "modified"])

        project2 = ProjectFactory(org=self.org, creator=self.user)
        response = self.send_api_request(
            url=CONFIG_URL,
            method="patch",
            data={"project_external_id": project2.external_id},
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        profile.refresh_from_db()
        self.assertEqual(profile.daily_note_project_id, project2.id)
        self.assertIsNone(profile.daily_note_template_id)

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
        profile = self._profile()
        profile.daily_note_project = project
        profile.daily_note_template = template
        profile.save(update_fields=["daily_note_project", "daily_note_template", "modified"])

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

    def test_falls_back_to_utc_when_date_missing(self):
        project = ProjectFactory(org=self.org, creator=self.user)
        self._configure(project)

        response = self.send_api_request(url=TODAY_URL, method="post", data={})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        payload = response.json()
        # Title should be a valid YYYY-MM-DD
        self.assertRegex(payload["title"], r"^\d{4}-\d{2}-\d{2}$")


class TestDailyNoteOrganize(DailyNoteTestBase):
    def _configure(self, project):
        profile = self._profile()
        profile.daily_note_project = project
        profile.save(update_fields=["daily_note_project", "modified"])

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
