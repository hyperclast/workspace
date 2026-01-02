from django.test import TestCase
from django.utils import timezone

from updates.models import Update

from .factories import UpdateFactory, UnpublishedUpdateFactory


class TestUpdateModel(TestCase):
    def test_create_update(self):
        update = UpdateFactory(title="Test Update", content="Some content")

        self.assertEqual(update.title, "Test Update")
        self.assertEqual(update.content, "Some content")
        self.assertTrue(update.is_published)
        self.assertIsNotNone(update.published_at)

    def test_slug_auto_generated_from_title(self):
        update = UpdateFactory(title="My First Update")

        self.assertEqual(update.slug, "my-first-update")

    def test_slug_handles_special_characters(self):
        update = UpdateFactory(title="What's New in v2.0?")

        self.assertEqual(update.slug, "whats-new-in-v20")

    def test_slug_uniqueness_with_counter(self):
        UpdateFactory(title="Duplicate Title")
        update2 = UpdateFactory(title="Duplicate Title")
        update3 = UpdateFactory(title="Duplicate Title")

        self.assertEqual(update2.slug, "duplicate-title-1")
        self.assertEqual(update3.slug, "duplicate-title-2")

    def test_published_at_auto_set_when_publishing(self):
        update = UnpublishedUpdateFactory()

        self.assertIsNone(update.published_at)

        update.is_published = True
        update.save()

        self.assertIsNotNone(update.published_at)

    def test_published_at_not_changed_if_already_set(self):
        original_time = timezone.now()
        update = UpdateFactory(published_at=original_time)

        update.title = "Updated Title"
        update.save()

        self.assertEqual(update.published_at, original_time)

    def test_str_representation(self):
        update = UpdateFactory(title="Test String")

        self.assertEqual(str(update), "Test String")

    def test_ordering_by_published_at_descending(self):
        older = UpdateFactory(title="Older")
        newer = UpdateFactory(title="Newer")

        updates = list(Update.objects.all())

        self.assertEqual(updates[0], newer)
        self.assertEqual(updates[1], older)

    def test_emailed_at_initially_none(self):
        update = UpdateFactory()

        self.assertIsNone(update.emailed_at)

    def test_image_url_optional(self):
        update = UpdateFactory(image_url="")
        self.assertEqual(update.image_url, "")

        update_with_image = UpdateFactory(image_url="https://example.com/image.png")
        self.assertEqual(update_with_image.image_url, "https://example.com/image.png")
