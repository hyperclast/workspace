"""Unit tests for `users.access.user_has_org_access`.

The helper is the single source of truth shared by the
`Profile.current_org` write path (`/api/users/me/` PATCH) and the
read paths (`get_user_state`, `_pick_homepage_target`). The matrix
below pins each tier so a future refactor that narrows the helper
to "member only" or the opposite (any project access regardless of
org boundary) breaks here loudly.
"""

from django.test import TestCase

from pages.constants import PageEditorRole, ProjectEditorRole
from pages.tests.factories import (
    PageEditorFactory,
    PageFactory,
    ProjectEditorFactory,
    ProjectFactory,
)
from users.access import user_has_org_access
from users.constants import OrgMemberRole
from users.models import OrgMember
from users.tests.factories import OrgFactory, UserFactory


class TestUserHasOrgAccess(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.org = OrgFactory()

    def test_returns_false_when_org_is_none(self):
        self.assertFalse(user_has_org_access(self.user, None))

    def test_returns_true_for_org_admin(self):
        OrgMember.objects.create(org=self.org, user=self.user, role=OrgMemberRole.ADMIN.value)
        self.assertTrue(user_has_org_access(self.user, self.org))

    def test_returns_true_for_org_member(self):
        OrgMember.objects.create(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)
        self.assertTrue(user_has_org_access(self.user, self.org))

    def test_returns_true_for_org_member_in_empty_org(self):
        """An org with no projects/pages must still resolve for its
        members — the access helper can't depend on data existing
        inside the org, only on the user's relationship with it."""
        OrgMember.objects.create(org=self.org, user=self.user, role=OrgMemberRole.ADMIN.value)
        # No projects, no pages.
        self.assertTrue(user_has_org_access(self.user, self.org))

    def test_returns_true_for_project_editor_without_membership(self):
        owner = UserFactory()
        OrgMember.objects.create(org=self.org, user=owner, role=OrgMemberRole.ADMIN.value)
        project = ProjectFactory(org=self.org, creator=owner, org_members_can_access=False)
        PageFactory(project=project, creator=owner)
        ProjectEditorFactory(user=self.user, project=project, role=ProjectEditorRole.EDITOR.value)

        self.assertTrue(user_has_org_access(self.user, self.org))

    def test_returns_true_for_page_editor_without_membership(self):
        owner = UserFactory()
        OrgMember.objects.create(org=self.org, user=owner, role=OrgMemberRole.ADMIN.value)
        project = ProjectFactory(org=self.org, creator=owner, org_members_can_access=False)
        page = PageFactory(project=project, creator=owner)
        PageEditorFactory(user=self.user, page=page, role=PageEditorRole.EDITOR.value)

        self.assertTrue(user_has_org_access(self.user, self.org))

    def test_returns_false_when_user_has_no_relationship_with_org(self):
        owner = UserFactory()
        OrgMember.objects.create(org=self.org, user=owner, role=OrgMemberRole.ADMIN.value)
        project = ProjectFactory(org=self.org, creator=owner, org_members_can_access=False)
        # A page in the org, but `self.user` is not its editor and not
        # a project editor — no access via any tier.
        PageFactory(project=project, creator=owner)

        self.assertFalse(user_has_org_access(self.user, self.org))
