from datetime import timedelta
from http import HTTPStatus

from django.conf import settings
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from pages.tests.factories import ProjectFactory, ProjectInvitationFactory
from users.tests.factories import UserFactory


class TestAcceptProjectInvitationView(TestCase):
    """Test the accept_project_invitation view."""

    def setUp(self):
        self.client = Client()

    def get_accept_url(self, token):
        """Helper to get the project invitation acceptance URL."""
        return reverse("pages:accept_project_invitation", kwargs={"token": token})

    def test_accept_project_invitation_with_invalid_token(self):
        """Test accepting invitation with invalid token shows error page."""
        url = self.get_accept_url("invalid-token-123")
        response = self.client.get(url)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, "pages/invitation_invalid.html")
        self.assertIn("invalid", response.content.decode().lower())

    def test_accept_project_invitation_with_expired_token(self):
        """Test accepting expired invitation shows error page."""
        invitation = ProjectInvitationFactory(accepted=False, expires_at=timezone.now() - timedelta(days=1))

        url = self.get_accept_url(invitation.token)
        response = self.client.get(url)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, "pages/invitation_invalid.html")
        self.assertIn("invalid", response.content.decode().lower())

    def test_accept_project_invitation_already_accepted(self):
        """Test accepting already-accepted invitation shows error page."""
        user = UserFactory()
        invitation = ProjectInvitationFactory(
            accepted=True, accepted_by=user, expires_at=timezone.now() + timedelta(days=7)
        )

        url = self.get_accept_url(invitation.token)
        response = self.client.get(url)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, "pages/invitation_invalid.html")

    def test_accept_project_invitation_unauthenticated_stores_session_and_redirects(self):
        """Test unauthenticated user gets token stored and redirected to signup."""
        invitation = ProjectInvitationFactory(
            email="newuser@example.com",
            accepted=False,
            expires_at=timezone.now() + timedelta(days=7),
        )

        url = self.get_accept_url(invitation.token)
        response = self.client.get(url)

        # Should redirect to signup
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertIn("/accounts/signup/", response.url)

        # Check session has token stored
        session = self.client.session
        self.assertEqual(session[settings.PROJECT_INVITATION_PENDING_TOKEN_SESSION_KEY], invitation.token)
        self.assertEqual(session[settings.PROJECT_INVITATION_PENDING_EMAIL_SESSION_KEY], invitation.email)

    def test_accept_project_invitation_authenticated_correct_email_accepts(self):
        """Test authenticated user with matching email accepts invitation."""
        user = UserFactory(email="invitee@example.com")
        project = ProjectFactory()
        invitation = ProjectInvitationFactory(
            project=project,
            email="invitee@example.com",
            accepted=False,
            expires_at=timezone.now() + timedelta(days=7),
        )

        # Log in
        self.client.force_login(user)

        url = self.get_accept_url(invitation.token)
        response = self.client.get(url)

        # Should redirect to the project
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertIn(str(project.external_id), response.url)

        # Verify invitation was accepted
        invitation.refresh_from_db()
        self.assertTrue(invitation.accepted)
        self.assertEqual(invitation.accepted_by, user)

        # Verify user is now an editor
        self.assertTrue(project.editors.filter(id=user.id).exists())

    def test_accept_project_invitation_authenticated_email_case_insensitive(self):
        """Test email matching is case-insensitive."""
        user = UserFactory(email="InVitee@Example.COM")
        project = ProjectFactory()
        invitation = ProjectInvitationFactory(
            project=project,
            email="invitee@example.com",  # lowercase
            accepted=False,
            expires_at=timezone.now() + timedelta(days=7),
        )

        # Log in
        self.client.force_login(user)

        url = self.get_accept_url(invitation.token)
        response = self.client.get(url)

        # Should accept successfully
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertIn(str(project.external_id), response.url)

        # Verify invitation was accepted
        invitation.refresh_from_db()
        self.assertTrue(invitation.accepted)

    def test_accept_project_invitation_authenticated_wrong_email_shows_error(self):
        """Test authenticated user with wrong email sees error page."""
        user = UserFactory(email="wronguser@example.com")
        invitation = ProjectInvitationFactory(
            email="rightuser@example.com",
            accepted=False,
            expires_at=timezone.now() + timedelta(days=7),
        )

        # Log in as wrong user
        self.client.force_login(user)

        url = self.get_accept_url(invitation.token)
        response = self.client.get(url)

        # Should show error page
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, "pages/invitation_invalid.html")
        self.assertIn("rightuser@example.com", response.content.decode())

        # Verify invitation was NOT accepted
        invitation.refresh_from_db()
        self.assertFalse(invitation.accepted)

    def test_accept_project_invitation_redirect_url_includes_project_id(self):
        """Test that redirect URL includes the project external_id."""
        user = UserFactory(email="user@example.com")
        project = ProjectFactory()
        invitation = ProjectInvitationFactory(
            project=project,
            email="user@example.com",
            accepted=False,
            expires_at=timezone.now() + timedelta(days=7),
        )

        self.client.force_login(user)

        url = self.get_accept_url(invitation.token)
        response = self.client.get(url)

        # Check redirect URL contains project external_id
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertIn(f"?project={project.external_id}", response.url)

    def test_accept_project_invitation_unauthenticated_redirect_includes_next(self):
        """Test that signup redirect includes next parameter."""
        project = ProjectFactory()
        invitation = ProjectInvitationFactory(
            project=project,
            email="newuser@example.com",
            accepted=False,
            expires_at=timezone.now() + timedelta(days=7),
        )

        url = self.get_accept_url(invitation.token)
        response = self.client.get(url)

        # Should redirect to signup with next parameter
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertIn("/accounts/signup/", response.url)
        self.assertIn("next=", response.url)
        self.assertIn(str(project.external_id), response.url)

    def test_accept_project_invitation_does_not_accept_twice(self):
        """Test that accepting an invitation twice doesn't cause issues."""
        user = UserFactory(email="user@example.com")
        project = ProjectFactory()
        invitation = ProjectInvitationFactory(
            project=project,
            email="user@example.com",
            accepted=False,
            expires_at=timezone.now() + timedelta(days=7),
        )

        self.client.force_login(user)

        url = self.get_accept_url(invitation.token)

        # First acceptance
        response1 = self.client.get(url)
        self.assertEqual(response1.status_code, HTTPStatus.FOUND)

        # Second attempt - invitation is now accepted
        response2 = self.client.get(url)
        self.assertEqual(response2.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response2, "pages/invitation_invalid.html")

    def test_invalid_project_invitation_page_contains_frontend_home_link(self):
        """Test that invalid invitation page links to frontend homepage."""

        url = self.get_accept_url("invalid-token")
        response = self.client.get(url)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        # Check that FRONTEND_URL is in the response context or content
        content = response.content.decode()
        # The link should point to FRONTEND_URL (frontend homepage)
        self.assertIn("href=", content)
        # In test environment, should contain the frontend URL
        self.assertIn(settings.FRONTEND_URL, content)
