from http import HTTPStatus

from django.core.cache import cache

from core.tests.common import BaseAuthenticatedViewTestCase
from users.constants import OrgMemberRole
from users.models import Org, OrgMember
from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory


class TestOrgsAPI(BaseAuthenticatedViewTestCase):
    """Test organization API endpoints."""

    def test_list_orgs_returns_user_orgs(self):
        """User should only see orgs they belong to."""
        # Create two orgs - user is member of first one only
        org1 = OrgFactory()
        org2 = OrgFactory()

        OrgMemberFactory(org=org1, user=self.user, role=OrgMemberRole.MEMBER.value)

        response = self.send_api_request(url="/api/orgs/", method="get")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["external_id"], org1.external_id)
        self.assertEqual(payload[0]["name"], org1.name)

    def test_list_orgs_returns_empty_for_no_membership(self):
        """User with no org membership should see empty list."""
        # Create an org but don't add user
        OrgFactory()

        response = self.send_api_request(url="/api/orgs/", method="get")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(len(payload), 0)

    def test_get_org_details(self):
        """User should be able to get details of org they belong to."""
        org = OrgFactory()
        OrgMemberFactory(org=org, user=self.user, role=OrgMemberRole.MEMBER.value)

        response = self.send_api_request(url=f"/api/orgs/{org.external_id}/", method="get")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(payload["external_id"], org.external_id)
        self.assertEqual(payload["name"], org.name)
        self.assertIn("created", payload)
        self.assertIn("modified", payload)

    def test_get_org_requires_membership(self):
        """User cannot get details of org they don't belong to."""
        org = OrgFactory()

        response = self.send_api_request(url=f"/api/orgs/{org.external_id}/", method="get")

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_create_org_makes_user_admin(self):
        """Creating org should make user an admin."""
        orgs_before = Org.objects.count()

        response = self.send_api_request(url="/api/orgs/", method="post", data={"name": "New Organization"})
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        self.assertEqual(payload["name"], "New Organization")
        self.assertIn("external_id", payload)

        # Verify org was created
        self.assertEqual(Org.objects.count(), orgs_before + 1)

        # Verify user is admin
        org = Org.objects.get(external_id=payload["external_id"])
        membership = OrgMember.objects.get(org=org, user=self.user)
        self.assertEqual(membership.role, "admin")

    def test_create_org_with_empty_name_returns_422(self):
        """Creating org with empty name should fail."""
        response = self.send_api_request(url="/api/orgs/", method="post", data={"name": ""})

        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)

    def test_create_org_with_long_name_returns_422(self):
        """Creating org with name longer than 255 chars should fail."""
        response = self.send_api_request(url="/api/orgs/", method="post", data={"name": "a" * 256})

        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)

    def test_update_org_as_admin(self):
        """Admin should be able to update org details."""
        org = OrgFactory(name="Old Name")
        OrgMemberFactory(org=org, user=self.user, role=OrgMemberRole.ADMIN.value)

        response = self.send_api_request(url=f"/api/orgs/{org.external_id}/", method="patch", data={"name": "New Name"})
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(payload["name"], "New Name")

        # Verify database was updated
        org.refresh_from_db()
        self.assertEqual(org.name, "New Name")

    def test_update_org_requires_admin(self):
        """Non-admin members cannot update org details."""
        org = OrgFactory(name="Old Name")
        OrgMemberFactory(org=org, user=self.user, role=OrgMemberRole.MEMBER.value)

        response = self.send_api_request(url=f"/api/orgs/{org.external_id}/", method="patch", data={"name": "New Name"})

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertIn("Only admins can update", response.json()["message"])

        # Verify org name unchanged
        org.refresh_from_db()
        self.assertEqual(org.name, "Old Name")

    def test_delete_org_as_admin(self):
        """Admin should be able to delete org."""
        org = OrgFactory()
        OrgMemberFactory(org=org, user=self.user, role=OrgMemberRole.ADMIN.value)

        response = self.send_api_request(url=f"/api/orgs/{org.external_id}/", method="delete")

        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)

        # Verify org was deleted
        self.assertFalse(Org.objects.filter(external_id=org.external_id).exists())

    def test_delete_org_requires_admin(self):
        """Non-admin members cannot delete org."""
        org = OrgFactory()
        OrgMemberFactory(org=org, user=self.user, role=OrgMemberRole.MEMBER.value)

        response = self.send_api_request(url=f"/api/orgs/{org.external_id}/", method="delete")

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertIn("Only admins can delete", response.json()["message"])

        # Verify org still exists
        self.assertTrue(Org.objects.filter(external_id=org.external_id).exists())

    def test_unauthenticated_request_returns_401(self):
        """Unauthenticated requests should be rejected."""
        self.client.logout()

        response = self.send_api_request(url="/api/orgs/", method="get")

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)


class TestOrgMembersAPI(BaseAuthenticatedViewTestCase):
    """Test org membership API endpoints."""

    def setUp(self):
        super().setUp()
        # Clear cache to avoid rate limiting from previous tests
        cache.clear()
        # Create org and add self.user as member
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)

    def tearDown(self):
        super().tearDown()
        cache.clear()

    def test_list_members_returns_all_org_members(self):
        """Should list all members of the organization."""
        # Add another member
        other_user = UserFactory()
        OrgMemberFactory(org=self.org, user=other_user, role=OrgMemberRole.ADMIN.value)

        response = self.send_api_request(url=f"/api/orgs/{self.org.external_id}/members/", method="get")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(len(payload), 2)

        # Check members are included
        emails = [m["email"] for m in payload]
        self.assertIn(self.user.email, emails)
        self.assertIn(other_user.email, emails)

    def test_list_members_requires_membership(self):
        """Only org members can list members."""
        # Create another org
        other_org = OrgFactory()

        response = self.send_api_request(url=f"/api/orgs/{other_org.external_id}/members/", method="get")

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_any_member_can_invite(self):
        """Any org member can invite new members."""
        new_user = UserFactory(email="newuser@example.com")

        response = self.send_api_request(
            url=f"/api/orgs/{self.org.external_id}/members/",
            method="post",
            data={"email": new_user.email, "role": "member"},
        )
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        self.assertEqual(payload["email"], new_user.email)
        self.assertEqual(payload["role"], "member")

        # Verify membership was created
        self.assertTrue(OrgMember.objects.filter(org=self.org, user=new_user).exists())

    def test_invite_member_with_no_role_defaults_to_member(self):
        """Inviting without specifying role should default to 'member'."""
        new_user = UserFactory(email="newuser@example.com")

        response = self.send_api_request(
            url=f"/api/orgs/{self.org.external_id}/members/", method="post", data={"email": new_user.email}
        )
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        self.assertEqual(payload["role"], "member")

    def test_invite_nonexistent_user_returns_404(self):
        """Inviting non-existent user should fail."""
        response = self.send_api_request(
            url=f"/api/orgs/{self.org.external_id}/members/",
            method="post",
            data={"email": "nonexistent@example.com"},
        )

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
        self.assertIn("not found", response.json()["message"])

    def test_invite_existing_member_returns_400(self):
        """Inviting user who is already a member should fail."""
        response = self.send_api_request(
            url=f"/api/orgs/{self.org.external_id}/members/", method="post", data={"email": self.user.email}
        )

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIn("already a member", response.json()["message"])

    def test_remove_member(self):
        """Should be able to remove members."""
        member_to_remove = UserFactory()
        OrgMemberFactory(org=self.org, user=member_to_remove, role=OrgMemberRole.MEMBER.value)

        response = self.send_api_request(
            url=f"/api/orgs/{self.org.external_id}/members/{member_to_remove.external_id}/", method="delete"
        )

        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)

        # Verify membership was removed
        self.assertFalse(OrgMember.objects.filter(org=self.org, user=member_to_remove).exists())

    def test_cannot_remove_only_admin(self):
        """Cannot remove the only admin from org."""
        # Make self.user the only admin
        OrgMember.objects.filter(org=self.org, user=self.user).update(role="admin")

        response = self.send_api_request(
            url=f"/api/orgs/{self.org.external_id}/members/{self.user.external_id}/", method="delete"
        )

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIn("Cannot remove the only admin", response.json()["message"])

        # Verify membership still exists
        self.assertTrue(OrgMember.objects.filter(org=self.org, user=self.user).exists())

    def test_can_remove_self_when_other_admins_exist(self):
        """Can remove yourself if there are other admins."""
        # Add another admin
        other_admin = UserFactory()
        OrgMemberFactory(org=self.org, user=other_admin, role=OrgMemberRole.ADMIN.value)
        OrgMember.objects.filter(org=self.org, user=self.user).update(role="admin")

        response = self.send_api_request(
            url=f"/api/orgs/{self.org.external_id}/members/{self.user.external_id}/", method="delete"
        )

        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)
        self.assertFalse(OrgMember.objects.filter(org=self.org, user=self.user).exists())

    def test_remove_nonexistent_member_returns_404(self):
        """Removing non-member should return 404."""
        other_user = UserFactory()

        response = self.send_api_request(
            url=f"/api/orgs/{self.org.external_id}/members/{other_user.external_id}/", method="delete"
        )

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_update_member_role_as_admin(self):
        """Admin should be able to change member roles."""
        # Make self.user admin
        OrgMember.objects.filter(org=self.org, user=self.user).update(role="admin")

        # Add a regular member
        member = UserFactory()
        OrgMemberFactory(org=self.org, user=member, role=OrgMemberRole.MEMBER.value)

        response = self.send_api_request(
            url=f"/api/orgs/{self.org.external_id}/members/{member.external_id}/",
            method="patch",
            data={"role": "admin"},
        )
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(payload["role"], "admin")

        # Verify database was updated
        membership = OrgMember.objects.get(org=self.org, user=member)
        self.assertEqual(membership.role, "admin")

    def test_update_member_role_requires_admin(self):
        """Non-admin members cannot change roles."""
        other_member = UserFactory()
        OrgMemberFactory(org=self.org, user=other_member, role=OrgMemberRole.MEMBER.value)

        response = self.send_api_request(
            url=f"/api/orgs/{self.org.external_id}/members/{other_member.external_id}/",
            method="patch",
            data={"role": "admin"},
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertIn("Only admins can change", response.json()["message"])

    def test_cannot_demote_only_admin(self):
        """Cannot demote the only admin."""
        # Make self.user the only admin
        OrgMember.objects.filter(org=self.org, user=self.user).update(role="admin")

        response = self.send_api_request(
            url=f"/api/orgs/{self.org.external_id}/members/{self.user.external_id}/",
            method="patch",
            data={"role": "member"},
        )

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIn("Cannot demote the only admin", response.json()["message"])

        # Verify role unchanged
        membership = OrgMember.objects.get(org=self.org, user=self.user)
        self.assertEqual(membership.role, "admin")

    def test_can_demote_self_when_other_admins_exist(self):
        """Can demote yourself if there are other admins."""
        # Add another admin
        other_admin = UserFactory()
        OrgMemberFactory(org=self.org, user=other_admin, role=OrgMemberRole.ADMIN.value)
        OrgMember.objects.filter(org=self.org, user=self.user).update(role="admin")

        response = self.send_api_request(
            url=f"/api/orgs/{self.org.external_id}/members/{self.user.external_id}/",
            method="patch",
            data={"role": "member"},
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)

        # Verify role changed
        membership = OrgMember.objects.get(org=self.org, user=self.user)
        self.assertEqual(membership.role, "member")


class TestOrgMemberUsername(BaseAuthenticatedViewTestCase):
    """Test that member list includes username."""

    def test_member_list_includes_username(self):
        """Member list includes username field."""
        org = OrgFactory()
        OrgMemberFactory(org=org, user=self.user)

        response = self.send_api_request(f"/api/orgs/{org.external_id}/members/", method="get")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("username", response.json()[0])
        self.assertEqual(response.json()[0]["username"], self.user.username)


class TestAddMemberThrottling(BaseAuthenticatedViewTestCase):
    """Test rate limiting on the add member endpoint."""

    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)
        cache.clear()

    def tearDown(self):
        super().tearDown()
        cache.clear()

    def _add_member(self, email):
        return self.send_api_request(
            url=f"/api/orgs/{self.org.external_id}/members/",
            method="post",
            data={"email": email},
        )

    def test_first_request_succeeds(self):
        """First add member request should succeed."""
        new_user = UserFactory(email="user1@example.com")

        response = self._add_member(new_user.email)

        self.assertEqual(response.status_code, HTTPStatus.CREATED)

    def test_burst_rate_limit_blocks_rapid_requests(self):
        """Rapid consecutive requests should be blocked by burst throttle."""
        user1 = UserFactory(email="user1@example.com")
        user2 = UserFactory(email="user2@example.com")

        response1 = self._add_member(user1.email)
        self.assertEqual(response1.status_code, HTTPStatus.CREATED)

        response2 = self._add_member(user2.email)
        self.assertEqual(response2.status_code, HTTPStatus.TOO_MANY_REQUESTS)

    def test_different_users_have_separate_rate_limits(self):
        """Different users should have independent rate limits."""
        user1 = UserFactory(email="user1@example.com")
        user2 = UserFactory(email="user2@example.com")
        other_member = UserFactory(email="other_member@example.com")

        OrgMemberFactory(org=self.org, user=other_member, role=OrgMemberRole.MEMBER.value)

        response1 = self._add_member(user1.email)
        self.assertEqual(response1.status_code, HTTPStatus.CREATED)

        self.client.logout()
        self.login(other_member)

        response2 = self._add_member(user2.email)
        self.assertEqual(response2.status_code, HTTPStatus.CREATED)

    def test_throttle_returns_429_with_error_detail(self):
        """Throttled responses should return 429 with error message."""
        user1 = UserFactory(email="user1@example.com")
        user2 = UserFactory(email="user2@example.com")

        self._add_member(user1.email)

        response = self._add_member(user2.email)

        self.assertEqual(response.status_code, HTTPStatus.TOO_MANY_REQUESTS)
        payload = response.json()
        self.assertIn("detail", payload)
