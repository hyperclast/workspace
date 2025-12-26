from django.db import IntegrityError
from django.test import TestCase

from pages.models import ProjectEditor
from pages.tests.factories import ProjectEditorFactory, ProjectFactory
from users.tests.factories import UserFactory


class TestProjectEditorModel(TestCase):
    """Test ProjectEditor model."""

    def test_project_editor_creation(self):
        """Test that a project editor can be created."""
        project = ProjectFactory()
        user = UserFactory()

        editor = ProjectEditor.objects.create(user=user, project=project)

        self.assertIsNotNone(editor.id)
        self.assertEqual(editor.user, user)
        self.assertEqual(editor.project, project)
        self.assertIsNotNone(editor.created)
        self.assertIsNotNone(editor.modified)

    def test_project_editor_factory(self):
        """Test the ProjectEditor factory works correctly."""
        editor = ProjectEditorFactory()

        self.assertIsNotNone(editor.id)
        self.assertIsNotNone(editor.user)
        self.assertIsNotNone(editor.project)

    def test_str_representation(self):
        """Test __str__ returns project: user format."""
        project = ProjectFactory(name="Test Project")
        user = UserFactory(email="editor@example.com")
        editor = ProjectEditorFactory(project=project, user=user)

        expected = f"{project}: {user}"
        self.assertEqual(str(editor), expected)

    def test_unique_constraint_prevents_duplicate(self):
        """Test that the same user cannot be added twice to the same project."""
        project = ProjectFactory()
        user = UserFactory()

        # First editor creation should succeed
        ProjectEditor.objects.create(user=user, project=project)

        # Second creation should fail with unique constraint
        with self.assertRaises(IntegrityError):
            ProjectEditor.objects.create(user=user, project=project)

    def test_same_user_can_edit_multiple_projects(self):
        """Test that the same user can be an editor on multiple projects."""
        user = UserFactory()
        project1 = ProjectFactory()
        project2 = ProjectFactory()

        editor1 = ProjectEditor.objects.create(user=user, project=project1)
        editor2 = ProjectEditor.objects.create(user=user, project=project2)

        self.assertEqual(editor1.user, user)
        self.assertEqual(editor2.user, user)
        self.assertNotEqual(editor1.project, editor2.project)

    def test_same_project_can_have_multiple_editors(self):
        """Test that a project can have multiple editors."""
        project = ProjectFactory()
        user1 = UserFactory()
        user2 = UserFactory()
        user3 = UserFactory()

        ProjectEditor.objects.create(user=user1, project=project)
        ProjectEditor.objects.create(user=user2, project=project)
        ProjectEditor.objects.create(user=user3, project=project)

        editors = ProjectEditor.objects.filter(project=project)
        self.assertEqual(editors.count(), 3)

    def test_cascade_delete_on_project(self):
        """Test that deleting a project cascades to project editors."""
        project = ProjectFactory()
        editor = ProjectEditorFactory(project=project)
        editor_id = editor.id

        project.delete()

        self.assertFalse(ProjectEditor.objects.filter(id=editor_id).exists())

    def test_cascade_delete_on_user(self):
        """Test that deleting a user cascades to project editor entries."""
        user = UserFactory()
        # Create a project with a different creator to avoid PROTECT error
        project = ProjectFactory()
        editor = ProjectEditor.objects.create(user=user, project=project)
        editor_id = editor.id

        user.delete()

        self.assertFalse(ProjectEditor.objects.filter(id=editor_id).exists())

    def test_m2m_relationship_via_project(self):
        """Test that editors can be accessed via project.editors M2M."""
        project = ProjectFactory()
        user1 = UserFactory()
        user2 = UserFactory()

        ProjectEditor.objects.create(user=user1, project=project)
        ProjectEditor.objects.create(user=user2, project=project)

        editors = project.editors.all()
        self.assertEqual(editors.count(), 2)
        self.assertIn(user1, editors)
        self.assertIn(user2, editors)

    def test_m2m_relationship_via_user(self):
        """Test that editable projects can be accessed via user.editable_projects."""
        user = UserFactory()
        project1 = ProjectFactory()
        project2 = ProjectFactory()

        ProjectEditor.objects.create(user=user, project=project1)
        ProjectEditor.objects.create(user=user, project=project2)

        projects = user.editable_projects.all()
        self.assertEqual(projects.count(), 2)
        self.assertIn(project1, projects)
        self.assertIn(project2, projects)

    def test_timestamped_fields(self):
        """Test that created and modified timestamps are set correctly."""
        editor = ProjectEditorFactory()

        self.assertIsNotNone(editor.created)
        self.assertIsNotNone(editor.modified)
        self.assertGreaterEqual(editor.modified, editor.created)
