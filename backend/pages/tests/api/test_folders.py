from http import HTTPStatus
from unittest.mock import patch

from django.test import override_settings

from core.tests.common import BaseAuthenticatedViewTestCase
from pages.constants import ProjectEditorRole
from pages.models import Folder, Page
from pages.tests.factories import FolderFactory, PageFactory, ProjectEditorFactory, ProjectFactory
from users.constants import OrgMemberRole
from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory, TEST_USER_PASSWORD

_SENTINEL = object()


class TestFolderCreateAPI(BaseAuthenticatedViewTestCase):
    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def send_create_request(self, name, parent_id=None):
        data = {"name": name}
        if parent_id is not None:
            data["parent_id"] = parent_id
        return self.send_api_request(
            url=f"/api/projects/{self.project.external_id}/folders/",
            method="post",
            data=data,
        )

    def test_create_root_folder_succeeds(self):
        response = self.send_create_request("Design")
        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        payload = response.json()
        self.assertEqual(payload["name"], "Design")
        self.assertIsNone(payload["parent_id"])
        self.assertIn("external_id", payload)

        folder = Folder.objects.get(external_id=payload["external_id"])
        self.assertEqual(folder.name, "Design")
        self.assertIsNone(folder.parent_id)
        self.assertEqual(folder.project, self.project)

    def test_create_nested_folder_succeeds(self):
        parent = FolderFactory(project=self.project, parent=None, name="Design")
        response = self.send_create_request("Wireframes", parent_id=str(parent.external_id))
        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        payload = response.json()
        self.assertEqual(payload["name"], "Wireframes")
        self.assertEqual(payload["parent_id"], str(parent.external_id))

        folder = Folder.objects.get(external_id=payload["external_id"])
        self.assertEqual(folder.parent, parent)

    def test_create_folder_strips_whitespace(self):
        response = self.send_create_request("  Design  ")
        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        payload = response.json()
        self.assertEqual(payload["name"], "Design")

    def test_create_folder_empty_name_returns_422(self):
        response = self.send_create_request("")
        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)

    def test_create_folder_whitespace_only_name_returns_422(self):
        response = self.send_create_request("   ")
        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)

    def test_create_folder_forbidden_chars_returns_422(self):
        response = self.send_create_request("Design/Notes")
        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)

    def test_create_folder_backslash_returns_422(self):
        response = self.send_create_request("Design\\Notes")
        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)

    def test_create_folder_duplicate_name_same_parent_returns_409(self):
        FolderFactory(project=self.project, parent=None, name="Design")
        response = self.send_create_request("Design")
        self.assertEqual(response.status_code, HTTPStatus.CONFLICT)
        payload = response.json()
        self.assertIn("duplicate_name", payload.get("code", ""))

    def test_create_folder_duplicate_name_different_parent_succeeds(self):
        parent1 = FolderFactory(project=self.project, parent=None, name="Design")
        FolderFactory(project=self.project, parent=parent1, name="Notes")
        parent2 = FolderFactory(project=self.project, parent=None, name="Engineering")
        response = self.send_create_request("Notes", parent_id=str(parent2.external_id))
        self.assertEqual(response.status_code, HTTPStatus.CREATED)

    def test_create_folder_parent_not_found_returns_404(self):
        response = self.send_create_request("Sub", parent_id="fld_nonexistent")
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_create_folder_parent_from_other_project_returns_404(self):
        other_project = ProjectFactory(org=OrgFactory())
        other_folder = FolderFactory(project=other_project, parent=None, name="Other")
        response = self.send_create_request("Sub", parent_id=str(other_folder.external_id))
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_create_folder_depth_limit_returns_400(self):
        parent = None
        for i in range(10):
            parent = FolderFactory(project=self.project, parent=parent, name=f"Level{i}")
        response = self.send_create_request("TooDeep", parent_id=str(parent.external_id))
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        payload = response.json()
        self.assertIn("depth_limit_exceeded", payload.get("code", ""))

    def test_create_folder_at_exact_depth_limit_succeeds(self):
        """Creating a folder at exactly depth 10 should succeed."""
        parent = None
        for i in range(9):
            parent = FolderFactory(project=self.project, parent=parent, name=f"Level{i}")
        response = self.send_create_request("Level9", parent_id=str(parent.external_id))
        self.assertEqual(response.status_code, HTTPStatus.CREATED)

    @patch("pages.api.folders.MAX_FOLDERS_PER_PROJECT", 3)
    def test_create_folder_limit_reached_returns_400(self):
        for i in range(3):
            FolderFactory(project=self.project, parent=None, name=f"Folder{i}")
        response = self.send_create_request("OneMore")
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        payload = response.json()
        self.assertIn("folder_limit_reached", payload.get("code", ""))

    def test_create_folder_project_not_found_returns_404(self):
        response = self.send_api_request(
            url="/api/projects/proj_nonexistent/folders/",
            method="post",
            data={"name": "Design"},
        )
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_create_folder_no_edit_permission_returns_403(self):
        viewer = UserFactory()
        ProjectEditorFactory(project=self.project, user=viewer, role=ProjectEditorRole.VIEWER.value)
        self.client.logout()
        self.client.login(email=viewer.email, password=TEST_USER_PASSWORD)
        response = self.send_create_request("Design")
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    def test_create_folder_unauthenticated_returns_401(self):
        self.client.logout()
        response = self.send_create_request("Design")
        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)

    @override_settings(WS_FOLDERS_RATE_LIMIT_REQUESTS=1, WS_FOLDERS_RATE_LIMIT_WINDOW_SECONDS=60)
    def test_create_folder_rate_limited_returns_429(self):
        self.send_create_request("First")
        response = self.send_create_request("Second")
        self.assertEqual(response.status_code, HTTPStatus.TOO_MANY_REQUESTS)


class TestFolderGetAPI(BaseAuthenticatedViewTestCase):
    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def test_get_folder_succeeds(self):
        folder = FolderFactory(project=self.project, parent=None, name="Design")
        response = self.send_api_request(
            url=f"/api/projects/{self.project.external_id}/folders/{folder.external_id}/",
            method="get",
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        payload = response.json()
        self.assertEqual(payload["external_id"], str(folder.external_id))
        self.assertEqual(payload["name"], "Design")
        self.assertIsNone(payload["parent_id"])

    def test_get_nested_folder_includes_parent_id(self):
        parent = FolderFactory(project=self.project, parent=None, name="Design")
        child = FolderFactory(project=self.project, parent=parent, name="Wireframes")
        response = self.send_api_request(
            url=f"/api/projects/{self.project.external_id}/folders/{child.external_id}/",
            method="get",
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        payload = response.json()
        self.assertEqual(payload["parent_id"], str(parent.external_id))

    def test_get_folder_not_found_returns_404(self):
        response = self.send_api_request(
            url=f"/api/projects/{self.project.external_id}/folders/fld_nonexistent/",
            method="get",
        )
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_get_folder_wrong_project_returns_404(self):
        """A folder from another project should not be accessible."""
        other_org = OrgFactory()
        OrgMemberFactory(org=other_org, user=self.user, role=OrgMemberRole.MEMBER.value)
        other_project = ProjectFactory(org=other_org, creator=self.user)
        folder = FolderFactory(project=other_project, parent=None, name="Design")
        response = self.send_api_request(
            url=f"/api/projects/{self.project.external_id}/folders/{folder.external_id}/",
            method="get",
        )
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_get_folder_inaccessible_project_returns_404(self):
        """User without project access gets 404."""
        other_project = ProjectFactory(org=OrgFactory())
        folder = FolderFactory(project=other_project, parent=None, name="Design")
        response = self.send_api_request(
            url=f"/api/projects/{other_project.external_id}/folders/{folder.external_id}/",
            method="get",
        )
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)


class TestFolderUpdateAPI(BaseAuthenticatedViewTestCase):
    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def send_update_request(self, folder_id, name=_SENTINEL, parent_id=_SENTINEL):
        """Send a PATCH request. Use _SENTINEL to omit fields, None to send null."""
        data = {}
        if name is not _SENTINEL:
            data["name"] = name
        if parent_id is not _SENTINEL:
            data["parent_id"] = parent_id
        return self.send_api_request(
            url=f"/api/projects/{self.project.external_id}/folders/{folder_id}/",
            method="patch",
            data=data,
        )

    def test_rename_folder_succeeds(self):
        folder = FolderFactory(project=self.project, parent=None, name="Design")
        response = self.send_update_request(str(folder.external_id), name="Visual")
        self.assertEqual(response.status_code, HTTPStatus.OK)
        payload = response.json()
        self.assertEqual(payload["name"], "Visual")

        folder.refresh_from_db()
        self.assertEqual(folder.name, "Visual")

    def test_rename_folder_empty_name_returns_422(self):
        folder = FolderFactory(project=self.project, parent=None, name="Design")
        response = self.send_update_request(str(folder.external_id), name="")
        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)

    def test_rename_folder_forbidden_chars_returns_422(self):
        folder = FolderFactory(project=self.project, parent=None, name="Design")
        response = self.send_update_request(str(folder.external_id), name="A/B")
        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)

    def test_rename_to_duplicate_name_returns_409(self):
        FolderFactory(project=self.project, parent=None, name="Design")
        other = FolderFactory(project=self.project, parent=None, name="Engineering")
        response = self.send_update_request(str(other.external_id), name="Design")
        self.assertEqual(response.status_code, HTTPStatus.CONFLICT)
        payload = response.json()
        self.assertIn("duplicate_name", payload.get("code", ""))

    def test_move_folder_to_root_succeeds(self):
        parent = FolderFactory(project=self.project, parent=None, name="Design")
        child = FolderFactory(project=self.project, parent=parent, name="Wireframes")
        response = self.send_update_request(str(child.external_id), parent_id=None)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        payload = response.json()
        self.assertIsNone(payload["parent_id"])

        child.refresh_from_db()
        self.assertIsNone(child.parent_id)

    def test_move_folder_to_other_parent_succeeds(self):
        design = FolderFactory(project=self.project, parent=None, name="Design")
        engineering = FolderFactory(project=self.project, parent=None, name="Engineering")
        wireframes = FolderFactory(project=self.project, parent=design, name="Wireframes")
        response = self.send_update_request(
            str(wireframes.external_id),
            parent_id=str(engineering.external_id),
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)

        wireframes.refresh_from_db()
        self.assertEqual(wireframes.parent, engineering)

    def test_move_folder_creates_cycle_returns_400(self):
        parent = FolderFactory(project=self.project, parent=None, name="Design")
        child = FolderFactory(project=self.project, parent=parent, name="Wireframes")
        response = self.send_update_request(
            str(parent.external_id),
            parent_id=str(child.external_id),
        )
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        payload = response.json()
        self.assertIn("cycle_detected", payload.get("code", ""))

    def test_move_folder_into_grandchild_returns_400(self):
        """Cycle detection should catch indirect descendants too."""
        a = FolderFactory(project=self.project, parent=None, name="A")
        b = FolderFactory(project=self.project, parent=a, name="B")
        c = FolderFactory(project=self.project, parent=b, name="C")
        response = self.send_update_request(str(a.external_id), parent_id=str(c.external_id))
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIn("cycle_detected", response.json().get("code", ""))

    def test_move_folder_depth_limit_exceeded_returns_400(self):
        """Moving a subtree that would exceed depth 10 is rejected."""
        # Build chain of 8: root -> L1 -> ... -> L7
        chain = [FolderFactory(project=self.project, parent=None, name="Root")]
        for i in range(7):
            chain.append(FolderFactory(project=self.project, parent=chain[-1], name=f"L{i+1}"))
        # Build a separate chain of 3: A -> B -> C
        a = FolderFactory(project=self.project, parent=None, name="A")
        b = FolderFactory(project=self.project, parent=a, name="B")
        FolderFactory(project=self.project, parent=b, name="C")
        # Move A under L7 → would make depth 8 + 3 = 11 > 10
        response = self.send_update_request(str(a.external_id), parent_id=str(chain[-1].external_id))
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIn("depth_limit_exceeded", response.json().get("code", ""))

    def test_rename_and_move_in_same_request_succeeds(self):
        design = FolderFactory(project=self.project, parent=None, name="Design")
        engineering = FolderFactory(project=self.project, parent=None, name="Engineering")
        wireframes = FolderFactory(project=self.project, parent=design, name="Wireframes")
        response = self.send_update_request(
            str(wireframes.external_id),
            name="Specs",
            parent_id=str(engineering.external_id),
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        payload = response.json()
        self.assertEqual(payload["name"], "Specs")
        self.assertEqual(payload["parent_id"], str(engineering.external_id))

    def test_update_without_parent_id_does_not_move(self):
        parent = FolderFactory(project=self.project, parent=None, name="Design")
        child = FolderFactory(project=self.project, parent=parent, name="Wireframes")
        response = self.send_update_request(str(child.external_id), name="Specs")
        self.assertEqual(response.status_code, HTTPStatus.OK)
        child.refresh_from_db()
        self.assertEqual(child.parent, parent)

    def test_move_to_same_parent_is_noop(self):
        """Moving a folder to its current parent shouldn't error."""
        parent = FolderFactory(project=self.project, parent=None, name="Design")
        child = FolderFactory(project=self.project, parent=parent, name="Wireframes")
        response = self.send_update_request(
            str(child.external_id),
            parent_id=str(parent.external_id),
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        child.refresh_from_db()
        self.assertEqual(child.parent, parent)

    def test_move_to_nonexistent_parent_returns_404(self):
        folder = FolderFactory(project=self.project, parent=None, name="Design")
        response = self.send_update_request(str(folder.external_id), parent_id="fld_nonexistent")
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_update_folder_not_found_returns_404(self):
        response = self.send_update_request("fld_nonexistent", name="New")
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_update_folder_no_edit_permission_returns_403(self):
        folder = FolderFactory(project=self.project, parent=None, name="Design")
        viewer = UserFactory()
        ProjectEditorFactory(project=self.project, user=viewer, role=ProjectEditorRole.VIEWER.value)
        self.client.logout()
        self.client.login(email=viewer.email, password=TEST_USER_PASSWORD)
        response = self.send_update_request(str(folder.external_id), name="New")
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    def test_update_folder_unauthenticated_returns_401(self):
        folder = FolderFactory(project=self.project, parent=None, name="Design")
        self.client.logout()
        response = self.send_update_request(str(folder.external_id), name="New")
        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)


class TestFolderDeleteAPI(BaseAuthenticatedViewTestCase):
    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def send_delete_request(self, folder_external_id):
        return self.send_api_request(
            url=f"/api/projects/{self.project.external_id}/folders/{folder_external_id}/",
            method="delete",
        )

    def test_delete_empty_folder_succeeds(self):
        folder = FolderFactory(project=self.project, parent=None, name="Design")
        response = self.send_delete_request(str(folder.external_id))
        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)
        self.assertFalse(Folder.objects.filter(id=folder.id).exists())

    def test_delete_folder_with_pages_returns_409(self):
        folder = FolderFactory(project=self.project, parent=None, name="Design")
        PageFactory(project=self.project, folder=folder, creator=self.user, title="Page")
        response = self.send_delete_request(str(folder.external_id))
        self.assertEqual(response.status_code, HTTPStatus.CONFLICT)
        payload = response.json()
        self.assertIn("folder_not_empty", payload.get("code", ""))
        self.assertTrue(Folder.objects.filter(id=folder.id).exists())

    def test_delete_folder_with_only_soft_deleted_pages_succeeds(self):
        """Soft-deleted pages should not block folder deletion."""
        folder = FolderFactory(project=self.project, parent=None, name="Design")
        page = PageFactory(project=self.project, folder=folder, creator=self.user, title="Page")
        page.is_deleted = True
        page.save(update_fields=["is_deleted"])
        response = self.send_delete_request(str(folder.external_id))
        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)

    def test_delete_folder_with_subfolders_returns_409(self):
        parent = FolderFactory(project=self.project, parent=None, name="Design")
        FolderFactory(project=self.project, parent=parent, name="Wireframes")
        response = self.send_delete_request(str(parent.external_id))
        self.assertEqual(response.status_code, HTTPStatus.CONFLICT)
        self.assertTrue(Folder.objects.filter(id=parent.id).exists())

    def test_delete_folder_not_found_returns_404(self):
        response = self.send_delete_request("fld_nonexistent")
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_delete_folder_no_edit_permission_returns_403(self):
        folder = FolderFactory(project=self.project, parent=None, name="Design")
        viewer = UserFactory()
        ProjectEditorFactory(project=self.project, user=viewer, role=ProjectEditorRole.VIEWER.value)
        self.client.logout()
        self.client.login(email=viewer.email, password=TEST_USER_PASSWORD)
        response = self.send_delete_request(str(folder.external_id))
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    def test_delete_folder_unauthenticated_returns_401(self):
        folder = FolderFactory(project=self.project, parent=None, name="Design")
        self.client.logout()
        response = self.send_delete_request(str(folder.external_id))
        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)


class TestBulkMovePagesAPI(BaseAuthenticatedViewTestCase):
    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def send_move_request(self, page_ids, folder_id=_SENTINEL):
        """Send a bulk move request. Use _SENTINEL to omit folder_id (moves to root)."""
        data = {"page_ids": page_ids}
        if folder_id is not _SENTINEL:
            data["folder_id"] = folder_id
        return self.send_api_request(
            url=f"/api/projects/{self.project.external_id}/folders/move-pages/",
            method="post",
            data=data,
        )

    def test_move_pages_to_folder_succeeds(self):
        folder = FolderFactory(project=self.project, parent=None, name="Design")
        page1 = PageFactory(project=self.project, creator=self.user, title="Page 1", folder=None)
        page2 = PageFactory(project=self.project, creator=self.user, title="Page 2", folder=None)
        response = self.send_move_request(
            [str(page1.external_id), str(page2.external_id)],
            folder_id=str(folder.external_id),
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        payload = response.json()
        self.assertEqual(payload["moved"], 2)

        page1.refresh_from_db()
        page2.refresh_from_db()
        self.assertEqual(page1.folder, folder)
        self.assertEqual(page2.folder, folder)

    def test_move_pages_to_root_succeeds(self):
        folder = FolderFactory(project=self.project, parent=None, name="Design")
        page = PageFactory(project=self.project, creator=self.user, title="Page", folder=folder)
        response = self.send_move_request([str(page.external_id)], folder_id=None)
        self.assertEqual(response.status_code, HTTPStatus.OK)

        page.refresh_from_db()
        self.assertIsNone(page.folder_id)

    def test_move_pages_to_root_omitting_folder_id_succeeds(self):
        """When folder_id is not in the body at all, schema defaults to None (root)."""
        folder = FolderFactory(project=self.project, parent=None, name="Design")
        page = PageFactory(project=self.project, creator=self.user, title="Page", folder=folder)
        response = self.send_move_request([str(page.external_id)])
        self.assertEqual(response.status_code, HTTPStatus.OK)

        page.refresh_from_db()
        self.assertIsNone(page.folder_id)

    def test_move_pages_not_found_returns_400(self):
        response = self.send_move_request(["pg_nonexistent"])
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        payload = response.json()
        self.assertIn("pages_not_found", payload.get("code", ""))

    def test_move_pages_partial_not_found_returns_400(self):
        """If some page IDs are valid and some aren't, the entire request fails."""
        page = PageFactory(project=self.project, creator=self.user, title="Page")
        response = self.send_move_request([str(page.external_id), "pg_nonexistent"])
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)

        # Verify nothing was moved
        page.refresh_from_db()
        self.assertIsNone(page.folder_id)

    def test_move_pages_target_folder_not_found_returns_404(self):
        page = PageFactory(project=self.project, creator=self.user, title="Page")
        response = self.send_move_request(
            [str(page.external_id)],
            folder_id="fld_nonexistent",
        )
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_move_pages_target_folder_from_other_project_returns_404(self):
        other_project = ProjectFactory(org=OrgFactory())
        other_folder = FolderFactory(project=other_project, parent=None, name="Other")
        page = PageFactory(project=self.project, creator=self.user, title="Page")
        response = self.send_move_request(
            [str(page.external_id)],
            folder_id=str(other_folder.external_id),
        )
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_move_pages_no_edit_permission_returns_403(self):
        page = PageFactory(project=self.project, creator=self.user, title="Page")
        viewer = UserFactory()
        ProjectEditorFactory(project=self.project, user=viewer, role=ProjectEditorRole.VIEWER.value)
        self.client.logout()
        self.client.login(email=viewer.email, password=TEST_USER_PASSWORD)
        response = self.send_move_request([str(page.external_id)])
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    def test_move_pages_unauthenticated_returns_401(self):
        page = PageFactory(project=self.project, creator=self.user, title="Page")
        self.client.logout()
        response = self.send_move_request([str(page.external_id)])
        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)

    def test_move_pages_from_other_project_returns_400(self):
        """Pages belonging to a different project should not be movable."""
        other_org = OrgFactory()
        OrgMemberFactory(org=other_org, user=self.user, role=OrgMemberRole.MEMBER.value)
        other_project = ProjectFactory(org=other_org, creator=self.user)
        page = PageFactory(project=other_project, creator=self.user, title="Other Page")
        response = self.send_move_request([str(page.external_id)])
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)

    @override_settings(WS_FOLDERS_BULK_MOVE_MAX_PAGES=2)
    def test_move_too_many_pages_returns_400(self):
        """Exceeding the bulk move limit returns 400 with too_many_pages code."""
        pages = [PageFactory(project=self.project, creator=self.user, title=f"Page {i}") for i in range(3)]
        response = self.send_move_request([str(p.external_id) for p in pages])
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        payload = response.json()
        self.assertIn("too_many_pages", payload.get("code", ""))

    @override_settings(WS_FOLDERS_BULK_MOVE_MAX_PAGES=2)
    def test_move_at_exact_limit_succeeds(self):
        """Moving exactly the max number of pages succeeds."""
        pages = [PageFactory(project=self.project, creator=self.user, title=f"Page {i}") for i in range(2)]
        response = self.send_move_request([str(p.external_id) for p in pages])
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_move_empty_page_ids_returns_422(self):
        """Sending an empty page_ids list is rejected by schema validation."""
        response = self.send_move_request([])
        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)


class TestConcurrentFolderCreation(BaseAuthenticatedViewTestCase):
    """Tests for concurrent folder creation and unique constraint handling."""

    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def test_duplicate_root_folder_name_returns_409_on_db_constraint(self):
        """
        If two concurrent requests try to create the same root folder name,
        the unique constraint should prevent duplicates. The second request
        should return 409 (duplicate_name) from the application-level check.
        """
        # Create first folder
        response1 = self.send_api_request(
            url=f"/api/projects/{self.project.external_id}/folders/",
            method="post",
            data={"name": "Design"},
        )
        self.assertEqual(response1.status_code, HTTPStatus.CREATED)

        # Try to create the same folder again — should get 409
        response2 = self.send_api_request(
            url=f"/api/projects/{self.project.external_id}/folders/",
            method="post",
            data={"name": "Design"},
        )
        self.assertEqual(response2.status_code, HTTPStatus.CONFLICT)
        self.assertIn("duplicate_name", response2.json().get("code", ""))

    def test_duplicate_nested_folder_name_returns_409(self):
        """
        Duplicate folder names under the same parent should be caught by the
        unique constraint (project, parent, name).
        """
        parent = FolderFactory(project=self.project, parent=None, name="Design")

        response1 = self.send_api_request(
            url=f"/api/projects/{self.project.external_id}/folders/",
            method="post",
            data={"name": "Wireframes", "parent_id": str(parent.external_id)},
        )
        self.assertEqual(response1.status_code, HTTPStatus.CREATED)

        response2 = self.send_api_request(
            url=f"/api/projects/{self.project.external_id}/folders/",
            method="post",
            data={"name": "Wireframes", "parent_id": str(parent.external_id)},
        )
        self.assertEqual(response2.status_code, HTTPStatus.CONFLICT)

    def test_same_name_different_projects_both_succeed(self):
        """Two folders with the same name in different projects should both succeed."""
        other_org = OrgFactory()
        OrgMemberFactory(org=other_org, user=self.user, role=OrgMemberRole.MEMBER.value)
        other_project = ProjectFactory(org=other_org, creator=self.user)

        response1 = self.send_api_request(
            url=f"/api/projects/{self.project.external_id}/folders/",
            method="post",
            data={"name": "Design"},
        )
        self.assertEqual(response1.status_code, HTTPStatus.CREATED)

        response2 = self.send_api_request(
            url=f"/api/projects/{other_project.external_id}/folders/",
            method="post",
            data={"name": "Design"},
        )
        self.assertEqual(response2.status_code, HTTPStatus.CREATED)

    def test_db_integrity_error_caught_on_race_condition(self):
        """
        The create_folder endpoint wraps Folder.objects.create() in a
        try/except IntegrityError block. Verify that a race condition
        (duplicate detected at DB level but not at app level) returns 409.
        """
        from django.db import IntegrityError

        # Simulate: app-level check passes, but DB constraint fires
        original_create = Folder.objects.create

        def create_that_raises_integrity(**kwargs):
            raise IntegrityError("duplicate key value violates unique constraint")

        # First create normally to verify setup works
        response1 = self.send_api_request(
            url=f"/api/projects/{self.project.external_id}/folders/",
            method="post",
            data={"name": "Design"},
        )
        self.assertEqual(response1.status_code, HTTPStatus.CREATED)

        # Delete the folder so app-level check passes, but patch create to raise
        Folder.objects.filter(project=self.project).delete()

        with patch.object(Folder.objects, "create", side_effect=create_that_raises_integrity):
            response2 = self.send_api_request(
                url=f"/api/projects/{self.project.external_id}/folders/",
                method="post",
                data={"name": "Design"},
            )
        # The IntegrityError is caught and returns 409
        self.assertEqual(response2.status_code, HTTPStatus.CONFLICT)
        self.assertIn("duplicate_name", response2.json().get("code", ""))
