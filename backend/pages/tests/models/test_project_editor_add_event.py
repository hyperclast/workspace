from django.test import TestCase

from pages.models import ProjectEditorAddEvent
from pages.tests.factories import ProjectEditorAddEventFactory, ProjectFactory
from users.tests.factories import UserFactory


class TestProjectEditorAddEventManager(TestCase):
    """Test ProjectEditorAddEvent custom manager methods."""

    def test_log_editor_added_event_creates_event(self):
        """Test that log_editor_added_event creates an event."""
        project = ProjectFactory()
        added_by = UserFactory()
        editor = UserFactory()

        event = ProjectEditorAddEvent.objects.log_editor_added_event(
            project=project,
            added_by=added_by,
            editor=editor,
            editor_email=editor.email,
        )

        self.assertIsNotNone(event)
        self.assertEqual(event.project, project)
        self.assertEqual(event.added_by, added_by)
        self.assertEqual(event.editor, editor)
        self.assertEqual(event.editor_email, editor.email)

    def test_log_editor_added_event_with_null_editor(self):
        """Test that log_editor_added_event works with null editor (invitation case)."""
        project = ProjectFactory()
        added_by = UserFactory()
        email = "invited@example.com"

        event = ProjectEditorAddEvent.objects.log_editor_added_event(
            project=project,
            added_by=added_by,
            editor=None,
            editor_email=email,
        )

        self.assertIsNotNone(event)
        self.assertEqual(event.project, project)
        self.assertEqual(event.added_by, added_by)
        self.assertIsNone(event.editor)
        self.assertEqual(event.editor_email, email)

    def test_log_editor_added_event_handles_exception(self):
        """Test that log_editor_added_event handles exceptions gracefully."""
        # Pass invalid data that will cause an exception
        event = ProjectEditorAddEvent.objects.log_editor_added_event(
            project=None,  # This will cause an IntegrityError
            added_by=None,
            editor=None,
            editor_email="test@example.com",
        )

        # Should return None when exception occurs
        self.assertIsNone(event)


class TestProjectEditorAddEvent(TestCase):
    """Test ProjectEditorAddEvent model instance methods."""

    def test_str_returns_external_id(self):
        """Test that __str__ returns the external_id."""
        event = ProjectEditorAddEventFactory()
        str_repr = str(event)

        self.assertEqual(str_repr, str(event.external_id))

    def test_external_id_is_unique(self):
        """Test that external_id is unique."""
        event1 = ProjectEditorAddEventFactory()
        event2 = ProjectEditorAddEventFactory()

        self.assertNotEqual(event1.external_id, event2.external_id)

    def test_external_id_is_uuid(self):
        """Test that external_id is a valid UUID."""
        import uuid

        event = ProjectEditorAddEventFactory()

        # Should be a valid UUID
        uuid_obj = uuid.UUID(str(event.external_id))
        self.assertIsNotNone(uuid_obj)

    def test_project_relationship(self):
        """Test foreign key relationship with Project."""
        project = ProjectFactory(name="Test Project")
        event = ProjectEditorAddEventFactory(project=project)

        self.assertEqual(event.project, project)
        self.assertEqual(event.project.name, "Test Project")

    def test_added_by_relationship(self):
        """Test foreign key relationship with User (added_by)."""
        user = UserFactory(email="admin@example.com")
        event = ProjectEditorAddEventFactory(added_by=user)

        self.assertEqual(event.added_by, user)
        self.assertEqual(event.added_by.email, "admin@example.com")

    def test_editor_relationship(self):
        """Test foreign key relationship with User (editor)."""
        editor = UserFactory(email="editor@example.com")
        event = ProjectEditorAddEventFactory(editor=editor)

        self.assertEqual(event.editor, editor)
        self.assertEqual(event.editor.email, "editor@example.com")

    def test_editor_can_be_null(self):
        """Test that editor can be null (for invitation case)."""
        event = ProjectEditorAddEventFactory(editor=None, editor_email="invited@example.com")

        self.assertIsNone(event.editor)
        self.assertEqual(event.editor_email, "invited@example.com")

    def test_editor_email_is_indexed(self):
        """Test that editor_email field has db_index."""
        field = ProjectEditorAddEvent._meta.get_field("editor_email")
        self.assertTrue(field.db_index)

    def test_cascade_delete_on_project(self):
        """Test that deleting project cascades to events."""
        project = ProjectFactory()
        event = ProjectEditorAddEventFactory(project=project)
        event_id = event.id

        project.delete()

        self.assertFalse(ProjectEditorAddEvent.objects.filter(id=event_id).exists())

    def test_cascade_delete_on_added_by(self):
        """Test that deleting added_by user cascades to events."""
        user = UserFactory()
        # Use different project creator to avoid PROTECT
        project = ProjectFactory()
        event = ProjectEditorAddEventFactory(project=project, added_by=user)
        event_id = event.id

        user.delete()

        self.assertFalse(ProjectEditorAddEvent.objects.filter(id=event_id).exists())

    def test_set_null_on_editor_delete(self):
        """Test that deleting editor user sets editor to null."""
        editor = UserFactory()
        project = ProjectFactory()
        event = ProjectEditorAddEventFactory(project=project, editor=editor)
        event_id = event.id

        editor.delete()

        # Event should still exist
        event.refresh_from_db()
        self.assertTrue(ProjectEditorAddEvent.objects.filter(id=event_id).exists())
        self.assertIsNone(event.editor)

    def test_timestamped_fields(self):
        """Test that created and modified timestamps are set correctly."""
        event = ProjectEditorAddEventFactory()

        self.assertIsNotNone(event.created)
        self.assertIsNotNone(event.modified)
        self.assertGreaterEqual(event.modified, event.created)

    def test_related_name_on_project(self):
        """Test that events can be accessed via project.editor_added_event_logs."""
        project = ProjectFactory()
        event1 = ProjectEditorAddEventFactory(project=project)
        event2 = ProjectEditorAddEventFactory(project=project)

        events = project.editor_added_event_logs.all()
        self.assertEqual(events.count(), 2)
        self.assertIn(event1, events)
        self.assertIn(event2, events)

    def test_related_name_on_added_by_user(self):
        """Test that events can be accessed via user.editor_added_by_event_logs."""
        user = UserFactory()
        project = ProjectFactory()
        event = ProjectEditorAddEventFactory(project=project, added_by=user)

        events = user.editor_added_by_event_logs.all()
        self.assertEqual(events.count(), 1)
        self.assertIn(event, events)

    def test_related_name_on_editor_user(self):
        """Test that events can be accessed via user.editor_added_user_event_logs."""
        editor = UserFactory()
        event = ProjectEditorAddEventFactory(editor=editor)

        events = editor.editor_added_user_event_logs.all()
        self.assertEqual(events.count(), 1)
        self.assertIn(event, events)
