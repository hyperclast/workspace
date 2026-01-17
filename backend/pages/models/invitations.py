import secrets
import uuid
from typing import Optional

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django_extensions.db.models import TimeStampedModel

from backend.utils import log_info, log_warning
from core.emailer import Emailer
from pages.constants import PageEditorRole, ProjectEditorRole

User = get_user_model()


class PageInvitationManager(models.Manager):
    def create_invitation(self, page, email, invited_by, role=PageEditorRole.VIEWER.value):
        """Creates a new invitation with a secure token.

        Returns a tuple (invitation, created) where created is True if a new
        invitation was created, False if an existing one was returned.
        """
        # Check if there's already a valid pending invitation
        existing = self.filter(page=page, email__iexact=email, accepted=False, expires_at__gt=timezone.now()).first()

        if existing:
            # Return existing invitation (can be resent)
            return existing, False

        # Delete any expired pending invitations for this page/email combo
        # to avoid unique constraint violation
        self.filter(page=page, email__iexact=email, accepted=False, expires_at__lte=timezone.now()).delete()

        # Generate secure token
        token = secrets.token_urlsafe(settings.PAGE_INVITATION_TOKEN_BYTES)

        # Compute expiry
        expires_at = timezone.now() + settings.PAGE_INVITATION_TOKEN_EXPIRES_IN

        # Create invitation
        invitation = self.create(
            page=page,
            email=email.lower(),
            invited_by=invited_by,
            token=token,
            expires_at=expires_at,
            role=role,
        )

        return invitation, True

    def get_valid_invitation(self, token):
        """Get an invitation by token if it's still valid."""
        try:
            invitation = self.get(token=token, accepted=False, expires_at__gt=timezone.now())
            return invitation
        except self.model.DoesNotExist:
            return None


class PageInvitation(TimeStampedModel):
    """Invitation to collaborate on a page for users who don't have an account yet."""

    external_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    page = models.ForeignKey(
        "pages.Page",
        related_name="invitations",
        on_delete=models.CASCADE,
    )
    email = models.EmailField(db_index=True)
    invited_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="pagespage_invitations_sent",
    )
    token = models.TextField(unique=True)
    accepted = models.BooleanField(default=False)
    accepted_at = models.DateTimeField(null=True, blank=True)
    accepted_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pagespage_invitations_accepted",
    )
    expires_at = models.DateTimeField(db_index=True)
    role = models.TextField(
        choices=PageEditorRole.choices,
        default=PageEditorRole.VIEWER.value,
    )

    objects = PageInvitationManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["page", "email"],
                condition=models.Q(accepted=False),
                name="unique_pending_invitation_per_page",
            ),
        ]
        indexes = [
            models.Index(fields=["email", "accepted"]),
            models.Index(fields=["token", "accepted", "expires_at"]),
        ]

    def __str__(self):
        return f"Invitation for {self.email} to page {self.page.external_id}"

    @property
    def is_valid(self):
        """Check if invitation is still valid (not accepted and not expired)."""
        return not self.accepted and self.expires_at > timezone.now()

    @property
    def invitation_url(self):
        # Point to frontend invitation page instead of backend view
        return f"{settings.FRONTEND_URL}/invitation?token={self.token}"

    def accept(self, user):
        """Mark invitation as accepted and grant page access."""
        from pages.models import PageEditor

        if not self.is_valid:
            raise ValueError("Invitation is no longer valid")

        self.accepted = True
        self.accepted_at = timezone.now()
        self.accepted_by = user
        self.save(update_fields=["accepted", "accepted_at", "accepted_by", "modified"])

        # Add user as editor to the page with the invitation's role
        PageEditor.objects.get_or_create(
            user=user,
            page=self.page,
            defaults={"role": self.role},
        )

        log_info(
            "Invitation accepted: user=%s, page=%s, invitation=%s, role=%s",
            user.email,
            self.page.external_id,
            self.external_id,
            self.role,
        )

        return True

    def send(self, force_sync: Optional[bool] = False):
        if not self.is_valid:
            log_warning("Invitation %s has already expired or has been accepted.", self)
            return

        context = {
            "page_title": self.page.title,
            "invitation_url": self.invitation_url,
        }
        emailer = Emailer(
            template_prefix="pages/emails/page_invitation",
        )
        emailer.send_mail(
            email=self.email,
            context=context,
            force_sync=force_sync,
        )


class ProjectInvitationManager(models.Manager):
    def create_invitation(self, project, email, invited_by, role=ProjectEditorRole.VIEWER.value):
        """Creates a new project invitation with a secure token.

        Returns a tuple (invitation, created) where created is True if a new
        invitation was created, False if an existing one was returned.
        """
        # Check if there's already a valid pending invitation
        existing = self.filter(
            project=project, email__iexact=email, accepted=False, expires_at__gt=timezone.now()
        ).first()

        if existing:
            # Return existing invitation (can be resent)
            return existing, False

        # Delete any expired pending invitations for this project/email combo
        # to avoid unique constraint violation
        self.filter(project=project, email__iexact=email, accepted=False, expires_at__lte=timezone.now()).delete()

        # Generate secure token
        token = secrets.token_urlsafe(settings.PROJECT_INVITATION_TOKEN_BYTES)

        # Compute expiry
        expires_at = timezone.now() + settings.PROJECT_INVITATION_TOKEN_EXPIRES_IN

        # Create invitation
        invitation = self.create(
            project=project,
            email=email.lower(),
            invited_by=invited_by,
            token=token,
            expires_at=expires_at,
            role=role,
        )

        return invitation, True

    def get_valid_invitation(self, token):
        """Get an invitation by token if it's still valid."""
        try:
            invitation = self.get(token=token, accepted=False, expires_at__gt=timezone.now())
            return invitation
        except self.model.DoesNotExist:
            return None


class ProjectInvitation(TimeStampedModel):
    """Invitation to collaborate on a project for users who don't have an account yet."""

    external_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        "pages.Project",
        related_name="invitations",
        on_delete=models.CASCADE,
    )
    email = models.EmailField(db_index=True)
    invited_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="project_invitations_sent",
    )
    token = models.TextField(unique=True)
    accepted = models.BooleanField(default=False)
    accepted_at = models.DateTimeField(null=True, blank=True)
    accepted_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="project_invitations_accepted",
    )
    expires_at = models.DateTimeField(db_index=True)
    role = models.TextField(
        choices=ProjectEditorRole.choices,
        default=ProjectEditorRole.VIEWER.value,
    )

    objects = ProjectInvitationManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["project", "email"],
                condition=models.Q(accepted=False),
                name="unique_pending_project_invitation",
            ),
        ]
        indexes = [
            models.Index(fields=["email", "accepted"]),
            models.Index(fields=["token", "accepted", "expires_at"]),
        ]

    def __str__(self):
        return f"Invitation for {self.email} to project {self.project.external_id}"

    @property
    def is_valid(self):
        """Check if invitation is still valid (not accepted and not expired)."""
        return not self.accepted and self.expires_at > timezone.now()

    @property
    def invitation_url(self):
        # Point to frontend invitation page for projects
        return f"{settings.FRONTEND_URL}/project-invitation?token={self.token}"

    def accept(self, user):
        """Mark invitation as accepted and grant project access."""
        from pages.models import ProjectEditor

        if not self.is_valid:
            raise ValueError("Invitation is no longer valid")

        self.accepted = True
        self.accepted_at = timezone.now()
        self.accepted_by = user
        self.save(update_fields=["accepted", "accepted_at", "accepted_by", "modified"])

        # Add user as editor to the project with the invitation's role
        ProjectEditor.objects.get_or_create(
            user=user,
            project=self.project,
            defaults={"role": self.role},
        )

        log_info(
            "Project invitation accepted: user=%s, project=%s, invitation=%s, role=%s",
            user.email,
            self.project.external_id,
            self.external_id,
            self.role,
        )

        return True

    def send(self, force_sync: Optional[bool] = False):
        if not self.is_valid:
            log_warning("Project invitation %s has already expired or has been accepted.", self)
            return

        context = {
            "project_name": self.project.name,
            "invitation_url": self.invitation_url,
        }
        emailer = Emailer(
            template_prefix="pages/emails/project_invitation",
        )
        emailer.send_mail(
            email=self.email,
            context=context,
            force_sync=force_sync,
        )
