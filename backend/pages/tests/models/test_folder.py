from django.db import IntegrityError
from django.test import TestCase

from pages.models import Folder, Page
from pages.tests.factories import FolderFactory, PageFactory, ProjectFactory


class TestFolderModel(TestCase):
    def test_folder_creation(self):
        project = ProjectFactory()
        folder = FolderFactory(project=project, parent=None, name="Design")

        self.assertIsNotNone(folder.id)
        self.assertIsNotNone(folder.external_id)
        self.assertEqual(folder.project, project)
        self.assertEqual(folder.name, "Design")
        self.assertIsNone(folder.parent_id)
        self.assertIsNotNone(folder.created)
        self.assertIsNotNone(folder.modified)

    def test_folder_str_returns_name(self):
        folder = FolderFactory(name="Design")
        self.assertEqual(str(folder), "Design")

    def test_nested_folder_creation(self):
        project = ProjectFactory()
        parent = FolderFactory(project=project, parent=None, name="Design")
        child = FolderFactory(project=project, parent=parent, name="Wireframes")

        self.assertEqual(child.parent, parent)
        self.assertEqual(list(parent.subfolders.all()), [child])

    def test_unique_name_per_parent(self):
        project = ProjectFactory()
        FolderFactory(project=project, parent=None, name="Design")
        with self.assertRaises(IntegrityError):
            FolderFactory(project=project, parent=None, name="Design")

    def test_unique_name_per_parent_nested(self):
        """Duplicate names under the same non-null parent are rejected."""
        project = ProjectFactory()
        parent = FolderFactory(project=project, parent=None, name="Design")
        FolderFactory(project=project, parent=parent, name="Notes")
        with self.assertRaises(IntegrityError):
            FolderFactory(project=project, parent=parent, name="Notes")

    def test_same_name_different_parents_allowed(self):
        project = ProjectFactory()
        parent1 = FolderFactory(project=project, parent=None, name="Design")
        parent2 = FolderFactory(project=project, parent=None, name="Engineering")
        child1 = FolderFactory(project=project, parent=parent1, name="Notes")
        child2 = FolderFactory(project=project, parent=parent2, name="Notes")

        self.assertEqual(child1.name, child2.name)
        self.assertNotEqual(child1.parent, child2.parent)

    def test_same_name_different_projects_allowed(self):
        project1 = ProjectFactory()
        project2 = ProjectFactory()
        FolderFactory(project=project1, parent=None, name="Design")
        folder2 = FolderFactory(project=project2, parent=None, name="Design")
        self.assertEqual(folder2.name, "Design")

    def test_page_folder_relationship(self):
        project = ProjectFactory()
        folder = FolderFactory(project=project, parent=None, name="Design")
        page = PageFactory(project=project, folder=folder, title="Page")

        self.assertEqual(page.folder, folder)
        self.assertIn(page, folder.pages.all())

    def test_page_folder_set_null_on_folder_delete(self):
        """Deleting a folder sets page.folder to NULL (SET_NULL)."""
        project = ProjectFactory()
        folder = FolderFactory(project=project, parent=None, name="Design")
        page = PageFactory(project=project, folder=folder, title="Page")

        folder.delete()
        page.refresh_from_db()
        self.assertIsNone(page.folder_id)
        self.assertTrue(Page.objects.filter(id=page.id).exists())

    def test_cascade_delete_parent_deletes_children(self):
        """Deleting a parent folder cascades to child folders."""
        project = ProjectFactory()
        parent = FolderFactory(project=project, parent=None, name="Design")
        child = FolderFactory(project=project, parent=parent, name="Wireframes")
        grandchild = FolderFactory(project=project, parent=child, name="V1")

        parent.delete()
        self.assertFalse(Folder.objects.filter(id=parent.id).exists())
        self.assertFalse(Folder.objects.filter(id=child.id).exists())
        self.assertFalse(Folder.objects.filter(id=grandchild.id).exists())

    def test_cascade_delete_project_deletes_folders(self):
        """Deleting a project cascades to its folders."""
        project = ProjectFactory()
        folder = FolderFactory(project=project, parent=None, name="Design")
        folder_id = folder.id

        project.delete()
        self.assertFalse(Folder.objects.filter(id=folder_id).exists())

    def test_multiple_root_folders_allowed(self):
        project = ProjectFactory()
        f1 = FolderFactory(project=project, parent=None, name="Design")
        f2 = FolderFactory(project=project, parent=None, name="Engineering")
        self.assertEqual(project.folders.count(), 2)
        self.assertIn(f1, project.folders.all())
        self.assertIn(f2, project.folders.all())
