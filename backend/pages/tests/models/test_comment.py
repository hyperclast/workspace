from django.test import TestCase

from pages.models import Comment
from pages.models.comments import COMMENT_MAX_DEPTH
from pages.tests.factories import CommentFactory, PageFactory, ProjectFactory
from users.tests.factories import OrgFactory, UserFactory


class CommentModelMixin:
    """Shared setup for comment model tests."""

    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        self.user = UserFactory()
        self.project = ProjectFactory(org=self.org, creator=self.user)
        self.page = PageFactory(project=self.project, creator=self.user)


class TestCommentCanReply(CommentModelMixin, TestCase):
    """Test Comment.can_reply property."""

    def test_root_comment_can_reply(self):
        """Root comment (depth 0) can be replied to."""
        root = CommentFactory(page=self.page, author=self.user)
        self.assertEqual(root.depth, 0)
        self.assertTrue(root.can_reply)

    def test_mid_depth_comment_can_reply(self):
        """Comment at depth 3 can be replied to."""
        comment = CommentFactory(page=self.page, author=self.user)
        for _ in range(3):
            comment = CommentFactory(page=self.page, author=self.user, parent=comment)
        self.assertEqual(comment.depth, 3)
        self.assertTrue(comment.can_reply)

    def test_penultimate_depth_can_reply(self):
        """Comment at depth COMMENT_MAX_DEPTH - 2 can be replied to (reply would be at max - 1)."""
        comment = CommentFactory(page=self.page, author=self.user)
        for _ in range(COMMENT_MAX_DEPTH - 2):
            comment = CommentFactory(page=self.page, author=self.user, parent=comment)
        self.assertEqual(comment.depth, COMMENT_MAX_DEPTH - 2)
        self.assertTrue(comment.can_reply)

    def test_max_depth_cannot_reply(self):
        """Comment at depth COMMENT_MAX_DEPTH - 1 cannot be replied to."""
        comment = CommentFactory(page=self.page, author=self.user)
        for _ in range(COMMENT_MAX_DEPTH - 1):
            comment = CommentFactory(page=self.page, author=self.user, parent=comment)
        self.assertEqual(comment.depth, COMMENT_MAX_DEPTH - 1)
        self.assertFalse(comment.can_reply)


class TestGetThread(CommentModelMixin, TestCase):
    """Test Comment.get_thread() method."""

    def test_get_thread_from_root(self):
        """get_thread on a root returns root + all descendants."""
        root = CommentFactory(page=self.page, author=self.user)
        reply1 = CommentFactory(page=self.page, author=self.user, parent=root)
        reply2 = CommentFactory(page=self.page, author=self.user, parent=root)
        nested = CommentFactory(page=self.page, author=self.user, parent=reply1)

        thread = list(root.get_thread())
        thread_ids = {c.id for c in thread}

        self.assertEqual(len(thread), 4)
        self.assertIn(root.id, thread_ids)
        self.assertIn(reply1.id, thread_ids)
        self.assertIn(reply2.id, thread_ids)
        self.assertIn(nested.id, thread_ids)

    def test_get_thread_from_reply(self):
        """get_thread on a reply returns the full thread (same as from root)."""
        root = CommentFactory(page=self.page, author=self.user)
        reply = CommentFactory(page=self.page, author=self.user, parent=root)
        nested = CommentFactory(page=self.page, author=self.user, parent=reply)

        thread = list(nested.get_thread())
        thread_ids = {c.id for c in thread}

        self.assertEqual(len(thread), 3)
        self.assertIn(root.id, thread_ids)
        self.assertIn(reply.id, thread_ids)
        self.assertIn(nested.id, thread_ids)

    def test_get_thread_ordered_by_created(self):
        """Thread is ordered by created ascending."""
        root = CommentFactory(page=self.page, author=self.user)
        reply1 = CommentFactory(page=self.page, author=self.user, parent=root)
        reply2 = CommentFactory(page=self.page, author=self.user, parent=root)

        thread = list(root.get_thread())
        created_times = [c.created for c in thread]
        self.assertEqual(created_times, sorted(created_times))

    def test_get_thread_excludes_other_threads(self):
        """get_thread only returns comments from the same thread, not other root threads."""
        root1 = CommentFactory(page=self.page, author=self.user)
        CommentFactory(page=self.page, author=self.user, parent=root1)

        root2 = CommentFactory(page=self.page, author=self.user)
        CommentFactory(page=self.page, author=self.user, parent=root2)

        thread = list(root1.get_thread())
        self.assertEqual(len(thread), 2)
        for c in thread:
            self.assertTrue(c.id == root1.id or c.root_id == root1.id)


class TestGetAncestorChain(CommentModelMixin, TestCase):
    """Test Comment.get_ancestor_chain() method."""

    def test_ancestor_chain_root_only(self):
        """Ancestor chain of a root comment is just [root]."""
        root = CommentFactory(page=self.page, author=self.user)
        chain = root.get_ancestor_chain()
        self.assertEqual(len(chain), 1)
        self.assertEqual(chain[0].id, root.id)

    def test_ancestor_chain_from_leaf(self):
        """Ancestor chain from a leaf returns root → ... → leaf."""
        root = CommentFactory(page=self.page, author=self.user)
        mid = CommentFactory(page=self.page, author=self.user, parent=root)
        leaf = CommentFactory(page=self.page, author=self.user, parent=mid)

        chain = leaf.get_ancestor_chain()
        self.assertEqual(len(chain), 3)
        self.assertEqual(chain[0].id, root.id)
        self.assertEqual(chain[1].id, mid.id)
        self.assertEqual(chain[2].id, leaf.id)

    def test_ancestor_chain_excludes_siblings(self):
        """Ancestor chain only includes direct ancestors, not siblings."""
        root = CommentFactory(page=self.page, author=self.user)
        sibling_a = CommentFactory(page=self.page, author=self.user, parent=root)
        sibling_b = CommentFactory(page=self.page, author=self.user, parent=root)
        leaf = CommentFactory(page=self.page, author=self.user, parent=sibling_a)

        chain = leaf.get_ancestor_chain()
        chain_ids = [c.id for c in chain]
        self.assertEqual(len(chain), 3)
        self.assertIn(root.id, chain_ids)
        self.assertIn(sibling_a.id, chain_ids)
        self.assertIn(leaf.id, chain_ids)
        self.assertNotIn(sibling_b.id, chain_ids)


class TestCascadeDeleteAcrossUsers(CommentModelMixin, TestCase):
    """Document the cascade-delete behavior where deleting a mid-tree comment
    destroys other users' replies."""

    def test_delete_parent_reply_cascades_other_users_descendants(self):
        """Deleting user A's reply cascades to user B's nested reply.

        This documents the current Django CASCADE behavior.
        """
        user_a = self.user
        user_b = UserFactory()

        root = CommentFactory(page=self.page, author=user_a)
        reply_a = CommentFactory(page=self.page, author=user_a, parent=root)
        reply_b = CommentFactory(page=self.page, author=user_b, parent=reply_a)

        self.assertEqual(Comment.objects.count(), 3)

        # Delete user A's reply — user B's reply is cascaded
        reply_a.delete()

        self.assertEqual(Comment.objects.count(), 1)
        self.assertTrue(Comment.objects.filter(id=root.id).exists())
        self.assertFalse(Comment.objects.filter(id=reply_a.id).exists())
        self.assertFalse(Comment.objects.filter(id=reply_b.id).exists())
