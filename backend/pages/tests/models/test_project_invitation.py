from datetime import timedelta
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from pages.models import ProjectInvitation
from pages.tests.factories import ProjectFactory, ProjectInvitationFactory
from users.tests.factories import UserFactory


class TestProjectInvitationManager(TestCase):
    """Test ProjectInvitation custom manager methods."""

    def test_create_invitation_generates_secure_token(self):
        """Test that create_invitation generates a secure token."""
        project = ProjectFactory()
        inviter = UserFactory()
        email = "newuser@example.com"

        invitation, created = ProjectInvitation.objects.create_invitation(
            project=project, email=email, invited_by=inviter
        )

        self.assertTrue(created)
        self.assertIsNotNone(invitation.token)
        self.assertTrue(len(invitation.token) > 32)  # URL-safe token should be longer
        self.assertEqual(invitation.email, email.lower())
        self.assertEqual(invitation.project, project)
        self.assertEqual(invitation.invited_by, inviter)
        self.assertFalse(invitation.accepted)

    def test_create_invitation_sets_expiration(self):
        """Test that create_invitation sets expiration correctly."""
        project = ProjectFactory()
        inviter = UserFactory()
        email = "newuser@example.com"

        before = timezone.now()
        invitation, created = ProjectInvitation.objects.create_invitation(
            project=project, email=email, invited_by=inviter
        )
        after = timezone.now()

        self.assertTrue(created)
        # Expiration should be approximately 7 days from now
        expected_min = before + timedelta(days=7)
        expected_max = after + timedelta(days=7)

        self.assertGreaterEqual(invitation.expires_at, expected_min)
        self.assertLessEqual(invitation.expires_at, expected_max)

    def test_create_invitation_normalizes_email(self):
        """Test that email is normalized to lowercase."""
        project = ProjectFactory()
        inviter = UserFactory()
        email = "NewUser@Example.COM"

        invitation, created = ProjectInvitation.objects.create_invitation(
            project=project, email=email, invited_by=inviter
        )

        self.assertTrue(created)
        self.assertEqual(invitation.email, "newuser@example.com")

    def test_create_invitation_returns_existing_pending(self):
        """Test that creating duplicate invitation returns existing one."""
        project = ProjectFactory()
        inviter = UserFactory()
        email = "newuser@example.com"

        invitation1, created1 = ProjectInvitation.objects.create_invitation(
            project=project, email=email, invited_by=inviter
        )
        self.assertTrue(created1)

        invitation2, created2 = ProjectInvitation.objects.create_invitation(
            project=project, email=email, invited_by=inviter
        )
        self.assertFalse(created2)  # Second call should NOT create

        # Should return the same invitation
        self.assertEqual(invitation1.id, invitation2.id)
        self.assertEqual(invitation1.token, invitation2.token)

        # Should only have one invitation in DB
        count = ProjectInvitation.objects.filter(project=project, email=email).count()
        self.assertEqual(count, 1)

    def test_create_invitation_creates_new_if_previous_accepted(self):
        """Test that new invitation is created if previous one was accepted."""
        project = ProjectFactory()
        inviter = UserFactory()
        email = "newuser@example.com"

        # Create and accept first invitation
        invitation1, created1 = ProjectInvitation.objects.create_invitation(
            project=project, email=email, invited_by=inviter
        )
        self.assertTrue(created1)
        user = UserFactory(email=email)
        invitation1.accept(user)

        # Create second invitation
        invitation2, created2 = ProjectInvitation.objects.create_invitation(
            project=project, email=email, invited_by=inviter
        )
        self.assertTrue(created2)  # Should create new one

        # Should be a different invitation
        self.assertNotEqual(invitation1.id, invitation2.id)
        self.assertNotEqual(invitation1.token, invitation2.token)

    def test_create_invitation_creates_new_if_previous_expired(self):
        """Test that new invitation is created if previous one expired."""
        project = ProjectFactory()
        inviter = UserFactory()
        email = "newuser@example.com"

        # Create expired invitation
        invitation1 = ProjectInvitationFactory(
            project=project,
            email=email,
            invited_by=inviter,
            expires_at=timezone.now() - timedelta(days=1),
        )

        # Create new invitation
        invitation2, created = ProjectInvitation.objects.create_invitation(
            project=project, email=email, invited_by=inviter
        )
        self.assertTrue(created)  # Should create new one

        # Should be a different invitation
        self.assertNotEqual(invitation1.id, invitation2.id)
        self.assertNotEqual(invitation1.token, invitation2.token)

    def test_get_valid_invitation_returns_valid_invitation(self):
        """Test that get_valid_invitation returns valid invitation."""
        invitation = ProjectInvitationFactory()

        result = ProjectInvitation.objects.get_valid_invitation(invitation.token)

        self.assertIsNotNone(result)
        self.assertEqual(result.id, invitation.id)

    def test_get_valid_invitation_returns_none_for_invalid_token(self):
        """Test that get_valid_invitation returns None for invalid token."""
        result = ProjectInvitation.objects.get_valid_invitation("invalid-token-123")

        self.assertIsNone(result)

    def test_get_valid_invitation_returns_none_for_accepted_invitation(self):
        """Test that get_valid_invitation returns None for accepted invitation."""
        invitation = ProjectInvitationFactory(accepted=True)

        result = ProjectInvitation.objects.get_valid_invitation(invitation.token)

        self.assertIsNone(result)

    def test_get_valid_invitation_returns_none_for_expired_invitation(self):
        """Test that get_valid_invitation returns None for expired invitation."""
        invitation = ProjectInvitationFactory(expires_at=timezone.now() - timedelta(days=1))

        result = ProjectInvitation.objects.get_valid_invitation(invitation.token)

        self.assertIsNone(result)


class TestProjectInvitationModel(TestCase):
    """Test ProjectInvitation model instance methods and properties."""

    def test_str_representation(self):
        """Test string representation of invitation."""
        invitation = ProjectInvitationFactory(email="test@example.com")

        str_repr = str(invitation)

        self.assertIn("test@example.com", str_repr)
        self.assertIn(str(invitation.project.external_id), str_repr)

    def test_is_valid_returns_true_for_valid_invitation(self):
        """Test that is_valid returns True for valid invitation."""
        invitation = ProjectInvitationFactory(accepted=False, expires_at=timezone.now() + timedelta(days=7))

        self.assertTrue(invitation.is_valid)

    def test_is_valid_returns_false_for_accepted_invitation(self):
        """Test that is_valid returns False for accepted invitation."""
        invitation = ProjectInvitationFactory(accepted=True, expires_at=timezone.now() + timedelta(days=7))

        self.assertFalse(invitation.is_valid)

    def test_is_valid_returns_false_for_expired_invitation(self):
        """Test that is_valid returns False for expired invitation."""
        invitation = ProjectInvitationFactory(accepted=False, expires_at=timezone.now() - timedelta(hours=1))

        self.assertFalse(invitation.is_valid)

    def test_accept_marks_invitation_as_accepted(self):
        """Test that accept() marks invitation as accepted."""
        invitation = ProjectInvitationFactory()
        user = UserFactory(email=invitation.email)

        result = invitation.accept(user)

        self.assertTrue(result)
        invitation.refresh_from_db()
        self.assertTrue(invitation.accepted)
        self.assertIsNotNone(invitation.accepted_at)
        self.assertEqual(invitation.accepted_by, user)

    def test_accept_grants_project_access(self):
        """Test that accept() adds user as editor to project."""
        invitation = ProjectInvitationFactory()
        user = UserFactory(email=invitation.email)

        invitation.accept(user)

        # Check that user is now an editor
        self.assertTrue(invitation.project.editors.filter(id=user.id).exists())

    def test_accept_raises_error_for_accepted_invitation(self):
        """Test that accept() raises error if already accepted."""
        invitation = ProjectInvitationFactory(accepted=True)
        user = UserFactory()

        with self.assertRaises(ValueError) as context:
            invitation.accept(user)

        self.assertIn("no longer valid", str(context.exception))

    def test_accept_raises_error_for_expired_invitation(self):
        """Test that accept() raises error if expired."""
        invitation = ProjectInvitationFactory(expires_at=timezone.now() - timedelta(days=1))
        user = UserFactory()

        with self.assertRaises(ValueError) as context:
            invitation.accept(user)

        self.assertIn("no longer valid", str(context.exception))

    def test_unique_constraint_prevents_duplicate_pending_invitations(self):
        """Test that unique constraint prevents duplicate pending invitations."""
        project = ProjectFactory()
        inviter = UserFactory()
        email = "test@example.com"

        # Create first invitation
        ProjectInvitationFactory(project=project, email=email, invited_by=inviter, accepted=False)

        # Try to create duplicate - should raise IntegrityError
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            ProjectInvitationFactory(project=project, email=email, invited_by=inviter, accepted=False)

    def test_unique_constraint_allows_accepted_and_pending(self):
        """Test that accepted and pending invitations can coexist."""
        project = ProjectFactory()
        inviter = UserFactory()
        email = "test@example.com"

        # Create accepted invitation
        ProjectInvitationFactory(project=project, email=email, invited_by=inviter, accepted=True)

        # Create pending invitation - should succeed
        invitation = ProjectInvitationFactory(project=project, email=email, invited_by=inviter, accepted=False)

        self.assertIsNotNone(invitation.id)

    def test_external_id_is_auto_generated(self):
        """Test that external_id is automatically generated."""
        invitation = ProjectInvitationFactory()

        self.assertIsNotNone(invitation.external_id)

    def test_token_is_unique(self):
        """Test that token is unique across invitations."""
        invitation1 = ProjectInvitationFactory()
        invitation2 = ProjectInvitationFactory()

        self.assertNotEqual(invitation1.token, invitation2.token)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_send_valid_invitation_sends_email(self):
        """Test that send() sends email for valid invitation."""
        invitation = ProjectInvitationFactory(
            accepted=False,
            expires_at=timezone.now() + timedelta(days=7),
        )

        invitation.send(force_sync=True)

        # Verify email was sent
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertIn(invitation.email, msg.to)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_send_expired_invitation_does_not_send_email(self):
        """Test that send() does not send email for expired invitation."""
        invitation = ProjectInvitationFactory(
            accepted=False,
            expires_at=timezone.now() - timedelta(days=1),
        )

        invitation.send(force_sync=True)

        # Verify no email was sent
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_send_accepted_invitation_does_not_send_email(self):
        """Test that send() does not send email for accepted invitation."""
        invitation = ProjectInvitationFactory(
            accepted=True,
            expires_at=timezone.now() + timedelta(days=7),
        )

        invitation.send(force_sync=True)

        # Verify no email was sent
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_send_includes_project_name_in_context(self):
        """Test that send() includes project name in email context."""
        project = ProjectFactory(name="Important Business Project")
        invitation = ProjectInvitationFactory(
            project=project,
            accepted=False,
            expires_at=timezone.now() + timedelta(days=7),
        )

        invitation.send(force_sync=True)

        # Verify email contains project name (may have line breaks due to word wrapping)
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        # Remove line breaks for comparison
        body_normalized = msg.body.replace("\n", " ")
        self.assertIn("Important Business Project", body_normalized)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_send_uses_correct_email_template(self):
        """Test that send() uses the correct email template prefix."""
        invitation = ProjectInvitationFactory(
            accepted=False,
            expires_at=timezone.now() + timedelta(days=7),
        )

        invitation.send(force_sync=True)

        # Verify email was sent (template exists and was used)
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        # Check that subject and body are not empty (template was rendered)
        self.assertTrue(len(msg.subject) > 0)
        self.assertTrue(len(msg.body) > 0)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_send_with_force_sync_true(self):
        """Test that send() respects force_sync parameter."""
        invitation = ProjectInvitationFactory(
            accepted=False,
            expires_at=timezone.now() + timedelta(days=7),
        )

        # Send synchronously
        invitation.send(force_sync=True)

        # Verify email was sent immediately
        self.assertEqual(len(mail.outbox), 1)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_send_with_force_sync_false(self):
        """Test that send() works with force_sync=False (async)."""
        invitation = ProjectInvitationFactory(
            accepted=False,
            expires_at=timezone.now() + timedelta(days=7),
        )

        # Send asynchronously (default)
        invitation.send(force_sync=False)

        # Note: In test environment with console backend, async jobs may not
        # execute immediately. We just verify the method doesn't raise an error.
        # Actual email sending would be verified in integration tests.

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", FRONTEND_URL="http://localhost:9800"
    )
    def test_send_includes_invitation_url_in_email(self):
        """Test that send() includes a valid invitation URL in the email."""
        invitation = ProjectInvitationFactory(
            accepted=False,
            expires_at=timezone.now() + timedelta(days=7),
        )

        invitation.send(force_sync=True)

        # Verify email contains invitation URL
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]

        # Check the frontend URL format with token query parameter
        # Email body may have line breaks, so normalize it
        body_normalized = msg.body.replace("\n", "")
        expected_url_part = f"/project-invitation?token={invitation.token}"

        # Check plain text body
        self.assertIn(expected_url_part, body_normalized)

        # Verify the URL is well-formed (starts with http/https)
        self.assertIn("http", body_normalized.lower())

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", FRONTEND_URL="https://example.com"
    )
    def test_send_uses_configured_frontend_url(self):
        """Test that send() uses FRONTEND_URL from settings."""
        invitation = ProjectInvitationFactory(
            accepted=False,
            expires_at=timezone.now() + timedelta(days=7),
        )

        invitation.send(force_sync=True)

        # Verify email contains the configured frontend URL
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]

        expected_url = f"https://example.com/project-invitation?token={invitation.token}"
        body_normalized = msg.body.replace("\n", "")
        self.assertIn(expected_url, body_normalized)
