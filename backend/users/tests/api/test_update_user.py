from http import HTTPStatus

from core.tests.common import BaseAuthenticatedViewTestCase
from users.tests.factories import UserFactory


class TestUpdateUserAPI(BaseAuthenticatedViewTestCase):
    def send_update_user_request(self, data):
        return self.send_api_request(url="/api/users/me/", method="patch", data=data)

    def test_update_username_success(self):
        response = self.send_update_user_request({"username": "newusername"})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "newusername")

    def test_update_username_with_hyphens_underscores(self):
        response = self.send_update_user_request({"username": "new-user_name123"})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "new-user_name123")

    def test_update_username_rejects_special_chars(self):
        response = self.send_update_user_request({"username": "user@name"})

        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)
        self.user.refresh_from_db()
        self.assertNotEqual(self.user.username, "user@name")

    def test_update_username_rejects_spaces(self):
        response = self.send_update_user_request({"username": "user name"})

        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)

    def test_update_username_allows_dots(self):
        response = self.send_update_user_request({"username": "user.name"})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "user.name")

    def test_update_username_case_insensitive_uniqueness(self):
        UserFactory(username="ExistingUser")

        response = self.send_update_user_request({"username": "existinguser"})

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        payload = response.json()
        self.assertEqual(payload["message"], "Username is already taken")

    def test_update_username_case_insensitive_uniqueness_uppercase(self):
        UserFactory(username="existinguser")

        response = self.send_update_user_request({"username": "EXISTINGUSER"})

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        payload = response.json()
        self.assertEqual(payload["message"], "Username is already taken")

    def test_update_username_allows_own_username_different_case(self):
        self.user.username = "myusername"
        self.user.save()

        response = self.send_update_user_request({"username": "MyUsername"})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "MyUsername")

    def test_update_username_mixed_case_allowed(self):
        response = self.send_update_user_request({"username": "CamelCaseUser"})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "CamelCaseUser")

    def test_update_username_rejects_too_short(self):
        response = self.send_update_user_request({"username": "abc"})

        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)

    def test_update_username_accepts_minimum_length(self):
        response = self.send_update_user_request({"username": "abcd"})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "abcd")

    def test_update_username_rejects_reserved_username(self):
        response = self.send_update_user_request({"username": "admin"})

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        payload = response.json()
        self.assertIn("reserved", payload["message"].lower())

    def test_update_username_rejects_reserved_username_case_insensitive(self):
        response = self.send_update_user_request({"username": "HYPERCLAST"})

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        payload = response.json()
        self.assertIn("reserved", payload["message"].lower())


class TestUpdateCurrentOrgAPI(BaseAuthenticatedViewTestCase):
    """PATCH /api/users/me/ accepts current_org_id and persists it to
    Profile.current_org. Membership is enforced on write."""

    def setUp(self):
        super().setUp()
        from users.models import OrgMember
        from users.tests.factories import OrgFactory

        self.org_a = OrgFactory()
        OrgMember.objects.create(org=self.org_a, user=self.user, role="admin")
        self.org_b = OrgFactory()
        OrgMember.objects.create(org=self.org_b, user=self.user, role="admin")

    def _patch(self, data):
        return self.send_api_request(url="/api/users/me/", method="patch", data=data)

    def test_set_current_org_persists_to_profile(self):
        response = self._patch({"current_org_id": self.org_a.external_id})
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.profile.current_org_id, self.org_a.id)

    def test_switching_current_org_updates_to_new_org(self):
        self._patch({"current_org_id": self.org_a.external_id})
        self._patch({"current_org_id": self.org_b.external_id})
        self.user.refresh_from_db()
        self.assertEqual(self.user.profile.current_org_id, self.org_b.id)

    def test_empty_string_clears_current_org(self):
        self._patch({"current_org_id": self.org_a.external_id})
        response = self._patch({"current_org_id": ""})
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.profile.current_org_id)

    def test_rejects_org_user_is_not_a_member_of(self):
        """No info disclosure: any unknown / non-member org_id gets 400."""
        from users.tests.factories import OrgFactory

        outsider_org = OrgFactory()
        response = self._patch({"current_org_id": outsider_org.external_id})
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.profile.current_org_id)

    def test_omitting_current_org_id_leaves_it_alone(self):
        self._patch({"current_org_id": self.org_a.external_id})
        # PATCH that only updates other fields should not touch current_org.
        response = self._patch({"first_name": "Newname"})
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.profile.current_org_id, self.org_a.id)

    def test_rejects_partial_persistence_when_org_invalid(self):
        """A mixed payload with valid name fields + bogus current_org_id
        must reject the whole request — not leave the name fields persisted
        with a 400 response. The endpoint validates everything first, then
        applies inside transaction.atomic.
        """
        original_first_name = self.user.first_name

        response = self._patch({"first_name": "ShouldNotPersist", "current_org_id": "does-not-exist"})

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, original_first_name)
        self.assertIsNone(self.user.profile.current_org_id)


class TestUpdateOrgStateAPI(BaseAuthenticatedViewTestCase):
    """PATCH /api/users/me/org-state/{org_id}/ writes the user's resume page
    per org into `Profile.org_state[org_external_id]["last_page_id"]`."""

    def setUp(self):
        super().setUp()
        from pages.tests.factories import PageFactory, ProjectFactory
        from users.models import OrgMember
        from users.tests.factories import OrgFactory

        self.org = OrgFactory()
        OrgMember.objects.create(org=self.org, user=self.user, role="admin")
        self.project = ProjectFactory(org=self.org, creator=self.user)
        self.page = PageFactory(project=self.project, creator=self.user, title="Hello")

    def _patch(self, org_external_id, data):
        url = f"/api/users/me/org-state/{org_external_id}/"
        return self.send_api_request(url=url, method="patch", data=data)

    def _bucket(self, org_external_id=None):
        self.user.refresh_from_db()
        return (self.user.profile.org_state or {}).get(org_external_id or self.org.external_id, {})

    def test_set_last_page_writes_org_state_bucket(self):
        response = self._patch(self.org.external_id, {"last_page_id": self.page.external_id})
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(self._bucket().get("last_page_id"), self.page.external_id)

    def test_clearing_last_page_sets_null(self):
        self._patch(self.org.external_id, {"last_page_id": self.page.external_id})
        self._patch(self.org.external_id, {"last_page_id": None})
        self.assertIsNone(self._bucket().get("last_page_id"))

    def test_cross_org_page_is_silently_dropped(self):
        """A page from Org B can't be set as the last page for Org A — the
        endpoint silently treats it as a clear so a misbehaving client can't
        smuggle cross-org references through the persistence layer."""
        from pages.tests.factories import PageFactory, ProjectFactory
        from users.models import OrgMember
        from users.tests.factories import OrgFactory

        other_org = OrgFactory()
        OrgMember.objects.create(org=other_org, user=self.user, role="admin")
        other_project = ProjectFactory(org=other_org, creator=self.user)
        other_page = PageFactory(project=other_project, creator=self.user, title="Other")

        # Try to set Org A's last_page to a page that belongs to Org B.
        response = self._patch(self.org.external_id, {"last_page_id": other_page.external_id})
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIsNone(self._bucket().get("last_page_id"))

    def test_inaccessible_same_org_page_is_silently_dropped(self):
        """A page IN the right org but the user has no read access to it
        (e.g., a locked-down project owned by another admin) can't be set
        as last_page. Membership alone isn't enough — the user has to be
        able to actually open the page."""
        from pages.tests.factories import PageFactory, ProjectFactory
        from users.constants import OrgMemberRole
        from users.models import OrgMember
        from users.tests.factories import UserFactory

        # Demote self to non-admin member of self.org so the locked-down
        # project actually denies access (admins bypass Tier 1).
        OrgMember.objects.filter(user=self.user, org=self.org).update(role=OrgMemberRole.MEMBER.value)

        owner = UserFactory()
        OrgMember.objects.create(org=self.org, user=owner, role=OrgMemberRole.ADMIN.value)
        locked_project = ProjectFactory(org=self.org, creator=owner, org_members_can_access=False)
        locked_page = PageFactory(project=locked_project, creator=owner, title="Locked")

        response = self._patch(self.org.external_id, {"last_page_id": locked_page.external_id})
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIsNone(self._bucket().get("last_page_id"))

    def test_non_member_returns_404(self):
        """Passing an org_id the user isn't a member of returns 404, without
        revealing whether the org exists."""
        from users.tests.factories import OrgFactory

        outsider_org = OrgFactory()
        response = self._patch(outsider_org.external_id, {"last_page_id": None})
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_unauthenticated_request_returns_401(self):
        """The endpoint must require auth. It was originally added without
        the explicit decorator, which would have let anonymous requests
        reach code that assumes request.user is authenticated."""
        self.client.logout()
        response = self._patch(self.org.external_id, {"last_page_id": None})
        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)


class TestOrgStatePersistenceForExternalCollaborators(BaseAuthenticatedViewTestCase):
    """Project-only and page-only collaborators must be allowed to
    persist `current_org` and `last_page_id` for workspaces they have
    access to even though they aren't `OrgMember`s.

    The endpoints used to gate on `members=user`; that gave external
    collaborators a half-working state — frontend kept the page-derived
    `currentOrgId` locally but the server refused to round-trip it, so
    cross-device resume silently broke. The new access boundary
    mirrors `get_user_accessible_pages` (project / page-editor sharing
    counts), matching how Ask and mentions already behave."""

    def setUp(self):
        super().setUp()
        from pages.constants import ProjectEditorRole
        from pages.tests.factories import PageFactory, ProjectEditorFactory, ProjectFactory
        from users.models import OrgMember
        from users.tests.factories import OrgFactory, UserFactory

        # An org the test user has NO OrgMember row for.
        self.org = OrgFactory()
        owner = UserFactory()
        OrgMember.objects.create(org=self.org, user=owner, role="admin")
        self.project = ProjectFactory(org=self.org, creator=owner, org_members_can_access=False)
        self.page = PageFactory(project=self.project, creator=owner, title="Shared")
        # Test user gets in via project-editor (Tier 2) for the project_*
        # tests and page-editor (Tier 3) for the page_* tests below.
        self._project_editor_factory = ProjectEditorFactory
        self._editor_role = ProjectEditorRole

    def _patch_me(self, data):
        return self.send_api_request(url="/api/users/me/", method="patch", data=data)

    def _patch_state(self, org_external_id, data):
        url = f"/api/users/me/org-state/{org_external_id}/"
        return self.send_api_request(url=url, method="patch", data=data)

    def test_project_editor_can_persist_current_org(self):
        """`PATCH /me/ { current_org_id }` accepts an org the user only
        reaches via project-editor sharing."""
        self._project_editor_factory(user=self.user, project=self.project, role=self._editor_role.EDITOR.value)

        response = self._patch_me({"current_org_id": self.org.external_id})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.profile.current_org_id, self.org.id)

    def test_project_editor_can_persist_last_page(self):
        self._project_editor_factory(user=self.user, project=self.project, role=self._editor_role.EDITOR.value)

        response = self._patch_state(self.org.external_id, {"last_page_id": self.page.external_id})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.user.refresh_from_db()
        bucket = (self.user.profile.org_state or {}).get(self.org.external_id, {})
        self.assertEqual(bucket.get("last_page_id"), self.page.external_id)

    def test_page_editor_can_persist_last_page(self):
        """Page-level sharing alone is enough — Tier 3 access counts."""
        self.page.editors.add(self.user)

        response = self._patch_state(self.org.external_id, {"last_page_id": self.page.external_id})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.user.refresh_from_db()
        bucket = (self.user.profile.org_state or {}).get(self.org.external_id, {})
        self.assertEqual(bucket.get("last_page_id"), self.page.external_id)

    def test_true_outsider_still_rejected_without_leaking_existence(self):
        """A user with no access at any tier still gets 400 from /me/
        and 404 from /org-state/. The error shape is indistinguishable
        from "org doesn't exist" so we don't leak existence."""
        from users.tests.factories import OrgFactory

        outsider_org = OrgFactory()

        # /me/ rejects with 400.
        response = self._patch_me({"current_org_id": outsider_org.external_id})
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)

        # /org-state/ rejects with 404.
        response = self._patch_state(outsider_org.external_id, {"last_page_id": None})
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
