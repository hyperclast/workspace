from datetime import timedelta
from http import HTTPStatus
from unittest.mock import patch

from django.test import override_settings
from django.utils import timezone

from collab.models import YSnapshot, YUpdate
from collab.tasks import sync_snapshot_with_page
from core.helpers import hashify
from core.tests.common import BaseAuthenticatedViewTestCase
from pages.constants import PageEditorRole, ProjectEditorRole
from pages.models import Page
from pages.models.rewind import Rewind
from pages.services.rewind import maybe_create_rewind
from pages.tests.factories import PageEditorFactory, PageFactory, ProjectEditorFactory, ProjectFactory
from users.constants import OrgMemberRole
from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory


class RewindAPITestBase(BaseAuthenticatedViewTestCase):
    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.ADMIN.value)
        self.project = ProjectFactory(org=self.org, creator=self.user)
        self.page = PageFactory(project=self.project, creator=self.user)

    def _create_rewind(self, content="Hello", **kwargs):
        self.page.refresh_from_db()
        content_hash = hashify(content)
        return maybe_create_rewind(self.page, content, content_hash, **kwargs)

    def _create_rewind_backdated(self, content, seconds_ago=120):
        """Create a rewind and backdate it to bypass time threshold."""
        Rewind.objects.filter(page=self.page).update(created=timezone.now() - timedelta(seconds=seconds_ago))
        self.page.refresh_from_db()
        return maybe_create_rewind(self.page, content, hashify(content))


# ============================================================
# LIST REWINDS
# ============================================================


class TestRewindModelBasics(RewindAPITestBase):
    def test_created_rewind_has_valid_id(self):
        """Rewind instances should have an auto-assigned positive integer id."""
        rewind = self._create_rewind("Hello")
        self.assertIsNotNone(rewind.id)
        self.assertIsInstance(rewind.id, int)
        self.assertGreater(rewind.id, 0)


class TestListRewinds(RewindAPITestBase):
    def test_list_rewinds_empty(self):
        response = self.send_api_request(url=f"/api/pages/{self.page.external_id}/rewind/")
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(data["count"], 0)
        self.assertEqual(data["items"], [])

    def test_list_rewinds_returns_ordered_by_rewind_number_desc(self):
        self._create_rewind("Rewind 1")
        self._create_rewind_backdated("Rewind 2")

        response = self.send_api_request(url=f"/api/pages/{self.page.external_id}/rewind/")
        data = response.json()
        self.assertEqual(data["count"], 2)
        self.assertEqual(data["items"][0]["rewind_number"], 2)
        self.assertEqual(data["items"][1]["rewind_number"], 1)

    def test_list_rewinds_excludes_content_field(self):
        self._create_rewind("Some content that should not appear in list")

        response = self.send_api_request(url=f"/api/pages/{self.page.external_id}/rewind/")
        data = response.json()
        self.assertNotIn("content", data["items"][0])

    def test_list_rewinds_includes_expected_fields(self):
        self._create_rewind("Hello")

        response = self.send_api_request(url=f"/api/pages/{self.page.external_id}/rewind/")
        item = response.json()["items"][0]

        expected_fields = {
            "external_id",
            "rewind_number",
            "title",
            "content_size_bytes",
            "editors",
            "label",
            "lines_added",
            "lines_deleted",
            "is_compacted",
            "compacted_from_count",
            "created",
        }
        self.assertEqual(set(item.keys()), expected_fields)

    def test_list_rewinds_with_label_filter_case_insensitive(self):
        v = self._create_rewind("Hello")
        v.label = "Before Refactor"
        v.save(update_fields=["label"])

        response = self.send_api_request(
            url=f"/api/pages/{self.page.external_id}/rewind/",
            query_params={"label": "before refactor"},
        )
        data = response.json()
        self.assertEqual(data["count"], 1)

    def test_list_rewinds_with_label_filter_partial_match(self):
        v = self._create_rewind("Hello")
        v.label = "Before Refactor"
        v.save(update_fields=["label"])

        response = self.send_api_request(
            url=f"/api/pages/{self.page.external_id}/rewind/",
            query_params={"label": "refac"},
        )
        data = response.json()
        self.assertEqual(data["count"], 1)

    def test_list_rewinds_with_label_filter_no_match(self):
        v = self._create_rewind("Hello")
        v.label = "Important"
        v.save(update_fields=["label"])

        response = self.send_api_request(
            url=f"/api/pages/{self.page.external_id}/rewind/",
            query_params={"label": "zzzznonexistentzzzz"},
        )
        data = response.json()
        self.assertEqual(data["count"], 0)

    def test_list_rewinds_pagination(self):
        """Default pagination should work."""
        for i in range(3):
            Rewind.objects.filter(page=self.page).update(created=timezone.now() - timedelta(seconds=120))
            self.page.refresh_from_db()
            maybe_create_rewind(self.page, f"Content {i}", hashify(f"Content {i}"))

        response = self.send_api_request(
            url=f"/api/pages/{self.page.external_id}/rewind/",
            query_params={"limit": 2, "offset": 0},
        )
        data = response.json()
        self.assertEqual(data["count"], 3)
        self.assertEqual(len(data["items"]), 2)

    def test_list_rewinds_pagination_second_page(self):
        for i in range(3):
            Rewind.objects.filter(page=self.page).update(created=timezone.now() - timedelta(seconds=120))
            self.page.refresh_from_db()
            maybe_create_rewind(self.page, f"Content {i}", hashify(f"Content {i}"))

        response = self.send_api_request(
            url=f"/api/pages/{self.page.external_id}/rewind/",
            query_params={"limit": 2, "offset": 2},
        )
        data = response.json()
        self.assertEqual(data["count"], 3)
        self.assertEqual(len(data["items"]), 1)


class TestListRewindsAccessControl(RewindAPITestBase):
    def test_nonexistent_page_returns_404(self):
        response = self.send_api_request(url="/api/pages/nonexistent123/rewind/")
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_deleted_page_returns_404(self):
        self._create_rewind("Hello")
        self.page.mark_as_deleted()

        response = self.send_api_request(url=f"/api/pages/{self.page.external_id}/rewind/")
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_no_access_returns_404(self):
        """User with no org/project/page access gets 404 (not 403, to avoid leaking existence)."""
        other_user = UserFactory()
        other_org = OrgFactory()
        OrgMemberFactory(org=other_org, user=other_user, role=OrgMemberRole.ADMIN.value)
        other_project = ProjectFactory(org=other_org, creator=other_user)
        other_page = PageFactory(project=other_project, creator=other_user)

        response = self.send_api_request(url=f"/api/pages/{other_page.external_id}/rewind/")
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_org_member_can_list(self):
        member = UserFactory()
        OrgMemberFactory(org=self.org, user=member, role=OrgMemberRole.MEMBER.value)
        self._create_rewind("Hello")

        self.login(member)
        response = self.send_api_request(url=f"/api/pages/{self.page.external_id}/rewind/")
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["count"], 1)

    def test_project_viewer_can_list(self):
        viewer = UserFactory()
        ProjectEditorFactory(user=viewer, project=self.project, role=ProjectEditorRole.VIEWER.value)
        self._create_rewind("Hello")

        self.login(viewer)
        response = self.send_api_request(url=f"/api/pages/{self.page.external_id}/rewind/")
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["count"], 1)

    def test_page_viewer_can_list(self):
        viewer = UserFactory()
        PageEditorFactory(user=viewer, page=self.page, role=PageEditorRole.VIEWER.value)
        self._create_rewind("Hello")

        self.login(viewer)
        response = self.send_api_request(url=f"/api/pages/{self.page.external_id}/rewind/")
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_no_access_response_identical_to_nonexistent(self):
        """Unauthorized access must be indistinguishable from nonexistent page
        to prevent information leakage."""
        # Response for nonexistent page
        nonexistent_resp = self.send_api_request(url="/api/pages/nonexistent123/rewind/")

        # Response for existing page user can't access
        other_user = UserFactory()
        other_org = OrgFactory()
        OrgMemberFactory(org=other_org, user=other_user, role=OrgMemberRole.ADMIN.value)
        other_project = ProjectFactory(org=other_org, creator=other_user)
        other_page = PageFactory(project=other_project, creator=other_user)

        no_access_resp = self.send_api_request(url=f"/api/pages/{other_page.external_id}/rewind/")

        # Both must return exactly the same status code and body structure
        self.assertEqual(nonexistent_resp.status_code, no_access_resp.status_code)
        self.assertEqual(nonexistent_resp.status_code, HTTPStatus.NOT_FOUND)
        self.assertEqual(nonexistent_resp.json(), no_access_resp.json())

    def test_unauthenticated_returns_401(self):
        self.client.logout()
        response = self.send_api_request(url=f"/api/pages/{self.page.external_id}/rewind/")
        self.assertIn(response.status_code, [HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN])


# ============================================================
# GET REWIND
# ============================================================


class TestGetRewind(RewindAPITestBase):
    def test_get_rewind_with_content(self):
        rewind = self._create_rewind("Full content here")

        response = self.send_api_request(url=f"/api/pages/{self.page.external_id}/rewind/{rewind.external_id}/")
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(data["content"], "Full content here")
        self.assertEqual(data["rewind_number"], 1)
        self.assertEqual(data["title"], self.page.title)
        self.assertIn("external_id", data)
        self.assertIn("created", data)

    def test_get_nonexistent_rewind_returns_404(self):
        response = self.send_api_request(url=f"/api/pages/{self.page.external_id}/rewind/nonexistent/")
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_get_rewind_from_wrong_page_returns_404(self):
        """A valid rewind external_id but for a different page → 404."""
        rewind = self._create_rewind("Hello")

        other_page = PageFactory(project=self.project, creator=self.user)
        response = self.send_api_request(url=f"/api/pages/{other_page.external_id}/rewind/{rewind.external_id}/")
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_get_rewind_on_deleted_page_returns_404(self):
        rewind = self._create_rewind("Hello")
        ext_id = rewind.external_id
        self.page.mark_as_deleted()

        response = self.send_api_request(url=f"/api/pages/{self.page.external_id}/rewind/{ext_id}/")
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_get_rewind_no_access_should_return_404(self):
        rewind = self._create_rewind("Hello")

        no_access_user = UserFactory()
        self.login(no_access_user)
        response = self.send_api_request(url=f"/api/pages/{self.page.external_id}/rewind/{rewind.external_id}/")
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_get_rewind_includes_all_fields(self):
        rewind = self._create_rewind("Content")
        rewind.label = "Labeled"
        rewind.save(update_fields=["label"])

        response = self.send_api_request(url=f"/api/pages/{self.page.external_id}/rewind/{rewind.external_id}/")
        data = response.json()

        expected_fields = {
            "external_id",
            "rewind_number",
            "title",
            "content",
            "content_size_bytes",
            "editors",
            "label",
            "lines_added",
            "lines_deleted",
            "is_compacted",
            "compacted_from_count",
            "created",
        }
        self.assertEqual(set(data.keys()), expected_fields)


# ============================================================
# RESTORE REWIND
# ============================================================


class TestRestoreRewind(RewindAPITestBase):
    def test_restore_updates_page_content(self):
        original = self._create_rewind("Original content")
        self._create_rewind_backdated("Changed content")

        self.send_api_request(
            url=f"/api/pages/{self.page.external_id}/rewind/{original.external_id}/restore/",
            method="post",
        )

        self.page.refresh_from_db()
        self.assertEqual(self.page.details["content"], "Original content")

    def test_restore_updates_page_title(self):
        """Title should be restored from the rewind too."""
        self.page.title = "Original Title"
        self.page.save(update_fields=["title"])
        original = self._create_rewind("Content")

        self.page.title = "New Title"
        self.page.save(update_fields=["title"])
        self._create_rewind_backdated("New Content")

        self.send_api_request(
            url=f"/api/pages/{self.page.external_id}/rewind/{original.external_id}/restore/",
            method="post",
        )

        self.page.refresh_from_db()
        self.assertEqual(self.page.title, "Original Title")

    def test_restore_creates_new_rewind(self):
        original = self._create_rewind("Original")
        self._create_rewind_backdated("Changed")

        response = self.send_api_request(
            url=f"/api/pages/{self.page.external_id}/rewind/{original.external_id}/restore/",
            method="post",
        )
        data = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(data["rewind_number"], 3)
        self.assertEqual(data["content"], "Original")
        self.assertIn("Restored from v1", data["label"])

    def test_restore_increments_current_rewind_number(self):
        original = self._create_rewind("Original")
        self._create_rewind_backdated("Changed")

        self.send_api_request(
            url=f"/api/pages/{self.page.external_id}/rewind/{original.external_id}/restore/",
            method="post",
        )

        self.page.refresh_from_db()
        self.assertEqual(self.page.current_rewind_number, 3)

    def test_restore_records_restoring_user_as_editor(self):
        original = self._create_rewind("Original")
        self._create_rewind_backdated("Changed")

        response = self.send_api_request(
            url=f"/api/pages/{self.page.external_id}/rewind/{original.external_id}/restore/",
            method="post",
        )
        data = response.json()

        self.assertIn(str(self.user.external_id), data["editors"])

    def test_restore_deletes_crdt_updates(self):
        room_id = f"page_{self.page.external_id}"
        YUpdate.objects.create(room_id=room_id, yupdate=b"update1")
        YUpdate.objects.create(room_id=room_id, yupdate=b"update2")

        original = self._create_rewind("Original")
        self._create_rewind_backdated("Changed")

        self.send_api_request(
            url=f"/api/pages/{self.page.external_id}/rewind/{original.external_id}/restore/",
            method="post",
        )

        self.assertEqual(YUpdate.objects.filter(room_id=room_id).count(), 0)

    def test_restore_deletes_crdt_snapshot(self):
        room_id = f"page_{self.page.external_id}"
        YSnapshot.objects.create(room_id=room_id, snapshot=b"snapshot", last_update_id=10)

        original = self._create_rewind("Original")
        self._create_rewind_backdated("Changed")

        self.send_api_request(
            url=f"/api/pages/{self.page.external_id}/rewind/{original.external_id}/restore/",
            method="post",
        )

        self.assertEqual(YSnapshot.objects.filter(room_id=room_id).count(), 0)

    def test_restore_same_rewind_twice(self):
        """Restoring the same rewind multiple times should work."""
        original = self._create_rewind("Original")
        self._create_rewind_backdated("Changed")

        r1 = self.send_api_request(
            url=f"/api/pages/{self.page.external_id}/rewind/{original.external_id}/restore/",
            method="post",
        )
        self.assertEqual(r1.status_code, HTTPStatus.OK)

        r2 = self.send_api_request(
            url=f"/api/pages/{self.page.external_id}/rewind/{original.external_id}/restore/",
            method="post",
        )
        self.assertEqual(r2.status_code, HTTPStatus.OK)

        # Two separate restore rewinds created
        self.assertEqual(r1.json()["rewind_number"], 3)
        self.assertEqual(r2.json()["rewind_number"], 4)

    def test_restore_nonexistent_rewind_returns_404(self):
        response = self.send_api_request(
            url=f"/api/pages/{self.page.external_id}/rewind/nonexistent/restore/",
            method="post",
        )
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_restore_rewind_from_wrong_page_returns_404(self):
        rewind = self._create_rewind("Hello")

        other_page = PageFactory(project=self.project, creator=self.user)
        response = self.send_api_request(
            url=f"/api/pages/{other_page.external_id}/rewind/{rewind.external_id}/restore/",
            method="post",
        )
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_restore_rewind_content_hash_matches_source(self):
        original = self._create_rewind("Original content")
        self._create_rewind_backdated("Changed content")

        response = self.send_api_request(
            url=f"/api/pages/{self.page.external_id}/rewind/{original.external_id}/restore/",
            method="post",
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)

        restore_v = Rewind.objects.get(page=self.page, rewind_number=response.json()["rewind_number"])

        # Same content, same hash
        self.assertEqual(restore_v.content, original.content)
        self.assertEqual(restore_v.content_hash, original.content_hash)

    def test_restore_succeeds_when_ws_disconnect_fails(self):
        original = self._create_rewind("Original")
        self._create_rewind_backdated("Changed")

        with patch("pages.api.rewind.get_channel_layer", side_effect=Exception("boom")):
            response = self.send_api_request(
                url=f"/api/pages/{self.page.external_id}/rewind/{original.external_id}/restore/",
                method="post",
            )
            self.assertEqual(response.status_code, HTTPStatus.OK)

        self.page.refresh_from_db()
        self.assertEqual(self.page.details["content"], "Original")

    def test_restore_updates_content_hash_in_details(self):
        original = self._create_rewind("Original content")
        self._create_rewind_backdated("Changed content")

        self.send_api_request(
            url=f"/api/pages/{self.page.external_id}/rewind/{original.external_id}/restore/",
            method="post",
        )

        self.page.refresh_from_db()
        self.assertEqual(self.page.details["content_hash"], hashify("Original content"))


class TestRestoreRewindAccessControl(RewindAPITestBase):
    def test_org_admin_can_restore(self):
        """Org admins always have edit access."""
        rewind = self._create_rewind("Content")

        response = self.send_api_request(
            url=f"/api/pages/{self.page.external_id}/rewind/{rewind.external_id}/restore/",
            method="post",
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_page_viewer_cannot_restore(self):
        viewer = UserFactory()
        PageEditorFactory(user=viewer, page=self.page, role=PageEditorRole.VIEWER.value)

        rewind = self._create_rewind("Content")

        self.login(viewer)
        response = self.send_api_request(
            url=f"/api/pages/{self.page.external_id}/rewind/{rewind.external_id}/restore/",
            method="post",
        )
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_project_viewer_cannot_restore(self):
        viewer = UserFactory()
        ProjectEditorFactory(user=viewer, project=self.project, role=ProjectEditorRole.VIEWER.value)

        rewind = self._create_rewind("Content")

        self.login(viewer)
        response = self.send_api_request(
            url=f"/api/pages/{self.page.external_id}/rewind/{rewind.external_id}/restore/",
            method="post",
        )
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_page_editor_can_restore(self):
        editor = UserFactory()
        PageEditorFactory(user=editor, page=self.page, role=PageEditorRole.EDITOR.value)

        rewind = self._create_rewind("Content")

        self.login(editor)
        response = self.send_api_request(
            url=f"/api/pages/{self.page.external_id}/rewind/{rewind.external_id}/restore/",
            method="post",
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_project_editor_can_restore(self):
        editor = UserFactory()
        ProjectEditorFactory(user=editor, project=self.project, role=ProjectEditorRole.EDITOR.value)

        rewind = self._create_rewind("Content")

        self.login(editor)
        response = self.send_api_request(
            url=f"/api/pages/{self.page.external_id}/rewind/{rewind.external_id}/restore/",
            method="post",
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_no_access_user_cannot_restore_should_return_404(self):
        stranger = UserFactory()
        rewind = self._create_rewind("Content")

        self.login(stranger)
        response = self.send_api_request(
            url=f"/api/pages/{self.page.external_id}/rewind/{rewind.external_id}/restore/",
            method="post",
        )
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)


# ============================================================
# RESTORE RACE CONDITIONS
# ============================================================


class TestRestoreRaceWithSyncTask(RewindAPITestBase):
    """Tests for race conditions between restore and sync_snapshot_with_page."""

    @override_settings(REWIND_ENABLED=True)
    def test_sync_task_after_restore_handles_missing_snapshot(self):
        room_id = f"page_{self.page.external_id}"

        # Create a snapshot and rewind
        YSnapshot.objects.create(room_id=room_id, snapshot=b"snapshot_data", last_update_id=1)
        original = self._create_rewind("Original")
        self._create_rewind_backdated("Changed")

        # Restore — this deletes CRDT data
        response = self.send_api_request(
            url=f"/api/pages/{self.page.external_id}/rewind/{original.external_id}/restore/",
            method="post",
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)

        # Verify CRDT data was deleted
        self.assertEqual(YSnapshot.objects.filter(room_id=room_id).count(), 0)
        self.assertEqual(YUpdate.objects.filter(room_id=room_id).count(), 0)

        # Simulate a previously-enqueued sync task running
        sync_snapshot_with_page(room_id)

        # Verify the restore was not corrupted
        self.page.refresh_from_db()
        self.assertEqual(self.page.details["content"], "Original")

    @override_settings(REWIND_ENABLED=True)
    def test_restore_state_not_clobbered_by_stale_sync(self):
        room_id = f"page_{self.page.external_id}"

        original = self._create_rewind("Original")
        self._create_rewind_backdated("Changed")

        response = self.send_api_request(
            url=f"/api/pages/{self.page.external_id}/rewind/{original.external_id}/restore/",
            method="post",
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        restore_rewind_number = response.json()["rewind_number"]

        # Stale sync runs — should be a no-op
        sync_snapshot_with_page(room_id)

        # Rewind count should be exactly 3: original, changed, restore
        self.assertEqual(Rewind.objects.filter(page=self.page).count(), 3)

        # Page rewind number should not have incremented beyond the restore
        self.page.refresh_from_db()
        self.assertEqual(self.page.current_rewind_number, restore_rewind_number)


# ============================================================
# UPDATE REWIND LABEL
# ============================================================


class TestUpdateRewindLabel(RewindAPITestBase):
    def test_update_label(self):
        rewind = self._create_rewind("Content")

        response = self.send_api_request(
            url=f"/api/pages/{self.page.external_id}/rewind/{rewind.external_id}/",
            method="patch",
            data={"label": "Before refactor"},
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["label"], "Before refactor")

        rewind.refresh_from_db()
        self.assertEqual(rewind.label, "Before refactor")

    def test_update_label_to_empty_string(self):
        rewind = self._create_rewind("Content")
        rewind.label = "Had a label"
        rewind.save(update_fields=["label"])

        response = self.send_api_request(
            url=f"/api/pages/{self.page.external_id}/rewind/{rewind.external_id}/",
            method="patch",
            data={"label": ""},
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["label"], "")

    def test_update_label_max_length(self):
        rewind = self._create_rewind("Content")

        long_label = "A" * 255
        response = self.send_api_request(
            url=f"/api/pages/{self.page.external_id}/rewind/{rewind.external_id}/",
            method="patch",
            data={"label": long_label},
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["label"], long_label)

    def test_update_label_too_long_returns_422(self):
        rewind = self._create_rewind("Content")

        too_long = "A" * 256
        response = self.send_api_request(
            url=f"/api/pages/{self.page.external_id}/rewind/{rewind.external_id}/",
            method="patch",
            data={"label": too_long},
        )
        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)

    def test_update_label_preserves_other_fields(self):
        rewind = self._create_rewind("Content")

        response = self.send_api_request(
            url=f"/api/pages/{self.page.external_id}/rewind/{rewind.external_id}/",
            method="patch",
            data={"label": "New Label"},
        )
        data = response.json()

        self.assertEqual(data["content"], "Content")
        self.assertEqual(data["rewind_number"], rewind.rewind_number)

    def test_update_label_nonexistent_rewind_returns_404(self):
        response = self.send_api_request(
            url=f"/api/pages/{self.page.external_id}/rewind/nonexistent/",
            method="patch",
            data={"label": "My label"},
        )
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_update_label_wrong_page_returns_404(self):
        rewind = self._create_rewind("Hello")
        other_page = PageFactory(project=self.project, creator=self.user)

        response = self.send_api_request(
            url=f"/api/pages/{other_page.external_id}/rewind/{rewind.external_id}/",
            method="patch",
            data={"label": "My label"},
        )
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)


class TestUpdateRewindLabelAccessControl(RewindAPITestBase):
    def test_viewer_cannot_label(self):
        viewer = UserFactory()
        PageEditorFactory(user=viewer, page=self.page, role=PageEditorRole.VIEWER.value)

        rewind = self._create_rewind("Content")

        self.login(viewer)
        response = self.send_api_request(
            url=f"/api/pages/{self.page.external_id}/rewind/{rewind.external_id}/",
            method="patch",
            data={"label": "My label"},
        )
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_editor_can_label(self):
        editor = UserFactory()
        PageEditorFactory(user=editor, page=self.page, role=PageEditorRole.EDITOR.value)

        rewind = self._create_rewind("Content")

        self.login(editor)
        response = self.send_api_request(
            url=f"/api/pages/{self.page.external_id}/rewind/{rewind.external_id}/",
            method="patch",
            data={"label": "My label"},
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_no_access_user_cannot_label_should_return_404(self):
        stranger = UserFactory()
        rewind = self._create_rewind("Content")

        self.login(stranger)
        response = self.send_api_request(
            url=f"/api/pages/{self.page.external_id}/rewind/{rewind.external_id}/",
            method="patch",
            data={"label": "My label"},
        )
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)


# ============================================================
# CROSS-ENDPOINT TESTS
# ============================================================


class TestRewindAPIIntegration(RewindAPITestBase):
    def test_full_lifecycle_create_list_get_label_restore(self):
        """End-to-end: create rewinds → list → get → label → restore."""
        # Create some rewinds
        v1 = self._create_rewind("Rewind 1")
        v2 = self._create_rewind_backdated("Rewind 2")

        # List
        resp = self.send_api_request(url=f"/api/pages/{self.page.external_id}/rewind/")
        self.assertEqual(resp.json()["count"], 2)

        # Get detail
        resp = self.send_api_request(url=f"/api/pages/{self.page.external_id}/rewind/{v1.external_id}/")
        self.assertEqual(resp.json()["content"], "Rewind 1")

        # Label
        resp = self.send_api_request(
            url=f"/api/pages/{self.page.external_id}/rewind/{v1.external_id}/",
            method="patch",
            data={"label": "Before big change"},
        )
        self.assertEqual(resp.status_code, HTTPStatus.OK)

        # Restore to v1
        resp = self.send_api_request(
            url=f"/api/pages/{self.page.external_id}/rewind/{v1.external_id}/restore/",
            method="post",
        )
        self.assertEqual(resp.status_code, HTTPStatus.OK)

        # Verify page content
        self.page.refresh_from_db()
        self.assertEqual(self.page.details["content"], "Rewind 1")

        # A third rewind should exist (the restore)
        resp = self.send_api_request(url=f"/api/pages/{self.page.external_id}/rewind/")
        self.assertEqual(resp.json()["count"], 3)

    def test_rewinds_only_for_their_page(self):
        """Rewinds from one page should not appear when listing another page's rewinds."""
        page2 = PageFactory(project=self.project, creator=self.user)
        maybe_create_rewind(page2, "Other page content", hashify("Other page content"))

        self._create_rewind("This page content")

        resp = self.send_api_request(url=f"/api/pages/{self.page.external_id}/rewind/")
        self.assertEqual(resp.json()["count"], 1)
        self.assertEqual(resp.json()["items"][0]["title"], self.page.title)


# ============================================================
# LINE DIFF STATS
# ============================================================


class TestLineDiffInListEndpoint(RewindAPITestBase):
    """Test that list endpoint returns lines_added/lines_deleted."""

    def test_first_rewind_shows_all_lines_added(self):
        self._create_rewind("line1\nline2\nline3")

        response = self.send_api_request(url=f"/api/pages/{self.page.external_id}/rewind/")
        item = response.json()["items"][0]

        self.assertEqual(item["lines_added"], 3)
        self.assertEqual(item["lines_deleted"], 0)

    def test_first_rewind_empty_content_zero_diff(self):
        self._create_rewind("")

        response = self.send_api_request(url=f"/api/pages/{self.page.external_id}/rewind/")
        item = response.json()["items"][0]

        self.assertEqual(item["lines_added"], 0)
        self.assertEqual(item["lines_deleted"], 0)

    @override_settings(REWIND_MIN_INTERVAL_SECONDS=0)
    def test_second_rewind_shows_additions(self):
        self._create_rewind("line1")
        self._create_rewind_backdated("line1\nline2\nline3")

        response = self.send_api_request(url=f"/api/pages/{self.page.external_id}/rewind/")
        # Items are ordered desc by rewind_number; first item is v2
        v2_item = response.json()["items"][0]

        self.assertEqual(v2_item["lines_added"], 2)
        self.assertEqual(v2_item["lines_deleted"], 0)

    @override_settings(REWIND_MIN_INTERVAL_SECONDS=0)
    def test_second_rewind_shows_deletions(self):
        self._create_rewind("line1\nline2\nline3")
        self._create_rewind_backdated("line1")

        response = self.send_api_request(url=f"/api/pages/{self.page.external_id}/rewind/")
        v2_item = response.json()["items"][0]

        self.assertEqual(v2_item["lines_added"], 0)
        self.assertEqual(v2_item["lines_deleted"], 2)

    @override_settings(REWIND_MIN_INTERVAL_SECONDS=0)
    def test_replacement_shows_both_added_and_deleted(self):
        self._create_rewind("old_line")
        self._create_rewind_backdated("new_line")

        response = self.send_api_request(url=f"/api/pages/{self.page.external_id}/rewind/")
        v2_item = response.json()["items"][0]

        self.assertEqual(v2_item["lines_added"], 1)
        self.assertEqual(v2_item["lines_deleted"], 1)


class TestLineDiffInGetEndpoint(RewindAPITestBase):
    """Test that get detail endpoint returns lines_added/lines_deleted."""

    def test_get_rewind_includes_diff_stats(self):
        rewind = self._create_rewind("line1\nline2")

        response = self.send_api_request(url=f"/api/pages/{self.page.external_id}/rewind/{rewind.external_id}/")
        data = response.json()

        self.assertEqual(data["lines_added"], 2)
        self.assertEqual(data["lines_deleted"], 0)

    @override_settings(REWIND_MIN_INTERVAL_SECONDS=0)
    def test_get_second_rewind_diff_stats(self):
        self._create_rewind("a\nb")
        v2 = self._create_rewind_backdated("a\nb\nc\nd")

        response = self.send_api_request(url=f"/api/pages/{self.page.external_id}/rewind/{v2.external_id}/")
        data = response.json()

        self.assertEqual(data["lines_added"], 2)
        self.assertEqual(data["lines_deleted"], 0)


class TestLineDiffInRestoreEndpoint(RewindAPITestBase):
    """Test that restore creates a rewind with correct diff stats."""

    def test_restore_rewind_has_diff_stats(self):
        """Restoring from 'Changed' to 'Original' should compute diff between them."""
        original = self._create_rewind("Original\nline2")
        self._create_rewind_backdated("Changed\nline2\nline3")

        # Sync page details to match latest rewind (mirrors sync_snapshot_with_page)
        self.page.details["content"] = "Changed\nline2\nline3"
        self.page.save(update_fields=["details"])

        response = self.send_api_request(
            url=f"/api/pages/{self.page.external_id}/rewind/{original.external_id}/restore/",
            method="post",
        )
        data = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("lines_added", data)
        self.assertIn("lines_deleted", data)
        # Restoring "Original\nline2" from "Changed\nline2\nline3"
        # "Changed" → "Original" (1 replace), "line3" removed (1 delete)
        self.assertEqual(data["lines_added"], 1)
        self.assertEqual(data["lines_deleted"], 2)

    def test_restore_to_same_content_shows_zero_diff(self):
        """If current content matches the restore target, diff should be 0/0."""
        # Create rewind with content A
        original = self._create_rewind("Same content")
        # Page details already have "Same content" as current
        self.page.details["content"] = "Same content"
        self.page.save(update_fields=["details"])

        response = self.send_api_request(
            url=f"/api/pages/{self.page.external_id}/rewind/{original.external_id}/restore/",
            method="post",
        )
        data = response.json()

        self.assertEqual(data["lines_added"], 0)
        self.assertEqual(data["lines_deleted"], 0)

    def test_restore_from_empty_to_content(self):
        """Restoring content when current page is empty."""
        original = self._create_rewind("line1\nline2\nline3")
        self._create_rewind_backdated("")

        # Ensure page details reflect empty content
        self.page.refresh_from_db()
        self.page.details["content"] = ""
        self.page.save(update_fields=["details"])

        response = self.send_api_request(
            url=f"/api/pages/{self.page.external_id}/rewind/{original.external_id}/restore/",
            method="post",
        )
        data = response.json()

        self.assertEqual(data["lines_added"], 3)
        self.assertEqual(data["lines_deleted"], 0)

    def test_restore_from_content_to_empty(self):
        """Restoring to an empty rewind when page has content."""
        empty_rewind = self._create_rewind("")
        self._create_rewind_backdated("line1\nline2\nline3")

        # Ensure page has current content
        self.page.refresh_from_db()
        self.page.details["content"] = "line1\nline2\nline3"
        self.page.save(update_fields=["details"])

        response = self.send_api_request(
            url=f"/api/pages/{self.page.external_id}/rewind/{empty_rewind.external_id}/restore/",
            method="post",
        )
        data = response.json()

        self.assertEqual(data["lines_added"], 0)
        self.assertEqual(data["lines_deleted"], 3)


class TestRestoreUpdatesPageDetails(RewindAPITestBase):
    """Verify restore side-effects: page details, rewind number, CRDT cleanup, permissions."""

    def test_restore_updates_page_content_and_hash(self):
        """After restore, page.details should reflect the restored content."""
        original = self._create_rewind("original content")
        self._create_rewind_backdated("changed content")

        self.page.details["content"] = "changed content"
        self.page.save(update_fields=["details"])

        self.send_api_request(
            url=f"/api/pages/{self.page.external_id}/rewind/{original.external_id}/restore/",
            method="post",
        )

        self.page.refresh_from_db()
        self.assertEqual(self.page.details["content"], "original content")
        self.assertEqual(self.page.details["content_hash"], hashify("original content"))

    def test_restore_increments_current_rewind_number(self):
        """Restore creates a new rewind, so current_rewind_number should increase by 1."""
        original = self._create_rewind("v1 content")
        self._create_rewind_backdated("v2 content")

        self.page.details["content"] = "v2 content"
        self.page.save(update_fields=["details"])

        self.page.refresh_from_db()
        rewind_number_before = self.page.current_rewind_number

        self.send_api_request(
            url=f"/api/pages/{self.page.external_id}/rewind/{original.external_id}/restore/",
            method="post",
        )

        self.page.refresh_from_db()
        self.assertEqual(self.page.current_rewind_number, rewind_number_before + 1)

    @patch("pages.api.rewind._disconnect_ws_clients")
    def test_restore_clears_crdt_state(self, mock_disconnect):
        """Restore should delete all YUpdate and YSnapshot records for the page's room."""
        original = self._create_rewind("v1 content")
        self._create_rewind_backdated("v2 content")

        self.page.details["content"] = "v2 content"
        self.page.save(update_fields=["details"])

        room_id = f"page_{self.page.external_id}"
        YUpdate.objects.create(room_id=room_id, yupdate=b"\x00")
        YSnapshot.objects.create(room_id=room_id, snapshot=b"\x00", last_update_id=1)

        self.assertEqual(YUpdate.objects.filter(room_id=room_id).count(), 1)
        self.assertEqual(YSnapshot.objects.filter(room_id=room_id).count(), 1)

        self.send_api_request(
            url=f"/api/pages/{self.page.external_id}/rewind/{original.external_id}/restore/",
            method="post",
        )

        self.assertEqual(YUpdate.objects.filter(room_id=room_id).count(), 0)
        self.assertEqual(YSnapshot.objects.filter(room_id=room_id).count(), 0)

    def test_viewer_cannot_restore(self):
        """A user with viewer role on the page should not be able to restore."""
        viewer = UserFactory()
        PageEditorFactory(user=viewer, page=self.page, role=PageEditorRole.VIEWER.value)

        original = self._create_rewind("content")

        self.login(viewer)
        response = self.send_api_request(
            url=f"/api/pages/{self.page.external_id}/rewind/{original.external_id}/restore/",
            method="post",
        )
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)


class TestLineDiffFullLifecycle(RewindAPITestBase):
    """Integration test: create multiple rewinds and verify diff stats across list."""

    @override_settings(REWIND_MIN_INTERVAL_SECONDS=0)
    def test_three_rewinds_each_with_correct_diff(self):
        """Create 3 rewinds and verify each has correct diff relative to its predecessor."""
        # v1: 2 lines from nothing
        self._create_rewind("a\nb")
        # v2: add 1 line
        self._create_rewind_backdated("a\nb\nc")
        # v3: replace 'c' with 'x', add 'd'
        self._create_rewind_backdated("a\nb\nx\nd")

        response = self.send_api_request(url=f"/api/pages/{self.page.external_id}/rewind/")
        items = response.json()["items"]  # ordered desc: v3, v2, v1

        # v3: compared to v2 ("a\nb\nc" → "a\nb\nx\nd") → +2 -1
        self.assertEqual(items[0]["rewind_number"], 3)
        self.assertEqual(items[0]["lines_added"], 2)
        self.assertEqual(items[0]["lines_deleted"], 1)

        # v2: compared to v1 ("a\nb" → "a\nb\nc") → +1 -0
        self.assertEqual(items[1]["rewind_number"], 2)
        self.assertEqual(items[1]["lines_added"], 1)
        self.assertEqual(items[1]["lines_deleted"], 0)

        # v1: first rewind ("" → "a\nb") → +2 -0
        self.assertEqual(items[2]["rewind_number"], 1)
        self.assertEqual(items[2]["lines_added"], 2)
        self.assertEqual(items[2]["lines_deleted"], 0)
