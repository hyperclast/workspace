from django.contrib.auth import get_user_model
from django.test import TestCase

from filehub.models import FileLink, FileUpload
from filehub.tests.factories import FileUploadFactory
from pages.models import Page, Project
from users.models import Org


User = get_user_model()


class FileLinkModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        self.org = Org.objects.create(name="Test Org")
        self.org.members.add(self.user)
        self.project = Project.objects.create(
            name="Test Project",
            org=self.org,
            creator=self.user,
        )
        self.page = Page.objects.create_with_owner(
            user=self.user,
            project=self.project,
            title="Source Page",
        )
        self.file = FileUploadFactory(
            uploaded_by=self.user,
            project=self.project,
            filename="test.png",
        )

    def test_sync_links_creates_links(self):
        """Test that file links are created when content contains file links."""
        content = f"Check out [test image](/files/{self.project.external_id}/{self.file.external_id}/{self.file.access_token}/)"

        FileLink.objects.sync_links_for_page(self.page, content)

        self.assertEqual(FileLink.objects.count(), 1)
        link = FileLink.objects.first()
        self.assertEqual(link.source_page, self.page)
        self.assertEqual(link.target_file, self.file)
        self.assertEqual(link.link_text, "test image")

    def test_sync_links_removes_old_links(self):
        """Test that old links are removed when content changes."""
        content1 = (
            f"Check out [test](/files/{self.project.external_id}/{self.file.external_id}/{self.file.access_token}/)"
        )
        FileLink.objects.sync_links_for_page(self.page, content1)
        self.assertEqual(FileLink.objects.count(), 1)

        content2 = "No links here"
        FileLink.objects.sync_links_for_page(self.page, content2)
        self.assertEqual(FileLink.objects.count(), 0)

    def test_sync_links_ignores_deleted_files(self):
        """Test that links to soft-deleted files are not created."""
        self.file.soft_delete()

        content = (
            f"Link to [deleted](/files/{self.project.external_id}/{self.file.external_id}/{self.file.access_token}/)"
        )
        FileLink.objects.sync_links_for_page(self.page, content)

        self.assertEqual(FileLink.objects.count(), 0)

    def test_sync_links_ignores_invalid_file_ids(self):
        """Test that links to non-existent files are not created."""
        content = "Link to [invalid](/files/proj123/nonexistent123/token123/)"

        FileLink.objects.sync_links_for_page(self.page, content)

        self.assertEqual(FileLink.objects.count(), 0)

    def test_sync_links_handles_multiple_links(self):
        """Test that multiple file links in content are all tracked."""
        file2 = FileUploadFactory(
            uploaded_by=self.user,
            project=self.project,
            filename="other.pdf",
        )

        content = f"""
        First: [image](/files/{self.project.external_id}/{self.file.external_id}/{self.file.access_token}/)
        Second: [document](/files/{self.project.external_id}/{file2.external_id}/{file2.access_token}/)
        """

        FileLink.objects.sync_links_for_page(self.page, content)

        self.assertEqual(FileLink.objects.count(), 2)
        file_ids = set(FileLink.objects.values_list("target_file_id", flat=True))
        self.assertEqual(file_ids, {self.file.id, file2.id})

    def test_sync_links_handles_absolute_urls(self):
        """Test that absolute URLs with domain are also matched."""
        content = (
            f"Check out [hosted](/files/{self.project.external_id}/{self.file.external_id}/{self.file.access_token}/)"
        )

        FileLink.objects.sync_links_for_page(self.page, content)

        self.assertEqual(FileLink.objects.count(), 1)

    def test_sync_links_returns_changed_flag(self):
        """Test that sync returns changed=True when links are added/removed, False otherwise."""
        content = (
            f"Check out [image](/files/{self.project.external_id}/{self.file.external_id}/{self.file.access_token}/)"
        )

        _, changed = FileLink.objects.sync_links_for_page(self.page, content)
        self.assertTrue(changed)

        _, changed = FileLink.objects.sync_links_for_page(self.page, content)
        self.assertFalse(changed)

        _, changed = FileLink.objects.sync_links_for_page(self.page, "no links")
        self.assertTrue(changed)

        _, changed = FileLink.objects.sync_links_for_page(self.page, "still no links")
        self.assertFalse(changed)

    def test_page_file_links_relationship(self):
        """Test that Page.file_links returns outgoing file links."""
        content = (
            f"Check out [test](/files/{self.project.external_id}/{self.file.external_id}/{self.file.access_token}/)"
        )
        FileLink.objects.sync_links_for_page(self.page, content)

        self.assertEqual(self.page.file_links.count(), 1)

    def test_file_page_references_relationship(self):
        """Test that FileUpload.page_references returns incoming links."""
        content = (
            f"Check out [test](/files/{self.project.external_id}/{self.file.external_id}/{self.file.access_token}/)"
        )
        FileLink.objects.sync_links_for_page(self.page, content)

        self.assertEqual(self.file.page_references.count(), 1)
        self.assertEqual(self.file.page_references.first().source_page, self.page)

    def test_sync_handles_same_file_different_text(self):
        """Test that same file with different link text creates separate entries."""
        content = f"""
        First: [image one](/files/{self.project.external_id}/{self.file.external_id}/{self.file.access_token}/)
        Second: [image two](/files/{self.project.external_id}/{self.file.external_id}/{self.file.access_token}/)
        """

        FileLink.objects.sync_links_for_page(self.page, content)

        self.assertEqual(FileLink.objects.count(), 2)
        texts = set(FileLink.objects.values_list("link_text", flat=True))
        self.assertEqual(texts, {"image one", "image two"})
