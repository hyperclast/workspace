"""
Tests for sync_snapshot_with_page task and content extraction.
"""

from unittest.mock import patch

from django.test import TestCase, override_settings
from pycrdt import Doc, Text

from collab.models import YSnapshot
from collab.tasks import sync_snapshot_with_page
from core.helpers import hashify
from pages.tests.factories import PageFactory


class TestYSnapshotContentProperty(TestCase):
    """Test the YSnapshot.content property."""

    def test_content_property_plain_text(self):
        """Test extracting plain text from a Yjs snapshot via the content property."""
        # Create a Yjs document with some content
        doc = Doc()
        ytext = Text()
        doc["codemirror"] = ytext
        ytext += "Hello World!\n\nThis is a test."

        # Get the snapshot bytes
        snapshot_bytes = doc.get_update()

        # Create a YSnapshot record
        snapshot = YSnapshot.objects.create(
            room_id="page_test123",
            snapshot=snapshot_bytes,
            last_update_id=1,
        )

        # Verify content property
        self.assertEqual(snapshot.content, "Hello World!\n\nThis is a test.")

    def test_content_property_empty_content(self):
        """Test extracting from an empty Yjs snapshot."""
        # Create an empty Yjs document
        doc = Doc()
        ytext = Text()
        doc["codemirror"] = ytext

        # Get the snapshot bytes
        snapshot_bytes = doc.get_update()

        # Create a YSnapshot record
        snapshot = YSnapshot.objects.create(
            room_id="page_test123",
            snapshot=snapshot_bytes,
            last_update_id=1,
        )

        # Verify empty content
        self.assertEqual(snapshot.content, "")

    def test_content_property_multiline_content(self):
        """Test extracting multiline content with various formatting."""
        # Create a Yjs document with multiline content
        doc = Doc()
        ytext = Text()
        doc["codemirror"] = ytext
        test_content = """# Title

This is a paragraph.

- List item 1
- List item 2

Another paragraph with **formatting**."""
        ytext += test_content

        # Get the snapshot bytes
        snapshot_bytes = doc.get_update()

        # Create a YSnapshot record
        snapshot = YSnapshot.objects.create(
            room_id="page_test123",
            snapshot=snapshot_bytes,
            last_update_id=1,
        )

        # Verify content
        self.assertEqual(snapshot.content, test_content)


@override_settings(ASK_FEATURE_ENABLED=True)
@patch("collab.tasks.update_page_embedding")
class TestSyncSnapshotWithPage(TestCase):
    """Test the sync_snapshot_with_page task."""

    def test_sync_snapshot_updates_page_content(self, mocked_compute):
        """Test that syncing a snapshot updates page.details['content']."""
        # Create a page
        page = PageFactory()
        room_id = f"page_{page.external_id}"

        # Create a Yjs snapshot with content
        doc = Doc()
        ytext = Text()
        doc["codemirror"] = ytext
        test_content = "This is the page content."
        ytext += test_content
        snapshot_bytes = doc.get_update()

        # Create a YSnapshot record
        snapshot = YSnapshot.objects.create(
            room_id=room_id,
            snapshot=snapshot_bytes,
            last_update_id=1,
        )

        # Run the sync task
        sync_snapshot_with_page(room_id)

        # Refresh page from database
        page.refresh_from_db()

        # Verify content was extracted and saved
        self.assertIn("content", page.details)
        self.assertEqual(page.details["content"], test_content)

        # Verify content_hash was saved
        self.assertIn("content_hash", page.details)
        expected_hash = hashify(test_content)
        self.assertEqual(page.details["content_hash"], expected_hash)

        # Verify timestamp was updated
        self.assertEqual(page.updated, snapshot.timestamp)

        # compute embedding task is enqueued
        mocked_compute.enqueue.assert_called_once_with(page_id=page.external_id)

    def test_sync_snapshot_handles_empty_content(self, mocked_compute):
        """Test syncing an empty snapshot."""
        # Create a page
        page = PageFactory()
        room_id = f"page_{page.external_id}"

        # Create an empty Yjs snapshot
        doc = Doc()
        ytext = Text()
        doc["codemirror"] = ytext
        snapshot_bytes = doc.get_update()

        # Create a YSnapshot record
        YSnapshot.objects.create(
            room_id=room_id,
            snapshot=snapshot_bytes,
            last_update_id=1,
        )

        # Run the sync task
        sync_snapshot_with_page(room_id)

        # Refresh page from database
        page.refresh_from_db()

        # Verify empty content was saved
        self.assertIn("content", page.details)
        self.assertEqual(page.details["content"], "")

        # Verify content_hash for empty string
        self.assertIn("content_hash", page.details)
        expected_hash = hashify("")
        self.assertEqual(page.details["content_hash"], expected_hash)

        mocked_compute.enqueue.assert_called_once_with(page_id=page.external_id)

    def test_sync_snapshot_preserves_other_details(self, mocked_compute):
        """Test that syncing doesn't overwrite other details fields."""
        # Create a page with existing details
        page = PageFactory(details={"custom_field": "custom_value"})
        room_id = f"page_{page.external_id}"

        # Create a Yjs snapshot
        doc = Doc()
        ytext = Text()
        doc["codemirror"] = ytext
        ytext += "New content"
        snapshot_bytes = doc.get_update()

        # Create a YSnapshot record
        YSnapshot.objects.create(
            room_id=room_id,
            snapshot=snapshot_bytes,
            last_update_id=1,
        )

        # Run the sync task
        sync_snapshot_with_page(room_id)

        # Refresh page from database
        page.refresh_from_db()

        # Verify content was added
        self.assertEqual(page.details["content"], "New content")

        # Verify content_hash was added
        self.assertEqual(page.details["content_hash"], hashify("New content"))

        # Verify other details were preserved
        self.assertEqual(page.details["custom_field"], "custom_value")
        mocked_compute.enqueue.assert_called_once_with(page_id=page.external_id)

    def test_sync_snapshot_updates_content_hash_when_content_changes(self, mocked_compute):
        """Test that content_hash is updated when content changes."""
        # Create a page
        page = PageFactory()
        room_id = f"page_{page.external_id}"

        # Create initial snapshot
        doc = Doc()
        ytext = Text()
        doc["codemirror"] = ytext
        ytext += "Initial content"
        snapshot_bytes = doc.get_update()

        snapshot = YSnapshot.objects.create(
            room_id=room_id,
            snapshot=snapshot_bytes,
            last_update_id=1,
        )

        # Run sync task
        sync_snapshot_with_page(room_id)
        page.refresh_from_db()

        initial_hash = page.details["content_hash"]
        self.assertEqual(initial_hash, hashify("Initial content"))

        # Verify embedding task was enqueued
        mocked_compute.enqueue.assert_called_once_with(page_id=page.external_id)
        mocked_compute.enqueue.reset_mock()

        # Update snapshot with new content
        doc2 = Doc()
        ytext2 = Text()
        doc2["codemirror"] = ytext2
        ytext2 += "Updated content"
        new_snapshot_bytes = doc2.get_update()

        snapshot.snapshot = new_snapshot_bytes
        snapshot.last_update_id = 2
        snapshot.save()

        # Run sync task again
        sync_snapshot_with_page(room_id)
        page.refresh_from_db()

        # Verify content and hash changed
        self.assertEqual(page.details["content"], "Updated content")
        updated_hash = page.details["content_hash"]
        self.assertEqual(updated_hash, hashify("Updated content"))
        self.assertNotEqual(initial_hash, updated_hash)

        # Verify embedding task was enqueued again (task always enqueues, optimization happens in embedding computation)
        mocked_compute.enqueue.assert_called_once_with(page_id=page.external_id)

    def test_sync_snapshot_always_enqueues_embedding_task(self, mocked_compute):
        """Test that embedding task is always enqueued, even when content hash doesn't change."""
        # Create a page with initial content
        page = PageFactory(details={"content": "Initial content", "content_hash": hashify("Initial content")})
        room_id = f"page_{page.external_id}"

        # Create a snapshot with THE SAME content
        doc = Doc()
        ytext = Text()
        doc["codemirror"] = ytext
        ytext += "Initial content"
        snapshot_bytes = doc.get_update()

        YSnapshot.objects.create(
            room_id=room_id,
            snapshot=snapshot_bytes,
            last_update_id=1,
        )

        # Run sync task
        sync_snapshot_with_page(room_id)
        page.refresh_from_db()

        # Verify content hash hasn't changed
        self.assertEqual(page.details["content_hash"], hashify("Initial content"))

        # Verify embedding task was STILL enqueued (optimization happens in embedding computation, not here)
        mocked_compute.enqueue.assert_called_once_with(page_id=page.external_id)

    def test_sync_snapshot_handles_missing_snapshot(self, mocked_compute):
        """Test that task handles missing snapshot gracefully."""
        # This should not raise an exception
        sync_snapshot_with_page("page_nonexistent")

        # If we get here without exception, the test passes

        self.assertFalse(mocked_compute.called)

    def test_sync_snapshot_handles_missing_page(self, mocked_compute):
        """Test that task handles missing page gracefully."""
        room_id = "page_00000000-0000-0000-0000-000000000000"

        # Create a snapshot without a corresponding page
        doc = Doc()
        ytext = Text()
        doc["codemirror"] = ytext
        ytext += "Content"
        snapshot_bytes = doc.get_update()

        YSnapshot.objects.create(
            room_id=room_id,
            snapshot=snapshot_bytes,
            last_update_id=1,
        )

        # This should not raise an exception
        sync_snapshot_with_page(room_id)

        # If we get here without exception, the test passes

        self.assertFalse(mocked_compute.called)


@override_settings(ASK_FEATURE_ENABLED=True)
@patch("collab.tasks.broadcast_links_updated")
@patch("collab.tasks.update_page_embedding")
class TestSyncSnapshotBroadcastsLinksUpdated(TestCase):
    """Test that sync_snapshot_with_page broadcasts links_updated to connected clients."""

    def test_sync_snapshot_broadcasts_links_updated(self, mocked_compute, mocked_broadcast):
        """Test that syncing a snapshot broadcasts links_updated via WebSocket."""
        page = PageFactory()
        room_id = f"page_{page.external_id}"

        doc = Doc()
        ytext = Text()
        doc["codemirror"] = ytext
        ytext += "Content with a [link](/pages/abc123/)"
        snapshot_bytes = doc.get_update()

        YSnapshot.objects.create(
            room_id=room_id,
            snapshot=snapshot_bytes,
            last_update_id=1,
        )

        sync_snapshot_with_page(room_id)

        mocked_broadcast.assert_called_once_with(room_id, page.external_id)

    def test_sync_snapshot_broadcasts_even_without_links(self, mocked_compute, mocked_broadcast):
        """Test that links_updated is broadcast even when content has no links."""
        page = PageFactory()
        room_id = f"page_{page.external_id}"

        doc = Doc()
        ytext = Text()
        doc["codemirror"] = ytext
        ytext += "Plain content without links"
        snapshot_bytes = doc.get_update()

        YSnapshot.objects.create(
            room_id=room_id,
            snapshot=snapshot_bytes,
            last_update_id=1,
        )

        sync_snapshot_with_page(room_id)

        mocked_broadcast.assert_called_once_with(room_id, page.external_id)


@override_settings(ASK_FEATURE_ENABLED=False)
@patch("collab.tasks.update_page_embedding")
class TestSyncSnapshotWithPageFeatureDisabled(TestCase):
    """Test sync_snapshot_with_page task when ASK_FEATURE_ENABLED is False."""

    def test_sync_snapshot_skips_embedding_when_feature_disabled(self, mocked_compute):
        """Test that embedding computation is skipped when ASK_FEATURE_ENABLED is False."""
        # Create a page
        page = PageFactory()
        room_id = f"page_{page.external_id}"

        # Create a Yjs snapshot with content
        doc = Doc()
        ytext = Text()
        doc["codemirror"] = ytext
        test_content = "This is the page content."
        ytext += test_content
        snapshot_bytes = doc.get_update()

        # Create a YSnapshot record
        snapshot = YSnapshot.objects.create(
            room_id=room_id,
            snapshot=snapshot_bytes,
            last_update_id=1,
        )

        # Run the sync task
        sync_snapshot_with_page(room_id)

        # Refresh page from database
        page.refresh_from_db()

        # Verify content was extracted and saved (this should still happen)
        self.assertIn("content", page.details)
        self.assertEqual(page.details["content"], test_content)

        # Verify content_hash was saved
        self.assertIn("content_hash", page.details)
        expected_hash = hashify(test_content)
        self.assertEqual(page.details["content_hash"], expected_hash)

        # Verify timestamp was updated
        self.assertEqual(page.updated, snapshot.timestamp)

        # Verify embedding computation was NOT called (feature disabled)
        mocked_compute.enqueue.assert_not_called()
