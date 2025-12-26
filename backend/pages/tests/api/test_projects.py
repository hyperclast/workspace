from http import HTTPStatus

from core.tests.common import BaseAuthenticatedViewTestCase
from pages.models import Project
from pages.tests.factories import PageFactory, ProjectFactory
from users.constants import OrgMemberRole
from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory


class TestProjectsAPI(BaseAuthenticatedViewTestCase):
    """Test project API endpoints."""

    def setUp(self):
        super().setUp()
        # Create org and add self.user as member
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)

    def test_list_projects_all_orgs(self):
        """User should see all projects from all their orgs."""
        # Create two projects in the org
        project1 = ProjectFactory(org=self.org)
        project2 = ProjectFactory(org=self.org)

        # Create project in different org (should not be visible)
        other_org = OrgFactory()
        ProjectFactory(org=other_org)

        response = self.send_api_request(url="/api/projects/", method="get")

        # Debug output
        if response.status_code != HTTPStatus.OK:
            print(f"\nStatus: {response.status_code}")
            print(f"Response: {response.content.decode()}\n")

        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(len(payload), 2)

        # Check that our projects are included
        project_ids = [p["external_id"] for p in payload]
        self.assertIn(project1.external_id, project_ids)
        self.assertIn(project2.external_id, project_ids)

        # Verify new schema structure
        project = payload[0]
        self.assertIn("external_id", project)
        self.assertIn("name", project)
        self.assertIn("description", project)
        self.assertIn("version", project)
        self.assertIn("created", project)
        self.assertIn("modified", project)
        self.assertIn("creator", project)
        self.assertIn("org", project)
        self.assertIsNone(project["pages"])  # Should be None without details=full

        # Verify creator structure
        self.assertIn("external_id", project["creator"])
        self.assertIn("email", project["creator"])

        # Verify org structure
        self.assertIn("external_id", project["org"])
        self.assertIn("name", project["org"])
        self.assertIn("domain", project["org"])

    def test_list_projects_filtered_by_org(self):
        """User can filter projects by org_id query param."""
        project1 = ProjectFactory(org=self.org)

        # Create another org and project
        org2 = OrgFactory()
        OrgMemberFactory(org=org2, user=self.user)
        project2 = ProjectFactory(org=org2)

        # Filter by org1
        response = self.send_api_request(url=f"/api/projects/?org_id={self.org.external_id}", method="get")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["external_id"], project1.external_id)

    def test_list_projects_with_pages_detail(self):
        """When details=full, projects should include pages list."""
        project = ProjectFactory(org=self.org)
        page1 = PageFactory(project=project, title="Page 1", creator=self.user)
        page2 = PageFactory(project=project, title="Page 2", creator=self.user)

        response = self.send_api_request(url="/api/projects/?details=full", method="get")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(len(payload), 1)

        project_data = payload[0]
        self.assertIsNotNone(project_data["pages"])
        self.assertEqual(len(project_data["pages"]), 2)

        # Verify page structure
        page = project_data["pages"][0]
        self.assertIn("external_id", page)
        self.assertIn("title", page)
        self.assertIn("updated", page)
        self.assertIn("modified", page)
        self.assertIn("created", page)

        # Verify page titles
        page_titles = [p["title"] for p in project_data["pages"]]
        self.assertIn("Page 1", page_titles)
        self.assertIn("Page 2", page_titles)

    def test_list_projects_without_pages_detail(self):
        """Without details=full, pages should be None."""
        project = ProjectFactory(org=self.org)
        PageFactory(project=project, creator=self.user)

        response = self.send_api_request(url="/api/projects/", method="get")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        project_data = payload[0]
        self.assertIsNone(project_data["pages"])

    def test_list_projects_excludes_deleted(self):
        """Soft-deleted projects should not appear in list."""
        active_project = ProjectFactory(org=self.org, is_deleted=False)
        deleted_project = ProjectFactory(org=self.org, is_deleted=True)

        response = self.send_api_request(url="/api/projects/", method="get")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        project_ids = [p["external_id"] for p in payload]
        self.assertIn(active_project.external_id, project_ids)
        self.assertNotIn(deleted_project.external_id, project_ids)

    def test_get_project_details(self):
        """User should be able to get project details."""
        project = ProjectFactory(org=self.org, name="Test Project", description="Test Description")

        response = self.send_api_request(url=f"/api/projects/{project.external_id}/", method="get")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(payload["external_id"], project.external_id)
        self.assertEqual(payload["name"], "Test Project")
        self.assertEqual(payload["description"], "Test Description")
        self.assertIn("version", payload)
        self.assertIn("created", payload)
        self.assertIn("modified", payload)
        self.assertIn("creator", payload)
        self.assertIn("org", payload)
        self.assertIsNone(payload["pages"])

    def test_get_project_with_pages(self):
        """Get project with details=full should include pages."""
        project = ProjectFactory(org=self.org)
        PageFactory(project=project, title="Test Page", creator=self.user)

        response = self.send_api_request(url=f"/api/projects/{project.external_id}/?details=full", method="get")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIsNotNone(payload["pages"])
        self.assertEqual(len(payload["pages"]), 1)
        self.assertEqual(payload["pages"][0]["title"], "Test Page")

    def test_get_project_requires_org_membership(self):
        """Cannot get project details if not org member."""
        other_org = OrgFactory()
        project = ProjectFactory(org=other_org)

        response = self.send_api_request(url=f"/api/projects/{project.external_id}/", method="get")

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_get_deleted_project_returns_404(self):
        """Cannot get soft-deleted projects."""
        project = ProjectFactory(org=self.org, is_deleted=True)

        response = self.send_api_request(url=f"/api/projects/{project.external_id}/", method="get")

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_create_project_in_org(self):
        """User can create project in org they belong to."""
        projects_before = Project.objects.filter(org=self.org).count()

        response = self.send_api_request(
            url="/api/projects/",
            method="post",
            data={"org_id": self.org.external_id, "name": "New Project", "description": "Project description"},
        )
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        self.assertEqual(payload["name"], "New Project")
        self.assertEqual(payload["description"], "Project description")
        self.assertIn("external_id", payload)

        # Verify project was created
        self.assertEqual(Project.objects.filter(org=self.org).count(), projects_before + 1)
        project = Project.objects.get(external_id=payload["external_id"])
        self.assertEqual(project.name, "New Project")
        self.assertEqual(project.creator, self.user)
        self.assertEqual(project.org, self.org)

    def test_create_project_without_description(self):
        """Can create project without description (defaults to empty string)."""
        response = self.send_api_request(
            url="/api/projects/", method="post", data={"org_id": self.org.external_id, "name": "New Project"}
        )
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        self.assertEqual(payload["description"], "")

    def test_create_project_with_empty_name_returns_422(self):
        """Creating project with empty name should fail."""
        response = self.send_api_request(
            url="/api/projects/", method="post", data={"org_id": self.org.external_id, "name": ""}
        )

        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)

    def test_create_project_with_long_name_returns_422(self):
        """Creating project with name longer than 255 chars should fail."""
        response = self.send_api_request(
            url="/api/projects/", method="post", data={"org_id": self.org.external_id, "name": "a" * 256}
        )

        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)

    def test_create_project_with_invalid_chars_returns_422(self):
        """Creating project with invalid filename characters should fail."""
        invalid_names = [
            "Project/Name",
            "Project\\Name",
            "Project:Name",
            "Project*Name",
            "Project?Name",
            'Project"Name',
            "Project<Name",
            "Project>Name",
            "Project|Name",
        ]
        for name in invalid_names:
            response = self.send_api_request(
                url="/api/projects/", method="post", data={"org_id": self.org.external_id, "name": name}
            )
            self.assertEqual(
                response.status_code,
                HTTPStatus.UNPROCESSABLE_ENTITY,
                f"Expected 422 for name with invalid char: {name}",
            )

    def test_create_project_with_valid_special_chars(self):
        """Project names can contain some special characters like dash and underscore."""
        valid_names = [
            "Project-Name",
            "Project_Name",
            "Project Name",
            "Project.Name",
            "Project (2024)",
            "日本語プロジェクト",
            "Project 🚀",
        ]
        for name in valid_names:
            response = self.send_api_request(
                url="/api/projects/", method="post", data={"org_id": self.org.external_id, "name": name}
            )
            self.assertEqual(
                response.status_code,
                HTTPStatus.CREATED,
                f"Expected 201 for valid name: {name}",
            )

    def test_cannot_create_project_in_other_org(self):
        """User cannot create project in org they don't belong to."""
        other_org = OrgFactory()

        response = self.send_api_request(
            url="/api/projects/", method="post", data={"org_id": other_org.external_id, "name": "New Project"}
        )

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_update_project(self):
        """User can update project in their org."""
        project = ProjectFactory(org=self.org, name="Old Name", description="Old Description")

        response = self.send_api_request(
            url=f"/api/projects/{project.external_id}/",
            method="patch",
            data={"name": "New Name", "description": "New Description"},
        )
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(payload["name"], "New Name")
        self.assertEqual(payload["description"], "New Description")

        # Verify database was updated
        project.refresh_from_db()
        self.assertEqual(project.name, "New Name")
        self.assertEqual(project.description, "New Description")

    def test_update_project_name_only(self):
        """Can update just the project name."""
        project = ProjectFactory(org=self.org, name="Old Name", description="Original Description")

        response = self.send_api_request(
            url=f"/api/projects/{project.external_id}/", method="patch", data={"name": "New Name"}
        )
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(payload["name"], "New Name")
        self.assertEqual(payload["description"], "Original Description")

    def test_update_project_description_only(self):
        """Can update just the project description."""
        project = ProjectFactory(org=self.org, name="Original Name", description="Old Description")

        response = self.send_api_request(
            url=f"/api/projects/{project.external_id}/", method="patch", data={"description": "New Description"}
        )
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(payload["name"], "Original Name")
        self.assertEqual(payload["description"], "New Description")

    def test_cannot_update_project_in_other_org(self):
        """Cannot update project in org you don't belong to."""
        other_org = OrgFactory()
        project = ProjectFactory(org=other_org)

        response = self.send_api_request(
            url=f"/api/projects/{project.external_id}/", method="patch", data={"name": "New Name"}
        )

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_update_project_with_invalid_chars_returns_422(self):
        """Updating project with invalid filename characters should fail."""
        project = ProjectFactory(org=self.org, name="Original Name")

        invalid_names = [
            "Project/Name",
            "Project\\Name",
            "Project:Name",
            "Project*Name",
        ]
        for name in invalid_names:
            response = self.send_api_request(
                url=f"/api/projects/{project.external_id}/",
                method="patch",
                data={"name": name},
            )
            self.assertEqual(
                response.status_code,
                HTTPStatus.UNPROCESSABLE_ENTITY,
                f"Expected 422 for name with invalid char: {name}",
            )

        # Verify original name unchanged
        project.refresh_from_db()
        self.assertEqual(project.name, "Original Name")

    def test_soft_delete_project(self):
        """Deleting project should soft-delete it (only creator can delete)."""
        # Creator must be self.user for delete permission
        project = ProjectFactory(org=self.org, is_deleted=False, creator=self.user)

        response = self.send_api_request(url=f"/api/projects/{project.external_id}/", method="delete")

        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)

        # Verify project was soft-deleted (not hard deleted)
        project.refresh_from_db()
        self.assertTrue(project.is_deleted)

    def test_project_editor_cannot_delete_project(self):
        """Project editors cannot delete projects they didn't create."""
        other_user = UserFactory()
        project = ProjectFactory(org=self.org, creator=other_user)

        # Add self.user as project editor
        project.editors.add(self.user)

        response = self.send_api_request(url=f"/api/projects/{project.external_id}/", method="delete")

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

        # Verify project was NOT deleted
        project.refresh_from_db()
        self.assertFalse(project.is_deleted)

    def test_cannot_delete_project_in_other_org(self):
        """Cannot delete project in org you don't belong to."""
        other_org = OrgFactory()
        project = ProjectFactory(org=other_org)

        response = self.send_api_request(url=f"/api/projects/{project.external_id}/", method="delete")

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

        # Verify project still exists
        project.refresh_from_db()
        self.assertFalse(project.is_deleted)

    def test_delete_nonexistent_project_returns_404(self):
        """Deleting non-existent project returns 404."""
        response = self.send_api_request(url="/api/projects/nonexistent-id/", method="delete")

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_unauthenticated_request_returns_401(self):
        """Unauthenticated requests should be rejected."""
        self.client.logout()

        response = self.send_api_request(url="/api/projects/", method="get")

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)


class TestProjectsAPIWithMultipleOrgs(BaseAuthenticatedViewTestCase):
    """Test project API with user belonging to multiple orgs."""

    def setUp(self):
        super().setUp()
        # Create two orgs, user is member of both
        self.org1 = OrgFactory(name="Org 1")
        self.org2 = OrgFactory(name="Org 2")

        OrgMemberFactory(org=self.org1, user=self.user, role=OrgMemberRole.MEMBER.value)
        OrgMemberFactory(org=self.org2, user=self.user, role=OrgMemberRole.ADMIN.value)

    def test_list_projects_from_all_orgs(self):
        """Without org_id filter, user sees projects from all orgs."""
        # Create projects in both orgs
        project1 = ProjectFactory(org=self.org1)
        project2 = ProjectFactory(org=self.org2)

        response = self.send_api_request(url="/api/projects/", method="get")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(len(payload), 2)
        project_ids = [p["external_id"] for p in payload]
        self.assertIn(project1.external_id, project_ids)
        self.assertIn(project2.external_id, project_ids)

    def test_list_projects_scoped_to_org(self):
        """Projects list can be filtered by org_id."""
        # Create projects in both orgs
        project1 = ProjectFactory(org=self.org1)
        project2 = ProjectFactory(org=self.org2)

        # List org1 projects
        response1 = self.send_api_request(url=f"/api/projects/?org_id={self.org1.external_id}", method="get")
        payload1 = response1.json()

        self.assertEqual(response1.status_code, HTTPStatus.OK)
        project_ids1 = [p["external_id"] for p in payload1]
        self.assertIn(project1.external_id, project_ids1)
        self.assertNotIn(project2.external_id, project_ids1)

        # List org2 projects
        response2 = self.send_api_request(url=f"/api/projects/?org_id={self.org2.external_id}", method="get")
        payload2 = response2.json()

        self.assertEqual(response2.status_code, HTTPStatus.OK)
        project_ids2 = [p["external_id"] for p in payload2]
        self.assertNotIn(project1.external_id, project_ids2)
        self.assertIn(project2.external_id, project_ids2)

    def test_can_access_project_from_any_org_membership(self):
        """User can access projects from any org they belong to."""
        project1 = ProjectFactory(org=self.org1)
        project2 = ProjectFactory(org=self.org2)

        # Should be able to get both projects
        response1 = self.send_api_request(url=f"/api/projects/{project1.external_id}/", method="get")
        response2 = self.send_api_request(url=f"/api/projects/{project2.external_id}/", method="get")

        self.assertEqual(response1.status_code, HTTPStatus.OK)
        self.assertEqual(response2.status_code, HTTPStatus.OK)


class TestProjectEditorAccess(BaseAuthenticatedViewTestCase):
    """Test project access for project editors (non-org members)."""

    def setUp(self):
        super().setUp()
        # Create an org that self.user is NOT a member of
        self.org = OrgFactory()
        self.org_member = UserFactory()
        OrgMemberFactory(org=self.org, user=self.org_member, role=OrgMemberRole.MEMBER.value)

        # Create a project in that org
        self.project = ProjectFactory(org=self.org, creator=self.org_member)

    def test_project_editor_can_list_project(self):
        """Project editor can see project in list."""
        # Add self.user as project editor
        self.project.editors.add(self.user)

        response = self.send_api_request(url="/api/projects/", method="get")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        payload = response.json()
        project_ids = [p["external_id"] for p in payload]
        self.assertIn(self.project.external_id, project_ids)

    def test_project_editor_can_get_project(self):
        """Project editor can get project details."""
        self.project.editors.add(self.user)

        response = self.send_api_request(url=f"/api/projects/{self.project.external_id}/", method="get")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["external_id"], self.project.external_id)

    def test_project_editor_can_update_project(self):
        """Project editor can update project details."""
        self.project.editors.add(self.user)

        response = self.send_api_request(
            url=f"/api/projects/{self.project.external_id}/",
            method="patch",
            data={"name": "Updated by Editor"},
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.project.refresh_from_db()
        self.assertEqual(self.project.name, "Updated by Editor")

    def test_non_editor_cannot_access_project(self):
        """User without org membership or editor access cannot access project."""
        # self.user is NOT an org member and NOT a project editor
        response = self.send_api_request(url=f"/api/projects/{self.project.external_id}/", method="get")

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_project_editor_can_get_project_with_details_full(self):
        """Project editor can get project with pages included."""
        self.project.editors.add(self.user)
        page = PageFactory(project=self.project)

        response = self.send_api_request(url=f"/api/projects/{self.project.external_id}/?details=full", method="get")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        payload = response.json()
        self.assertIsNotNone(payload["pages"])
        self.assertEqual(len(payload["pages"]), 1)
        self.assertEqual(payload["pages"][0]["external_id"], page.external_id)
