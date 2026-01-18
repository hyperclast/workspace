from django.test import TestCase

from pages.constants import ProjectEditorRole
from pages.models import Project, ProjectEditor
from pages.tests.factories import ProjectFactory
from users.tests.factories import OrgFactory, UserFactory


class TestProjectModel(TestCase):
    """Test Project model instance methods and properties."""

    def test_project_creation(self):
        """Test that project can be created with basic fields."""
        org = OrgFactory()
        creator = UserFactory()
        project = ProjectFactory(org=org, name="Test Project", description="Test description", creator=creator)

        self.assertIsNotNone(project.id)
        self.assertIsNotNone(project.external_id)
        self.assertEqual(project.org, org)
        self.assertEqual(project.name, "Test Project")
        self.assertEqual(project.description, "Test description")
        self.assertEqual(project.creator, creator)
        self.assertFalse(project.is_deleted)
        self.assertIsNotNone(project.created)
        self.assertIsNotNone(project.modified)

    def test_project_creation_without_name(self):
        """Test that project can be created without a name (blank=True)."""
        project = ProjectFactory(name="")

        self.assertIsNotNone(project.id)
        self.assertEqual(project.name, "")

    def test_project_creation_without_description(self):
        """Test that project can be created without a description."""
        project = ProjectFactory(description="")

        self.assertEqual(project.description, "")

    def test_external_id_is_auto_generated(self):
        """Test that external_id is automatically generated and unique."""
        project1 = ProjectFactory()
        project2 = ProjectFactory()

        self.assertIsNotNone(project1.external_id)
        self.assertIsNotNone(project2.external_id)
        self.assertNotEqual(project1.external_id, project2.external_id)

    def test_default_is_deleted_is_false(self):
        """Test that is_deleted defaults to False."""
        project = ProjectFactory()

        self.assertFalse(project.is_deleted)

    def test_is_deleted_can_be_set_to_true(self):
        """Test that is_deleted can be set to True (soft delete)."""
        project = ProjectFactory(is_deleted=False)

        project.is_deleted = True
        project.save()
        project.refresh_from_db()

        self.assertTrue(project.is_deleted)

    def test_str_representation_with_name(self):
        """Test string representation returns name when available."""
        project = ProjectFactory(name="My Project")

        self.assertEqual(str(project), "My Project")

    def test_str_representation_without_name(self):
        """Test string representation returns external_id when name is blank."""
        project = ProjectFactory(name="")

        self.assertEqual(str(project), project.external_id)

    def test_org_relationship(self):
        """Test foreign key relationship with Org."""
        org = OrgFactory(name="Test Org")
        project1 = ProjectFactory(org=org)
        project2 = ProjectFactory(org=org)

        self.assertEqual(project1.org, org)
        self.assertEqual(project2.org, org)

        # Test reverse relationship
        org_projects = org.projects.all()
        self.assertEqual(org_projects.count(), 2)
        self.assertIn(project1, org_projects)
        self.assertIn(project2, org_projects)

    def test_cascade_delete_org(self):
        """Test that deleting org cascades to projects."""
        org = OrgFactory()
        project = ProjectFactory(org=org)
        project_id = project.id

        org.delete()

        # Verify project was deleted
        from pages.models import Project

        self.assertFalse(Project.objects.filter(id=project_id).exists())

    def test_protect_on_creator_delete(self):
        """Test that deleting creator is prevented (PROTECT behavior)."""
        from django.db.models.deletion import ProtectedError

        creator = UserFactory()
        project = ProjectFactory(creator=creator)

        self.assertEqual(project.creator, creator)

        # Attempting to delete creator should raise ProtectedError
        with self.assertRaises(ProtectedError):
            creator.delete()

        # Verify creator and project still exist
        project.refresh_from_db()
        creator.refresh_from_db()
        self.assertEqual(project.creator, creator)

    def test_creator_relationship(self):
        """Test foreign key relationship with User (creator)."""
        creator = UserFactory()
        project1 = ProjectFactory(creator=creator)
        project2 = ProjectFactory(creator=creator)

        self.assertEqual(project1.creator, creator)
        self.assertEqual(project2.creator, creator)

        # Test that creator is required
        from pages.models import Project

        with self.assertRaises(Exception):  # IntegrityError or ValidationError
            Project.objects.create(org=OrgFactory(), name="Test", creator=None)  # Should fail

    def test_timestamped_fields(self):
        """Test that created and modified timestamps are set correctly."""
        project = ProjectFactory()

        self.assertIsNotNone(project.created)
        self.assertIsNotNone(project.modified)
        self.assertGreaterEqual(project.modified, project.created)

    def test_modified_updates_on_save(self):
        """Test that modified timestamp updates when project is saved."""
        project = ProjectFactory()
        original_modified = project.modified

        project.name = "Updated Name"
        project.save()

        self.assertGreater(project.modified, original_modified)

    def test_multiple_projects_per_org(self):
        """Test that an org can have multiple projects."""
        org = OrgFactory()
        project1 = ProjectFactory(org=org, name="Project 1")
        project2 = ProjectFactory(org=org, name="Project 2")
        project3 = ProjectFactory(org=org, name="Project 3")

        projects = org.projects.all()
        self.assertEqual(projects.count(), 3)
        self.assertIn(project1, projects)
        self.assertIn(project2, projects)
        self.assertIn(project3, projects)

    def test_soft_delete_filtering(self):
        """Test that soft-deleted projects can be filtered."""
        org = OrgFactory()
        active_project = ProjectFactory(org=org, is_deleted=False)
        deleted_project = ProjectFactory(org=org, is_deleted=True)

        from pages.models import Project

        active_projects = Project.objects.filter(org=org, is_deleted=False)
        deleted_projects = Project.objects.filter(org=org, is_deleted=True)

        self.assertEqual(active_projects.count(), 1)
        self.assertEqual(deleted_projects.count(), 1)
        self.assertEqual(active_projects.first(), active_project)
        self.assertEqual(deleted_projects.first(), deleted_project)

    def test_description_can_be_long_text(self):
        """Test that description field can hold long text."""
        long_description = "A" * 1000  # 1000 characters
        project = ProjectFactory(description=long_description)

        self.assertEqual(project.description, long_description)
        self.assertEqual(len(project.description), 1000)

    def test_projects_ordered_by_org(self):
        """Test that projects from different orgs are independent."""
        org1 = OrgFactory(name="Org 1")
        org2 = OrgFactory(name="Org 2")

        project1 = ProjectFactory(org=org1, name="Org1 Project")
        project2 = ProjectFactory(org=org2, name="Org2 Project")

        org1_projects = org1.projects.all()
        org2_projects = org2.projects.all()

        self.assertEqual(org1_projects.count(), 1)
        self.assertEqual(org2_projects.count(), 1)
        self.assertIn(project1, org1_projects)
        self.assertNotIn(project1, org2_projects)
        self.assertIn(project2, org2_projects)
        self.assertNotIn(project2, org1_projects)


class TestProjectManager(TestCase):
    """Test Project custom manager methods."""

    def test_create_default_project(self):
        """Test that create_default_project creates a project with correct fields."""
        user = UserFactory(email="test@example.com")
        org = OrgFactory()

        project = Project.objects.create_default_project(user=user, org=org)

        self.assertIsNotNone(project.id)
        self.assertEqual(project.org, org)
        self.assertEqual(project.creator, user)
        self.assertEqual(project.name, "First Project")
        self.assertIn("test@example.com", project.description)
        self.assertFalse(project.is_deleted)

    def test_create_default_project_name_format(self):
        """Test that default project name follows expected format."""
        user = UserFactory(email="developer@company.com")
        org = OrgFactory()

        project = Project.objects.create_default_project(user=user, org=org)

        self.assertEqual(project.name, "First Project")

    def test_create_default_project_description_format(self):
        """Test that default project description follows expected format."""
        user = UserFactory(email="developer@company.com")
        org = OrgFactory()

        project = Project.objects.create_default_project(user=user, org=org)

        expected_desc = "Initial project automatically created for developer@company.com"
        self.assertEqual(project.description, expected_desc)

    def test_create_default_project_for_different_users(self):
        """Test that different users get different default projects."""
        user1 = UserFactory(email="user1@example.com")
        user2 = UserFactory(email="user2@example.com")
        org = OrgFactory()

        project1 = Project.objects.create_default_project(user=user1, org=org)
        project2 = Project.objects.create_default_project(user=user2, org=org)

        self.assertNotEqual(project1.id, project2.id)
        # Projects have same name ("First Project") but different descriptions containing user emails
        self.assertIn("user1@example.com", project1.description)
        self.assertIn("user2@example.com", project2.description)
        self.assertEqual(project1.creator, user1)
        self.assertEqual(project2.creator, user2)

    def test_create_default_project_in_different_orgs(self):
        """Test that default projects can be created in different orgs."""
        user = UserFactory()
        org1 = OrgFactory()
        org2 = OrgFactory()

        project1 = Project.objects.create_default_project(user=user, org=org1)
        project2 = Project.objects.create_default_project(user=user, org=org2)

        self.assertEqual(project1.org, org1)
        self.assertEqual(project2.org, org2)
        self.assertNotEqual(project1.id, project2.id)

    def test_create_default_project_generates_unique_external_id(self):
        """Test that each default project gets a unique external_id."""
        user = UserFactory()
        org = OrgFactory()

        project1 = Project.objects.create_default_project(user=user, org=org)
        project2 = Project.objects.create_default_project(user=user, org=org)

        self.assertNotEqual(project1.external_id, project2.external_id)


class TestGetUserAccessibleProjects(TestCase):
    """Test ProjectManager.get_user_accessible_projects() method."""

    def setUp(self):
        """Set up test fixtures."""
        self.org = OrgFactory()
        self.org_member = UserFactory()
        self.org.members.add(self.org_member)

        self.project_editor = UserFactory()
        self.outsider = UserFactory()

        self.project = ProjectFactory(org=self.org, creator=self.org_member)
        self.project.editors.add(self.project_editor)

    def test_org_member_can_access_project(self):
        """Test that org members can access projects in their org."""
        accessible = Project.objects.get_user_accessible_projects(self.org_member)

        self.assertIn(self.project, accessible)

    def test_project_editor_can_access_project(self):
        """Test that project editors can access projects they're editors of."""
        accessible = Project.objects.get_user_accessible_projects(self.project_editor)

        self.assertIn(self.project, accessible)

    def test_outsider_cannot_access_project(self):
        """Test that users without org membership or editor access cannot access projects."""
        accessible = Project.objects.get_user_accessible_projects(self.outsider)

        self.assertNotIn(self.project, accessible)

    def test_deleted_projects_not_included(self):
        """Test that soft-deleted projects are excluded from results."""
        deleted_project = ProjectFactory(org=self.org, is_deleted=True)

        accessible = Project.objects.get_user_accessible_projects(self.org_member)

        self.assertNotIn(deleted_project, accessible)
        self.assertIn(self.project, accessible)

    def test_distinct_results_no_duplicates(self):
        """Test that results are distinct when user has both org and editor access."""
        # org_member is already in org, now also add as editor
        self.project.editors.add(self.org_member)

        accessible = Project.objects.get_user_accessible_projects(self.org_member)

        # Should only appear once, not twice
        self.assertEqual(accessible.filter(id=self.project.id).count(), 1)

    def test_multiple_projects_via_org_membership(self):
        """Test that org members can see all projects in their org."""
        project2 = ProjectFactory(org=self.org, creator=self.org_member)
        project3 = ProjectFactory(org=self.org, creator=self.org_member)

        accessible = Project.objects.get_user_accessible_projects(self.org_member)

        self.assertIn(self.project, accessible)
        self.assertIn(project2, accessible)
        self.assertIn(project3, accessible)

    def test_multiple_projects_via_editor_access(self):
        """Test that project editors can see all projects they're editors of."""
        other_org = OrgFactory()
        project2 = ProjectFactory(org=other_org)
        project2.editors.add(self.project_editor)

        accessible = Project.objects.get_user_accessible_projects(self.project_editor)

        self.assertIn(self.project, accessible)
        self.assertIn(project2, accessible)

    def test_mixed_access_via_org_and_editor(self):
        """Test user with both org membership and editor access on different projects."""
        # Create a second org with a project
        other_org = OrgFactory()
        other_project = ProjectFactory(org=other_org)

        # Make org_member also an editor on other_project
        other_project.editors.add(self.org_member)

        accessible = Project.objects.get_user_accessible_projects(self.org_member)

        # Should have access to both: self.project via org, other_project via editor
        self.assertIn(self.project, accessible)
        self.assertIn(other_project, accessible)

    def test_project_in_other_org_not_accessible(self):
        """Test that projects in other orgs are not accessible without editor access."""
        other_org = OrgFactory()
        other_project = ProjectFactory(org=other_org)

        accessible = Project.objects.get_user_accessible_projects(self.org_member)

        self.assertNotIn(other_project, accessible)

    def test_empty_result_for_user_without_any_access(self):
        """Test that users with no access get empty queryset."""
        new_user = UserFactory()

        accessible = Project.objects.get_user_accessible_projects(new_user)

        self.assertEqual(accessible.count(), 0)


class TestProjectAddEditorMethods(TestCase):
    """Test Project.add_editor() and Project.add_viewer() methods."""

    def setUp(self):
        """Set up test fixtures."""
        self.org = OrgFactory()
        self.project = ProjectFactory(org=self.org)
        self.user = UserFactory()

    def test_add_editor_creates_project_editor_with_editor_role(self):
        """Test that add_editor creates a ProjectEditor with 'editor' role."""
        self.project.add_editor(self.user)

        editor = ProjectEditor.objects.get(user=self.user, project=self.project)
        self.assertEqual(editor.role, ProjectEditorRole.EDITOR.value)

    def test_add_viewer_creates_project_editor_with_viewer_role(self):
        """Test that add_viewer creates a ProjectEditor with 'viewer' role."""
        self.project.add_viewer(self.user)

        editor = ProjectEditor.objects.get(user=self.user, project=self.project)
        self.assertEqual(editor.role, ProjectEditorRole.VIEWER.value)

    def test_add_editor_is_idempotent(self):
        """Test that calling add_editor twice doesn't create duplicates."""
        self.project.add_editor(self.user)
        self.project.add_editor(self.user)

        count = ProjectEditor.objects.filter(user=self.user, project=self.project).count()
        self.assertEqual(count, 1)

    def test_add_viewer_is_idempotent(self):
        """Test that calling add_viewer twice doesn't create duplicates."""
        self.project.add_viewer(self.user)
        self.project.add_viewer(self.user)

        count = ProjectEditor.objects.filter(user=self.user, project=self.project).count()
        self.assertEqual(count, 1)

    def test_add_editor_does_not_change_existing_role(self):
        """Test that add_editor doesn't change role if user already has one."""
        # First add as viewer
        self.project.add_viewer(self.user)
        editor = ProjectEditor.objects.get(user=self.user, project=self.project)
        self.assertEqual(editor.role, ProjectEditorRole.VIEWER.value)

        # Now try to add as editor - should not change role
        self.project.add_editor(self.user)
        editor.refresh_from_db()
        self.assertEqual(editor.role, ProjectEditorRole.VIEWER.value)

    def test_add_viewer_does_not_change_existing_role(self):
        """Test that add_viewer doesn't change role if user already has one."""
        # First add as editor
        self.project.add_editor(self.user)
        editor = ProjectEditor.objects.get(user=self.user, project=self.project)
        self.assertEqual(editor.role, ProjectEditorRole.EDITOR.value)

        # Now try to add as viewer - should not change role
        self.project.add_viewer(self.user)
        editor.refresh_from_db()
        self.assertEqual(editor.role, ProjectEditorRole.EDITOR.value)

    def test_add_editor_adds_user_to_editors_relation(self):
        """Test that add_editor adds user to project.editors M2M relation."""
        self.assertNotIn(self.user, self.project.editors.all())

        self.project.add_editor(self.user)

        self.assertIn(self.user, self.project.editors.all())

    def test_add_viewer_adds_user_to_editors_relation(self):
        """Test that add_viewer adds user to project.editors M2M relation."""
        self.assertNotIn(self.user, self.project.editors.all())

        self.project.add_viewer(self.user)

        self.assertIn(self.user, self.project.editors.all())

    def test_add_multiple_editors_to_same_project(self):
        """Test that multiple users can be added as editors to the same project."""
        user2 = UserFactory()
        user3 = UserFactory()

        self.project.add_editor(self.user)
        self.project.add_editor(user2)
        self.project.add_viewer(user3)

        self.assertEqual(ProjectEditor.objects.filter(project=self.project).count(), 3)
        self.assertEqual(
            ProjectEditor.objects.get(user=self.user, project=self.project).role,
            ProjectEditorRole.EDITOR.value,
        )
        self.assertEqual(
            ProjectEditor.objects.get(user=user2, project=self.project).role,
            ProjectEditorRole.EDITOR.value,
        )
        self.assertEqual(
            ProjectEditor.objects.get(user=user3, project=self.project).role,
            ProjectEditorRole.VIEWER.value,
        )

    def test_add_editor_to_multiple_projects(self):
        """Test that same user can be added as editor to multiple projects."""
        project2 = ProjectFactory(org=self.org)

        self.project.add_editor(self.user)
        project2.add_viewer(self.user)

        self.assertEqual(ProjectEditor.objects.filter(user=self.user).count(), 2)
        self.assertEqual(
            ProjectEditor.objects.get(user=self.user, project=self.project).role,
            ProjectEditorRole.EDITOR.value,
        )
        self.assertEqual(
            ProjectEditor.objects.get(user=self.user, project=project2).role,
            ProjectEditorRole.VIEWER.value,
        )
