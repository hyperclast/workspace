from http import HTTPStatus

from core.tests.common import BaseAuthenticatedViewTestCase
from pages.models import CommentReaction
from pages.tests.factories import CommentFactory, PageFactory, ProjectFactory
from users.constants import OrgMemberRole
from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory


class ReactionsTestMixin:
    """Shared setup for reaction tests."""

    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)
        self.project = ProjectFactory(org=self.org, creator=self.user)
        self.page = PageFactory(project=self.project, creator=self.user)
        self.comment = CommentFactory(page=self.page, author=self.user, anchor_text="test")

    def reaction_url(self, comment=None, page=None):
        page = page or self.page
        comment = comment or self.comment
        return f"/api/pages/{page.external_id}/comments/{comment.external_id}/reactions/"

    def comments_url(self, page=None):
        page = page or self.page
        return f"/api/pages/{page.external_id}/comments/"


class TestToggleReaction(ReactionsTestMixin, BaseAuthenticatedViewTestCase):
    def test_add_reaction(self):
        response = self.send_api_request(url=self.reaction_url(), method="post", data={"emoji": "👍"})
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["emoji"], "👍")
        self.assertEqual(data[0]["count"], 1)
        self.assertTrue(data[0]["reacted"])
        self.assertEqual(len(data[0]["users"]), 1)

    def test_toggle_removes_reaction(self):
        # Add
        self.send_api_request(url=self.reaction_url(), method="post", data={"emoji": "👍"})
        # Remove
        response = self.send_api_request(url=self.reaction_url(), method="post", data={"emoji": "👍"})
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(len(data), 0)
        self.assertEqual(CommentReaction.objects.count(), 0)

    def test_multiple_users_same_emoji(self):
        other_user = UserFactory()
        OrgMemberFactory(org=self.org, user=other_user, role=OrgMemberRole.MEMBER.value)

        # User 1 reacts
        self.send_api_request(url=self.reaction_url(), method="post", data={"emoji": "❤️"})
        # User 2 reacts
        self.login(other_user)
        response = self.send_api_request(url=self.reaction_url(), method="post", data={"emoji": "❤️"})
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["count"], 2)
        self.assertTrue(data[0]["reacted"])  # other_user just added theirs

    def test_multiple_emoji_same_comment(self):
        self.send_api_request(url=self.reaction_url(), method="post", data={"emoji": "👍"})
        response = self.send_api_request(url=self.reaction_url(), method="post", data={"emoji": "❤️"})
        data = response.json()
        self.assertEqual(len(data), 2)
        emojis = {r["emoji"] for r in data}
        self.assertEqual(emojis, {"👍", "❤️"})

    def test_invalid_emoji_rejected(self):
        response = self.send_api_request(url=self.reaction_url(), method="post", data={"emoji": "🤖"})
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)

    def test_no_access_returns_404(self):
        other_user = UserFactory()
        self.login(other_user)
        response = self.send_api_request(url=self.reaction_url(), method="post", data={"emoji": "👍"})
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_viewer_cannot_react(self):
        from pages.constants import PageEditorRole
        from pages.tests.factories import PageEditorFactory

        viewer = UserFactory()
        OrgMemberFactory(org=self.org, user=viewer, role=OrgMemberRole.MEMBER.value)
        # Give viewer read-only access via page editor with viewer role
        PageEditorFactory(page=self.page, user=viewer, role=PageEditorRole.VIEWER.value)
        # Remove org member access so they only have page-level viewer access
        from users.models import OrgMember

        OrgMember.objects.filter(user=viewer, org=self.org).delete()

        self.login(viewer)
        response = self.send_api_request(url=self.reaction_url(), method="post", data={"emoji": "👍"})
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    def test_nonexistent_comment_returns_404(self):
        response = self.send_api_request(
            url=f"/api/pages/{self.page.external_id}/comments/nonexistent123/reactions/",
            method="post",
            data={"emoji": "👍"},
        )
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_cascade_on_comment_delete(self):
        self.send_api_request(url=self.reaction_url(), method="post", data={"emoji": "👍"})
        self.assertEqual(CommentReaction.objects.count(), 1)
        self.comment.delete()
        self.assertEqual(CommentReaction.objects.count(), 0)


class TestReactionsInListComments(ReactionsTestMixin, BaseAuthenticatedViewTestCase):
    def test_reactions_included_in_list(self):
        CommentReaction.objects.create(comment=self.comment, user=self.user, emoji="👍")
        response = self.send_api_request(url=self.comments_url())
        data = response.json()
        item = data["items"][0]
        self.assertEqual(len(item["reactions"]), 1)
        self.assertEqual(item["reactions"][0]["emoji"], "👍")
        self.assertEqual(item["reactions"][0]["count"], 1)
        self.assertTrue(item["reactions"][0]["reacted"])

    def test_reacted_flag_per_user(self):
        other_user = UserFactory()
        OrgMemberFactory(org=self.org, user=other_user, role=OrgMemberRole.MEMBER.value)
        CommentReaction.objects.create(comment=self.comment, user=other_user, emoji="👍")

        # Current user hasn't reacted
        response = self.send_api_request(url=self.comments_url())
        data = response.json()
        reaction = data["items"][0]["reactions"][0]
        self.assertFalse(reaction["reacted"])
        self.assertEqual(reaction["count"], 1)

    def test_reactions_on_replies(self):
        reply = CommentFactory(page=self.page, author=self.user, parent=self.comment)
        CommentReaction.objects.create(comment=reply, user=self.user, emoji="🎉")

        response = self.send_api_request(url=self.comments_url())
        data = response.json()
        reply_data = data["items"][0]["replies"][0]
        self.assertEqual(len(reply_data["reactions"]), 1)
        self.assertEqual(reply_data["reactions"][0]["emoji"], "🎉")

    def test_empty_reactions_when_none(self):
        response = self.send_api_request(url=self.comments_url())
        data = response.json()
        self.assertEqual(data["items"][0]["reactions"], [])

    def test_users_tooltip_capped_at_10(self):
        """Tooltip user list is capped at 10 names even with more reactions."""
        users = [UserFactory(first_name=f"User{i}") for i in range(12)]
        for u in users:
            OrgMemberFactory(org=self.org, user=u, role=OrgMemberRole.MEMBER.value)
            CommentReaction.objects.create(comment=self.comment, user=u, emoji="👍")

        response = self.send_api_request(url=self.comments_url())
        data = response.json()
        reaction = data["items"][0]["reactions"][0]
        self.assertEqual(reaction["count"], 12)
        self.assertEqual(len(reaction["users"]), 10)

    def test_multiple_emojis_correct_counts_and_users(self):
        """Each emoji group has independent counts and user lists."""
        other_user = UserFactory()
        OrgMemberFactory(org=self.org, user=other_user, role=OrgMemberRole.MEMBER.value)

        # Both users react with 👍, only other_user reacts with ❤️
        CommentReaction.objects.create(comment=self.comment, user=self.user, emoji="👍")
        CommentReaction.objects.create(comment=self.comment, user=other_user, emoji="👍")
        CommentReaction.objects.create(comment=self.comment, user=other_user, emoji="❤️")

        response = self.send_api_request(url=self.comments_url())
        data = response.json()
        reactions = {r["emoji"]: r for r in data["items"][0]["reactions"]}

        self.assertEqual(reactions["👍"]["count"], 2)
        self.assertEqual(len(reactions["👍"]["users"]), 2)
        self.assertTrue(reactions["👍"]["reacted"])  # current user reacted

        self.assertEqual(reactions["❤️"]["count"], 1)
        self.assertEqual(len(reactions["❤️"]["users"]), 1)
        self.assertFalse(reactions["❤️"]["reacted"])  # current user didn't react
