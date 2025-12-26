from django.test import TestCase

from pages.models import ProjectEditorRemoveEvent
from pages.tests.factories import ProjectEditorRemoveEventFactory, ProjectFactory
from users.tests.factories import UserFactory


class TestProjectEditorRemoveEventManager(TestCase):
    """Test ProjectEditorRemoveEvent custom manager methods."""

    def test_log_editor_removed_event_creates_event(self):
        """Test that log_editor_removed_event creates an event."""
        project = ProjectFactory()
        removed_by = UserFactory()
        editor = UserFactory()

        event = ProjectEditorRemoveEvent.objects.log_editor_removed_event(
            project=project,
            removed_by=removed_by,
            editor=editor,
            editor_email=editor.email,
        )

        self.assertIsNotNone(event)
        self.assertEqual(event.project, project)
        self.assertEqual(event.removed_by, removed_by)
        self.assertEqual(event.editor, editor)
        self.assertEqual(event.editor_email, editor.email)

    def test_log_editor_removed_event_with_null_editor(self):
        """Test that log_editor_removed_event works with null editor."""
        project = ProjectFactory()
        removed_by = UserFactory()
        email = "removed@example.com"

        event = ProjectEditorRemoveEvent.objects.log_editor_removed_event(
            project=project,
            removed_by=removed_by,
            editor=None,
            editor_email=email,
        )

        self.assertIsNotNone(event)
        self.assertEqual(event.project, project)
        self.assertEqual(event.removed_by, removed_by)
        self.assertIsNone(event.editor)
        self.assertEqual(event.editor_email, email)

    def test_log_editor_removed_event_handles_exception(self):
        """Test that log_editor_removed_event handles exceptions gracefully."""
        # Pass invalid data that will cause an exception
        event = ProjectEditorRemoveEvent.objects.log_editor_removed_event(
            project=None,  # This will cause an IntegrityError
            removed_by=None,
            editor=None,
            editor_email="test@example.com",
        )

        # Should return None when exception occurs
        self.assertIsNone(event)


class TestProjectEditorRemoveEvent(TestCase):
    """Test ProjectEditorRemoveEvent model instance methods."""

    def test_str_returns_external_id(self):
        """Test that __str__ returns the external_id."""
        event = ProjectEditorRemoveEventFactory()
        str_repr = str(event)

        self.assertEqual(str_repr, str(event.external_id))

    def test_external_id_is_unique(self):
        """Test that external_id is unique."""
        event1 = ProjectEditorRemoveEventFactory()
        event2 = ProjectEditorRemoveEventFactory()

        self.assertNotEqual(event1.external_id, event2.external_id)

    def test_external_id_is_uuid(self):
        """Test that external_id is a valid UUID."""
        import uuid

        event = ProjectEditorRemoveEventFactory()

        # Should be a valid UUID
        uuid_obj = uuid.UUID(str(event.external_id))
        self.assertIsNotNone(uuid_obj)

    def test_project_relationship(self):
        """Test foreign key relationship with Project."""
        project = ProjectFactory(name="Test Project")
        event = ProjectEditorRemoveEventFactory(project=project)

        self.assertEqual(event.project, project)
        self.assertEqual(event.project.name, "Test Project")

    def test_removed_by_relationship(self):
        """Test foreign key relationship with User (removed_by)."""
        user = UserFactory(email="admin@example.com")
        event = ProjectEditorRemoveEventFactory(removed_by=user)

        self.assertEqual(event.removed_by, user)
        self.assertEqual(event.removed_by.email, "admin@example.com")

    def test_editor_relationship(self):
        """Test foreign key relationship with User (editor)."""
        editor = UserFactory(email="editor@example.com")
        event = ProjectEditorRemoveEventFactory(editor=editor)

        self.assertEqual(event.editor, editor)
        self.assertEqual(event.editor.email, "editor@example.com")

    def test_editor_can_be_null(self):
        """Test that editor can be null."""
        event = ProjectEditorRemoveEventFactory(editor=None, editor_email="removed@example.com")

        self.assertIsNone(event.editor)
        self.assertEqual(event.editor_email, "removed@example.com")

    def test_editor_email_is_indexed(self):
        """Test that editor_email field has db_index."""
        field = ProjectEditorRemoveEvent._meta.get_field("editor_email")
        self.assertTrue(field.db_index)

    def test_cascade_delete_on_project(self):
        """Test that deleting project cascades to events."""
        project = ProjectFactory()
        event = ProjectEditorRemoveEventFactory(project=project)
        event_id = event.id

        project.delete()

        self.assertFalse(ProjectEditorRemoveEvent.objects.filter(id=event_id).exists())

    def test_cascade_delete_on_removed_by(self):
        """Test that deleting removed_by user cascades to events."""
        user = UserFactory()
        # Use different project creator to avoid PROTECT
        project = ProjectFactory()
        event = ProjectEditorRemoveEventFactory(project=project, removed_by=user)
        event_id = event.id

        user.delete()

        self.assertFalse(ProjectEditorRemoveEvent.objects.filter(id=event_id).exists())

    def test_set_null_on_editor_delete(self):
        """Test that deleting editor user sets editor to null."""
        editor = UserFactory()
        project = ProjectFactory()
        event = ProjectEditorRemoveEventFactory(project=project, editor=editor)
        event_id = event.id

        editor.delete()

        # Event should still exist
        event.refresh_from_db()
        self.assertTrue(ProjectEditorRemoveEvent.objects.filter(id=event_id).exists())
        self.assertIsNone(event.editor)

    def test_timestamped_fields(self):
        """Test that created and modified timestamps are set correctly."""
        event = ProjectEditorRemoveEventFactory()

        self.assertIsNotNone(event.created)
        self.assertIsNotNone(event.modified)
        self.assertGreaterEqual(event.modified, event.created)

    def test_related_name_on_project(self):
        """Test that events can be accessed via project.editor_removed_event_logs."""
        project = ProjectFactory()
        event1 = ProjectEditorRemoveEventFactory(project=project)
        event2 = ProjectEditorRemoveEventFactory(project=project)

        events = project.editor_removed_event_logs.all()
        self.assertEqual(events.count(), 2)
        self.assertIn(event1, events)
        self.assertIn(event2, events)

    def test_related_name_on_removed_by_user(self):
        """Test that events can be accessed via user.editor_removed_by_event_logs."""
        user = UserFactory()
        project = ProjectFactory()
        event = ProjectEditorRemoveEventFactory(project=project, removed_by=user)

        events = user.editor_removed_by_event_logs.all()
        self.assertEqual(events.count(), 1)
        self.assertIn(event, events)

    def test_related_name_on_editor_user(self):
        """Test that events can be accessed via user.editor_removed_user_event_logs."""
        editor = UserFactory()
        event = ProjectEditorRemoveEventFactory(editor=editor)

        events = editor.editor_removed_user_event_logs.all()
        self.assertEqual(events.count(), 1)
        self.assertIn(event, events)
