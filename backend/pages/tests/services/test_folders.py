from django.test import TestCase

from pages.services.folders import (
    MAX_FOLDER_NAME_LENGTH,
    build_parent_map,
    check_depth_limit,
    get_depth,
    get_subtree_max_depth,
    validate_folder_name,
    would_create_cycle,
)
from pages.tests.factories import FolderFactory, ProjectFactory


class TestValidateFolderName(TestCase):
    def test_valid_name_returns_stripped(self):
        self.assertEqual(validate_folder_name("  Design  "), "Design")

    def test_valid_simple_name(self):
        self.assertEqual(validate_folder_name("Design"), "Design")

    def test_none_raises(self):
        with self.assertRaises(ValueError) as ctx:
            validate_folder_name(None)
        self.assertIn("empty", str(ctx.exception).lower())
        self.assertEqual(ctx.exception.args[1], "name_required")

    def test_empty_string_raises(self):
        with self.assertRaises(ValueError) as ctx:
            validate_folder_name("")
        self.assertEqual(ctx.exception.args[1], "name_required")

    def test_whitespace_only_raises(self):
        with self.assertRaises(ValueError) as ctx:
            validate_folder_name("   \t\n  ")
        self.assertEqual(ctx.exception.args[1], "name_required")

    def test_max_length_ok(self):
        name = "a" * MAX_FOLDER_NAME_LENGTH
        self.assertEqual(validate_folder_name(name), name)

    def test_exceeds_max_length_raises(self):
        with self.assertRaises(ValueError) as ctx:
            validate_folder_name("a" * (MAX_FOLDER_NAME_LENGTH + 1))
        self.assertIn("exceed", str(ctx.exception).lower())
        self.assertEqual(ctx.exception.args[1], "name_too_long")

    def test_slash_forbidden(self):
        with self.assertRaises(ValueError) as ctx:
            validate_folder_name("Design/Notes")
        self.assertEqual(ctx.exception.args[1], "invalid_name")

    def test_backslash_forbidden(self):
        with self.assertRaises(ValueError) as ctx:
            validate_folder_name("Design\\Notes")
        self.assertEqual(ctx.exception.args[1], "invalid_name")

    def test_null_byte_forbidden(self):
        with self.assertRaises(ValueError) as ctx:
            validate_folder_name("Design\x00Notes")
        self.assertEqual(ctx.exception.args[1], "invalid_name")

    def test_control_chars_forbidden(self):
        with self.assertRaises(ValueError) as ctx:
            validate_folder_name("Design\x01Notes")
        self.assertEqual(ctx.exception.args[1], "invalid_name")

    def test_del_char_forbidden(self):
        with self.assertRaises(ValueError) as ctx:
            validate_folder_name("Design\x7fNotes")
        self.assertEqual(ctx.exception.args[1], "invalid_name")


class TestBuildParentMap(TestCase):
    def test_empty_project_returns_empty_map(self):
        project = ProjectFactory()
        self.assertEqual(build_parent_map(project), {})

    def test_single_root_folder(self):
        project = ProjectFactory()
        folder = FolderFactory(project=project, parent=None)
        parent_map = build_parent_map(project)
        self.assertEqual(parent_map, {folder.id: None})

    def test_nested_folders(self):
        project = ProjectFactory()
        root = FolderFactory(project=project, parent=None)
        child = FolderFactory(project=project, parent=root)
        grandchild = FolderFactory(project=project, parent=child)
        parent_map = build_parent_map(project)
        self.assertIsNone(parent_map[root.id])
        self.assertEqual(parent_map[child.id], root.id)
        self.assertEqual(parent_map[grandchild.id], child.id)


class TestWouldCreateCycle(TestCase):
    def test_no_cycle_when_moving_to_root(self):
        parent_map = {1: None, 2: 1, 3: 2}
        self.assertFalse(would_create_cycle(2, None, parent_map))

    def test_no_cycle_when_moving_to_sibling(self):
        parent_map = {1: None, 2: 1, 3: 1}
        self.assertFalse(would_create_cycle(2, 3, parent_map))

    def test_cycle_when_moving_into_own_child(self):
        parent_map = {1: None, 2: 1, 3: 2}
        self.assertTrue(would_create_cycle(1, 2, parent_map))

    def test_cycle_when_moving_into_own_descendant(self):
        parent_map = {1: None, 2: 1, 3: 2, 4: 3}
        self.assertTrue(would_create_cycle(1, 4, parent_map))

    def test_cycle_when_moving_into_self(self):
        parent_map = {1: None, 2: 1}
        self.assertTrue(would_create_cycle(2, 2, parent_map))

    def test_no_cycle_when_moving_to_unrelated_branch(self):
        parent_map = {1: None, 2: 1, 3: 1, 4: 3}
        self.assertFalse(would_create_cycle(2, 3, parent_map))


class TestGetDepth(TestCase):
    def test_root_folder_depth_one(self):
        parent_map = {1: None}
        self.assertEqual(get_depth(1, parent_map), 1)

    def test_child_depth_two(self):
        parent_map = {1: None, 2: 1}
        self.assertEqual(get_depth(2, parent_map), 2)

    def test_deep_nesting(self):
        parent_map = {1: None, 2: 1, 3: 2, 4: 3, 5: 4}
        self.assertEqual(get_depth(5, parent_map), 5)


class TestGetSubtreeMaxDepth(TestCase):
    def test_leaf_folder_returns_zero(self):
        parent_map = {1: None, 2: 1}
        self.assertEqual(get_subtree_max_depth(2, parent_map), 0)

    def test_folder_with_one_child_returns_one(self):
        parent_map = {1: None, 2: 1}
        self.assertEqual(get_subtree_max_depth(1, parent_map), 1)

    def test_folder_with_deep_chain(self):
        parent_map = {1: None, 2: 1, 3: 2, 4: 3}
        self.assertEqual(get_subtree_max_depth(1, parent_map), 3)

    def test_folder_with_branching(self):
        parent_map = {1: None, 2: 1, 3: 1, 4: 2, 5: 3}
        self.assertEqual(get_subtree_max_depth(1, parent_map), 2)


class TestCheckDepthLimit(TestCase):
    def test_within_limit_returns_depth(self):
        parent_map = {1: None, 2: 1, 3: 2}
        self.assertEqual(check_depth_limit(3, parent_map), 3)

    def test_exceeds_limit_raises(self):
        parent_map = {1: None, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5, 7: 6, 8: 7, 9: 8, 10: 9, 11: 10}
        with self.assertRaises(ValueError) as ctx:
            check_depth_limit(11, parent_map)
        self.assertEqual(ctx.exception.args[1], "depth_limit_exceeded")
